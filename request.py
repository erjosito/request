#!/usr/bin/python
'''

Created by Jose Moreno, January 2016
v0.3

Expansion of an existing file (request.py) that was able to concatenate multiple
REST requests to ACI.

This script can parametrise those requests so that they can be reused

Additionally, it can generate content that can be leveraged in UCS Director, such as
JavaScript code for custom tasks, or a WFDX file containing the tasks themselves.

Requires having the file RESTcall.js in the same directory (template for generating
Java Script code)

'''

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
import base64

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
		variables = []
		variablesDefined = False
		pass
	tests = config['tests']
	try:
		rollbackTests = config ['rollback']
		tests += rollbackTests
	except Exception as E:
		# No rollback section defined
		pass
	errorsFound = 0
	for t in tests:
		type = t['type']
		file = t['file']

		# Do something only if we are speaking of a JSON/XML test
		if type=='json' or type=='xml':
			if debug:
				print "Checking test %s" % file
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

			# Get the URL (if any)
			try:
				url = t['url']
				urlDefined = True
			except Exception as e:
				# Probably no URL defined
				urlDefined = False
				pass

			# See that the file exists
			try:
				with open (file, 'r') as payload:
					data = payload.read()
			except Exception as e:
				print "ERROR: Could not open file %s: %s" % (file, str(e))
				sys.exit (0)

			# Analyze the file content and the URL for variables, and compare them to the variable list
			errorsFound += checkVariables (data, localVariables)
			if urlDefined:
				errorsFound += checkVariables (url, localVariables)			
	print "%s errors found" % errorsFound

def checkVariables (data, variableList):
	errorsFound = 0
	# Find variables in the file
	hits = re.findall ("\{\{[\w\s\.\-\_]+\}\}", data)
	# Remove duplicates converting to a set and back to an array
	hits = set (hits)
	for hit in hits:
		# Remove the "{{" and "}}"
		hit = hit [2 : len (hit)-2]
		if len(variableList) > 0:
			# Look for that var in the variables dictionary
			keyFound = False
			for var in variableList:
				for key in var:
					if key == hit:
						keyFound = True
						if debug:
							print "Variable %s found in config file" % key
			if not keyFound:
				print "ERROR: Variable %s not found in the config file" % hit
				errorsFound += 1
		else:
			print "ERROR: Variable %s found, although no variable defined in config file" % hit
			errorsFound += 1
		return errorsFound

# Returns a list with all variables to be defined in a JS file
def generateJSVarList (data):
	# Initialize (these 3 variables need to be there always
	jsVarList = ["apicIP", "username", "password"]
	# Find all "{{x}}" variables in the JSON file
	hits = re.findall ("\{\{[\w\s\.\-\_]+\}\}", data)
	# Remove duplicates converting to a set
	hits = set (hits)
	for hit in hits:
		# Remove the "{{" and "}}"
		varName = hit [2 : len (hit)-2]
		jsVarList.append (varName)
	# And return it
	return jsVarList

# Generates JavaScript code for an UCSD custom task
# It requires the JSON code to be pushed, plus a list of variables to be defined in the script
def generateJS (name, data, jsVarList, rollbackTaskName):
	# Load the template for the JavaScript file, it needs to be stored in the same
	#   directory as this script
	jstemplate = os.path.join(os.path.dirname(__file__), 'RESTcall.js')
	try:
		js = open (jstemplate,'r')
		jscode = js.read ()
	except Exception as e:
		print "ERROR: Could not find JavaScript template %s" % jstemplate
		sys.exit (1)
	# First we need to escape the quote signs and escape the CR (or LF?) characters
	# Help: chr(34)=", chr(39)=', chr(92)=\, chr(10)=LF, chr(13)=CR
	data = data.replace (chr(34), chr(92) + chr(34))
	data = data.replace (chr(39), chr(92) + chr(34))
	data = data.replace (chr(10), chr(92)+chr(10))
	# Instead of replacing the variables with its real value, we need to
	#  change them to JS format. For example, where it said tn-{{tenantName}}
	#  we need to write tn-"+tenantName+"
	jsVars = ""
	for varName in jsVarList:
		# Put the variable in Javascript format
		if varName != "username" and varName != "password" and varName != "apicIP":
			old = "{{" + varName + "}}"
			new = '" + ' + varName + ' + "'
			data = data.replace (old, new)
		jsVars += "var " + varName + " = input." + varName + ";\n"		
	# Now we need to create our JavaScript. There are 3 items we need to
	#   modify from the JSTemplate:
	#   1. Create variables (our variable list plus global parameters)
	#	2. Assign the data variable
	#   3. Assign the URL variable
	jscode = jscode.replace ("{{Variables}}", jsVars)
	jscode = jscode.replace ("{{data}}", data)
	jscode = jscode.replace ("{{name}}", name)
	if type == 'xml':
		url = '/api/node/mo/.xml'
	else:
		url = '/api/node/mo/.json'
	jscode = jscode.replace ("{{url}}", url)
	# Set output variables (NOT SUPPORTED YET)
	jscode = jscode.replace ("{{outputVariables}}", "")

	# Set HTTP / HTTPS
	if useHttps:
		jscode = jscode.replace ("{{protocol}}", "https")
	else:
		jscode = jscode.replace ("{{protocol}}", "http")
	
	# Now we need to add code to register a rollback task (if one has been provided)
	if len (rollbackTaskName) > 0:
		rollbackFunction = generateRollbackFunction (rollbackTaskName, jsVarList)
		rollbackRegister = generateRollbackRegister (jsVarList)
	else:
		rollbackFunction = ""
		rollbackRegister = ""
	jscode = jscode.replace ("{{rollbackRegister}}", rollbackRegister)
	jscode = jscode.replace ("{{rollbackFunction}}", rollbackFunction)	
	# We are done!
	return jscode

# Generate a rollback register statement for a UCS Director script
def generateRollbackRegister (jsVars):
	template = "registerUndoTask({{inputArgs}});"
	args=""
	for varName in jsVars:
		if len(args) > 0:
			args += ","
		args += varName
	template = template.replace ("{{inputArgs}}", args)
	return template

# Generate a JavaScript function that can be used in a UCS Director task to register
#   a rollback task
def generateRollbackFunction (name, jsVars):
	fncTemplate = """function registerUndoTask({{inputArgs}}) {
		// register undo task    
		var undoHandler = "custom_{{name}}";
		var undoContext = ctxt.createInnerTaskContext(undoHandler);
		var undoConfig = undoContext.getConfigObject();
{{undoVars}}
		// SYNTAX: ChangeTracker.undoableResourceModified (input.assetType, input.assetId, input.assetLabel, input.description, undoTaskHandlerName, configObject)
		ctxt.getChangeTracker().undoableResourceModified(
					 {{resource}}, 
					 {{resource}},
					 {{resource}},
					 {{resource}},
					 undoHandler,
					 undoConfig);
		}"""
	# Generate the function argument list
	args=""
	for varName in jsVars:
		if len(args) > 0:
			args += ","
		args += varName
	fncTemplate = fncTemplate.replace ("{{inputArgs}}", args)
	# Replace the rollback function name
	fncTemplate = fncTemplate.replace ("{{name}}", name)
	# undoConfig variables
	undoVars = ""
	for varName in jsVars:
		undoVars += "		undoConfig." + varName + " = " + varName + ";\n"
	fncTemplate = fncTemplate.replace ("{{undoVars}}", undoVars)
	# getChangeTracker: we use the task name for everything
	# BTW, here its syntax: ChangeTracker.undoableResourceModified(input.assetType,
	#    input.assetId, input.assetLabel, input.description, undoTaskHandlerName, configObject) ;
	if len (jsVars) > 3:
		# Option 1: use the 1st variable after IP, user and pwd, and assume it is meaningful
		resource = jsVars [3]
	else:
		# Option 2: use just the name of the rollback task
		resource = '"%s"' % name

	fncTemplate = fncTemplate.replace ("{{resource}}", resource)
	# We are done!
	return fncTemplate



# Generate the WFDX for an UCSD custom task
# It requires a name to be given to the task, plus the list of input variables to be defined
def generateWFDX (jscode, taskName, jsVarList):
	# We will use the filename (minus extension) as task name
	JSONtaskTemplate = '{"name":"{{Name}}","label":"{{Name}}","registerUnderTree":"{{Tree}}","ucsdFromVersion":null,"isActive":true,"summary":"","description":"","config":{"name":"InputConfig","fields":{"list":[{{InputVariables}}],"moTypeName":"com.cloupia.service.cIM.inframgr.mdui.MDUIFieldDescr","validatorName":"MDUIFieldListValidator"}},"outputs":{"list":[{{OutputVariables}}],"moTypeName":"com.cloupia.service.cIM.inframgr.mdui.MDUIWorkflowTaskOutputDescr","validatorName":"MDUIOutputListValidator"},"executionLang":"Javascript","executionScript":"{{Script}}","controllerImpl":{"list":[],"moTypeName":"com.cloupia.lib.cMacroUI.MacroControllerScript","validatorName":null}}'
	JSONtask = JSONtaskTemplate.replace ("{{Name}}", taskName)
	JSONtask = JSONtask.replace ("{{Tree}}", "APIC")

	# Now generate JSON for the input variables
	JSONvars = ""
	JSONvarTemplate = '{"name":"{{Name}}","label":"{{Name}}","persist":true,"columnInfo":null,"type":"{{type}}","mapToType":"gen_text_input","mandatory":true,"rbid":"","size":"medium","help":"","annotation":"","group":"","validate":false,"formManagedTable":false,"addEntryForm":"","editEntryForm":"","deleteEntryForm":"","moveUpForm":"","moveDownForm":"","infoEntryForm":"","runActionForm":"","editabe":true,"hidden":false,"multiline":false,"maxLength":128,"lov":"","lovProvider":"","order":99999,"uploadDir":"","table":"","validator":"","regex":".*","regexLabel":".*","minValue":-9223372036854775808,"maxValue":9223372036854775807,"hideFieldName":"","hideFieldValue":"","hideFieldCondition":"EQ","htmlPopupTag":"","htmlPopupLabel":"","htmlPopupStyle":0,"htmlPopupText":"","view":"","values":[]}'
	# We had compiled a list of variables
	for varName in jsVarList:
		if len(JSONvars) > 0:
			JSONvars += ","
		thisJSONvar = JSONvarTemplate.replace ("{{Name}}", varName)
		# Normally all input fields are text, but for the password we want to change that
		if varName == "password":
			thisJSONvar = thisJSONvar.replace ("{{type}}", "password")
		else:
			thisJSONvar = thisJSONvar.replace ("{{type}}", "text")
		JSONvars += thisJSONvar

	JSONtask = JSONtask.replace ("{{InputVariables}}", JSONvars)

	# No output variables for the time being...
	JSONtask = JSONtask.replace ("{{OutputVariables}}", "")

	# And finally, the script (we need to escape backslash and double quotes first)
	escapedJScode = jscode.replace (chr (92), chr (92) + chr (92))			    	# \ -> \\
	escapedJScode = escapedJScode.replace (chr (34), chr (92) + chr (34))           # " -> \"

	JSONtask = JSONtask.replace ("{{Script}}", escapedJScode)

	# Last step, encoding to Base64
	JSONtask64 = base64.b64encode (JSONtask)

	# And finally, wrap it up in XML
	XMLtaskTemplate = '<UnifiedFeatureAssetInfo><addiInfo></addiInfo><featureAssetEntry><data><![CDATA[{"taskName":"{{Name}}","taskLabel":"{{Name}}","isActive":true,"taskSummary":"","taskDescription":"","taskDetails":"{{taskDetails}}","taskData":"{{TaskData64}}"}]]></data></featureAssetEntry><type>CUSTOM_TASKS</type></UnifiedFeatureAssetInfo>'
	XMLtask = XMLtaskTemplate.replace ("{{TaskData64}}", JSONtask64)
	XMLtask = XMLtask.replace ("{{Name}}", taskName)
	# No task details supported as of this version
	XMLtask = XMLtask.replace ("{{taskDetails}}", "Task detail generation not supported just yet")

	# We are done
	return XMLtask

# To generate some code that can be leveraged in UCS Director: either JavaScript code that
#   can be used in custom tasks, or a WFDX file containing custom tasks (with that JS
#   code already embedded) that can be imported in UCSD	
def generateUCSDCode (config, printJs, printWfdx):
	# Browse the tests
	tests = config['tests']
	# Including the rollback section, if defined
	try:
		rollbackTests = config ['rollback']
		rollbackDefined = True
	except Exception as E:
		rollbackDefined = False
		pass
	if rollbackDefined:
		tests = tests + rollbackTests
		rollbackDict = createRollbackDict (config)
		if debug:
			print "DEBUG: Rollback dictionary: %s" % str (rollbackDict)

	# Add first part (sort of a header) of the WFDX file
	wfdx = '<?xml version="1.0" ?><OrchExportInfo><Time>Tue Jan 05 12:31:03 UTC 2016</Time><User></User><Comments></Comments>'
	
	# Browse the tests, and add one section to the WFDX file per test
	for t in tests:
		type = t['type']
		file = t['file']
		# Try to open the JSON file
		if type == 'json' or type == 'xml':
			try:
				fileFound = True
				payload = open (file,'r')
				data = payload.read ()
			except Exception as e:
				print "ERROR: Could not find file %s" % file
				fileFound = False
			if fileFound:			
				# We will use the test filename as name for the custom task
				taskName = getBareFileName (file)
				# Generate the JS code
				jsVarList = generateJSVarList (data)
				# We need to register a rollback task if:
				# 1. rollback is defined AND
				# 2. this specific commit task is to be associated with a rollback task
				if rollbackDefined:
					if file in rollbackDict.keys():
						rollbackTaskName = getBareFileName (rollbackDict[file])
					else:
						rollbackTaskName = ""
				else:
					rollbackTaskName = ""
				jscode = generateJS (taskName, data, jsVarList, rollbackTaskName)
				if printJs:
					print jscode				
				# Add task to WFDX code
				wfdx += generateWFDX (jscode, taskName, jsVarList)
	# Close the WFDX file (sort of a footer)
	wfdx += "<version>3.0</version></OrchExportInfo>"
	if printWfdx:
		print wfdx			

# Returns the bare file name of a path, without the extension or the directories 
def getBareFileName (file):
	# First, remove the extension (it can be JSON or XML)
	# There is a better way of removing ANY extension, something to do later
	if file[len(file)-4:len(file)] == "json":
		aux = file[0:len(file)-5]
	elif file[len(file)-3:len(file)] == "xml":
		aux = file[0:len(file)-4]
	# If filename contains a path, take only the filename
	for i in range (0, len (aux)):
		if aux[i] == "/":
			aux2 = aux [i+1 : len(aux)]
	# We are done
	return aux2


# This function creates a dictionary with entries for all commit tasks that need a rollback task
def createRollbackDict (config):
	commitTests = config ['tests']
	rollbackTests = config ['rollback']
	dict = {}
	for i in range (0, len (rollbackTests)):
		dict [commitTests[i]['file']] = rollbackTests[i]['file']
	return dict

# Run in standard mode: assume a login to the fabric has been mode, send all tests
#  (commit or rollback) to the fabric
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
	
	# Load the tests to run (depending whether the rollback option has been specified in the command line)
	if rollback:
		try:
			tests = config['rollback']
		except Exception as e:
			print "Error: no rollback section defined in config file"
			sys.exit (0)
	else:
		try:
			tests = config['tests']
		except Exception as e:
			print "Error: no main section defined in config file"
			sys.exit (0)
	
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
					# Read URL (if no path defined, use a standard URL)
					try:
						path = t['path']
						# Check if user forgot the leading "/"
						if path[0] != "/":
							path = "/" + path
						# Append path to URL
						url = 'http://%s%s' % (config['host'],path)
						# Check the URL for variables too
						if (variablesDefined or localVariablesDefined):
							url = replaceVariables (localVariables, url)
					except Exception as e:
						# We probably found no 'path' attribute
						url = 'http://%s/api/node/mo/.xml' % config['host']
						pass
					# Send POST
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
					# Read URL (if no path defined, use a standard URL)
					try:
						path = t['path']
						# Check if user forgot the leading "/"
						if path[0] != "/":
							path = "/" + path
						# Append path to URL
						url = 'http://%s%s' % (config['host'],path)
						# Check the URL for variables too
						if (variablesDefined or localVariablesDefined):
							url = replaceVariables (localVariables, url)
					except Exception as e:
						# We probably found no 'path' attribute
						url = 'http://%s/api/node/mo/.json' % config['host']
						pass
					# Send POST
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
		parser.add_argument('--rollback', action="store_true",
						   help='if the rollback section of the workflow should be executed, instead of the main section')
		parser.add_argument('--verbose', action="store_true",
						   help='if additional verbose output should be shown (aka debug)')
		parser.add_argument('--ucsdjs', action="store_true",
						   help='choose this option to print in stdout the JavaScript code you can use in an UCSD custom task')
		parser.add_argument('--ucsdwfdx', action="store_true",
						   help='choose this option to print in stdout the contents of a WFDX file containing custom tasks that can be imported in UCSD')
		parser.add_argument('--https', action="store_true",
						   help='choose this option to use HTTPS for the custom tasks that can be imported in UCSD')
		args = parser.parse_args()
		cfgFile = args.configFile
		testVariables = args.testVariables
		debug = args.verbose
		ucsdjs = args.ucsdjs
		ucsdwfdx = args.ucsdwfdx
		rollback = args.rollback
		useHttps = args.https
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
	elif (ucsdjs):
		generateUCSDCode (config, True, False)
	elif (ucsdwfdx):
		generateUCSDCode (config, False, True)
	# Run the workflow normally
	else:
		status = 0
		cookies = login (config)
		if status == 200:
			runConfig (config, cookies)
	