#!/usr/bin/python

import glob
import json
import os
import os.path
import requests
import sys
import time
import xml.dom.minidom
import yaml
import argparse
import re


# Browse the translation dictionary and solve recursive dependencies
# Currently only one level of hierarchy supported (variables inside variables)
def resolveVariables (variables):
	for var in variables:
		for key in var:				
			# If any variable defined in the variable value
			hits = re.findall ("\{\{[\w\s\.\-\_]+\}\}", var[key])
			if len(hits) > 0:
				replacedVariable = replaceVariables (variables, var[key])
				var[key] = replacedVariable
	return variables
				

# Merge a set of local and global variables
# If the same variable exists in both sets, the local variable has preference
def mergeVariables (localVariables, globalVariables):
	# Browse globalVariables for duplicates, and eliminate them
	for lvar in localVariables:
		for lkey in lvar:
			for gvar in globalVariables:
				for gkey in gvar:
					if lkey == gkey:
						globalVariables.remove (gvar)
	# Merge both lists, now there should not be any duplicate
	mergedVariables = globalVariables + localVariables
	mergedVariables = resolveVariables (mergedVariables)
	if debug:
		print 'Merging variable lists:'
		print ' - Global variable list: %s' % str (globalVariables)
		print ' - Local variable list:  %s' % str (localVariables)
		print ' - Merged variable list: %s' % str (mergedVariables)
	return mergedVariables

# Replace variables (defined in the list "variables") in a text ("data")
# Modes (variable definition syntax)
#   0: default, variables defined like {{variable_name}}
#   1: variables defined like %{variable_name}
def replaceVariables (variables, data, mode = 0):

	if len (variables) > 0:
		newdata = data
		# Replace all occurrences of the variable with its value
		for var in variables:
			for key in var:				
				try:
					if mode == 1:
						old = "%{" + key + "}"
					else:
						old = "{{" + key + "}}"
					new = var [key]
					newdata = newdata.replace (old, new)
				except Exception as e:
					print "Error when processing key %s: %s" % (key, str (e)) 
					sys.exit (0)
		if debug:
			print '++++ Variable substitution ++++'
			print newdata
			print '---- Variable substitution ----'                 	
		return newdata
	else:
		return data

def chkConfig (config):
	# Additional logic reading variables, since it could not have been defined in the YAML file
	try:
		variablesDefined = True
		variables = config['variables']
		# Resolve recursive variables (currently only one level of recursion supported)
		variables = resolveVariables (variables)
	except Exception as e:
		# Probably no variables section in the file
		print "ERROR: No variables defined in the config file!"
		variables = ""
		variablesDefined = False
		pass
	tests = config['tests']
	for t in tests:
		type = t['type']
		file = t['file']
		# Get local variables
		try:
			localVariablesDefined = True
			localVariables = t['variables']
			# Merge local Variables with global Variables (if defined)
			# mergeVariables already takes care of recursive variables
			if variablesDefined:
				localVariables = mergeVariables (variables, localVariables)
			if debug:
				print 'Local variables found, merged variable list: %s' % str (localVariables)
		except Exception as e:
			# Probably no variables section in this test
			localVariablesDefined = False
			localVariables = variables
			pass

		if type=='json' or type=='xml':
			try:
				with open (file, 'r') as payload:
					data = payload.read()
			except Exception as e:
				print "ERROR: Could not open file %s: %s" % (file, str(e))
			# Find variables in the file
			hits = re.findall ("\{\{[\w\s\.\-\_]+\}\}", data)
			# Remove duplicates converting to a set and back to an array
			hits = set (hits)
			for hit in hits:
				# Remove the "{{" and "}}"
				hit = hit [2 : len (hit)-2]
				if (variablesDefined or localVariablesDefined):
					# Look for that var in the variables dictionary
					keyFound = False
					for var in localVariables:
						for key in var:
							if key == hit:
								keyFound = True
								if debug:
									print "Variable %s found in config file" % key
					if not keyFound:
						print "ERROR: Variable %s (present in file %s) not found in the config file" % (hit, file)
				else:
					print "ERROR: Variable %s (present in file %s), although no variable defined in config file" % (hit, file)

def runConfig (config, cookies):
	# Variablie initialization
	global status
	cntSuccess = 0
	cntFailed  = 0

	try:
		variablesDefined = True
		variables = config['variables']
		# Resolve recursive variables (currently only one level of recursion supported)
		variables = resolveVariables (variables)		
	except Exception as e:
		# Probably no variables section in the file
		variablesDefined = False
		variables = ""
		pass
	tests = config['tests']
	for t in tests:
		type = t['type']
		file = t['file']

		# See whether there are local variables in this test
		try:
			localVariablesDefined = True
			localVariables = t['variables']
			# Merge local Variables with global Variables (if defined)
			# mergeVariables already takes care of recursive variables
			if variablesDefined:
				localVariables = mergeVariables (variables, localVariables)
		except Exception as e:
			# Probably no variables section in this test
			localVariablesDefined = False
			localVariables = variables
			pass
		
		# Verify the file exists
		try:
			fileFound = True
			test = open (file,'r')
		except Exception as e:
			print "ERROR: Could not find file %s" % file
			fileFound = False

		if fileFound:

			if type=='file':
				url = 'http://%s/%s' % (config['host'],t['path'])
				with open(file,'r') as package:
					if ( status==200) and ('wait' in t):
						time.sleep( t['wait'] )
					else:
						raw_input( 'Hit return to upload %s' % file )
					print 'url is (%s)' %url
					r = requests.post( url, 
									   cookies=cookies,
									   files={'file':package} )
					result = xml.dom.minidom.parseString( r.text )
					status = r.status_code
					if status == 200:
						cntSuccess += 1
					else:
						cntFailed += 1
					if debug:
						print '++++++++ RESPONSE (%s) ++++++++' % file
						print result.toprettyxml()
						print '-------- RESPONSE (%s) --------' % file
						print status

			elif type=='xml':
				with open( file, 'r' ) as payload:
					if ( status==200) and ('wait' in t):
						time.sleep( t['wait'] )
					else:
						raw_input( 'Hit return to process %s' % file )

					data = payload.read()
					if debug:			
						print '++++++++ REQUEST (%s) ++++++++' % file
						print data
						print '-------- REQUEST (%s) --------' % file 
					# If any substitution variable has been specified, replace and show
					if (variablesDefined or localVariablesDefined):
						data = replaceVariables (localVariables, data)
					# Post (always use the generic root URL?)
					url = 'http://%s/api/node/mo/.xml' % config['host']
					#url = 'http://%s/%s' % (config['host'],t['path'])
					# Check the URL for variables too
					#if (variablesDefined or localVariablesDefined):
					#	url = replaceVariables (localVariables, url)
					r = requests.post( url,
									   cookies = cookies,
									   data = data )
					result = xml.dom.minidom.parseString( r.text )
					status = r.status_code
					if status == 200:
						cntSuccess += 1
					else:
						cntFailed += 1
					if debug:
						print '++++++++ RESPONSE (%s) ++++++++' % file
						print result.toprettyxml()
						print '-------- RESPONSE (%s) --------' % file
						print status

			elif type=='json':
				with open( file, 'r' ) as payload:
					if( status==200) and ('wait' in t):
						time.sleep( t['wait'] )
					else:
						raw_input( 'Hit return to process %s' % file )

					data = payload.read()
					if debug:
						print '++++++++ REQUEST (%s) ++++++++' % file
						print data
						print '-------- REQUEST (%s) --------' % file 
					# If any substitution variable has been specified, replace and show
					if (variablesDefined or localVariablesDefined):
						data = replaceVariables (localVariables, data)
					# Post (always use the generic root URL?)
					url = 'http://%s/api/node/mo/.json' % config['host']
					#url = 'http://%s/%s' % (config['host'],t['path'])
					# Check the URL for variables too
					#if (variablesDefined or localVariablesDefined):
					#	url = replaceVariables (localVariables, url)
					r = requests.post( url,
									   cookies = cookies,
									   data = data )
					result = json.loads ( r.text )
					status = r.status_code
					if status == 200:
						cntSuccess += 1
					else:
						cntFailed += 1
					if debug:
						print '++++++++ RESPONSE (%s) ++++++++' % file
						print r.text
						print '-------- RESPONSE (%s) --------' % file
						print status
			else:
				print 'Unknown type:', type
	print "%s configs successful, %s configs failed" % (cntSuccess, cntFailed)

def login (config):
	global status
	# Make auth payload (using JSON)
	auth = {
		'aaaUser': {
			'attributes': {
				'name': config['name'],
				'pwd': config['passwd']
				}
			}
		}
	# Send the login POST request
	while (status != 200):
		url = 'http://%s/api/aaaLogin.json' % config['host']
		while(1):
			try:
				r = requests.post( url, data=json.dumps(auth), timeout=1 )
				break;
			except Exception as e:
				print "APIC Login timeout"
		status = r.status_code
		if status == 200:
			if debug:
				print "Logged on to APIC %s" % config['host']
		else:
			print "Error logging in to APIC %s" % config['host']
		cookies = r.cookies
		time.sleep (1)
		return cookies

if __name__ == "__main__":
	
	# Find arguments and flags
	try:
		parser = argparse.ArgumentParser (description = 'Process config files and send them to ACI')
		parser.add_argument('configFile',
						   help='the config file name where variables, URLs and configs are specified')
		parser.add_argument('--testVariables', action="store_true",
						   help='if requests.py should just verify that all variables have been specified in the config file')
		parser.add_argument('--verbose', action="store_true",
						   help='if additional output should be shown')
		args = parser.parse_args()
		cfgFile = args.configFile
		testVariables = args.testVariables
		debug = args.verbose
	except Exception as e:
		parser.print_help ()
		sys.exit (0)

	# Load information from YAML file
	with open( cfgFile, 'r' ) as config:
		config = yaml.safe_load (config)

	# Do what you have to do:
	# - either testing (verify all variables are correctly defined)
	if testVariables:
		chkConfig (config)
	# - or the real thing (login first, do the magic second)
	else:
		status = 0
		cookies = login (config)
		if status == 200:
			runConfig (config, cookies)
	
