'''

Created by Jose Moreno, January 2016
v0.1

Generates a WFDX with a custom task that can be imported in UCS Director. The custom
  task will post a JSON/XML file to ACI.

Arguments:
1. JSON/XML captured with the API Inspector or the "Save As" ACI functionality
2. Variable YAML file, with the strings to be replaced with variables. For example:
tenant_name_in_my_JSON_file: tenantName
3. Name: the name coded in the WFDX file for the new custom task

Requires having the file RESTcall.js in the same directory (template for generating
Java Script code), plus the python library request.py

Example:
python ./genWFDX.py examples/tenant/tn-HelloWorld-Tom.json examples/tenant/variables.yml myNewTenant >myCustomTask.wfdx


'''

import request
import yaml
import sys
import argparse

if __name__ == "__main__":
	# Find arguments and flags
	try:
		parser = argparse.ArgumentParser (description = 'Process XML or JSON code, and generate a WFDX file that can be imported to UCS Director')
		parser.add_argument('dataFile',
						   help='the file where JSON/XML code is stored')
		parser.add_argument('varFile',
						   help='the file containing variables in YAML format')
		parser.add_argument('taskName',
						   help='the name to be given to the task in the WFDX file')
		parser.add_argument('--onlyJS', action="store_true",
						   help='specify if you only want to generate JavaScript code, instead of the whole WFDX file')
		parser.add_argument('--onlyPayload', action="store_true",
						   help='specify if you only want to generate parametrised JSON/XML code, instead of the whole WFDX file')
		parser.add_argument('--verbose', action="store_true",
						   help='if additional verbose output should be shown (aka debug)')
		args = parser.parse_args()
		dataFile = args.dataFile
		varFile = args.varFile
		taskName = args.taskName
		onlyJS = args.onlyJS
		onlyPayload = args.onlyPayload
		debug = args.verbose
	except Exception as e:
		parser.print_help ()
		sys.exit (0)

	# Try to open both files
	# Load information from YAML file
	try:
		with open (dataFile, 'r') as payload:
			data = payload.read ()
	except Exception as e:
		print "ERROR: Could not find data file %s" % dataFile
		sys.exit (0)
	# Load information from YAML file
	try:
		with open (varFile, 'r') as variables:
			varDict = yaml.safe_load (variables)
		if debug:
			print "Variables read from file: %s" % str (varDict)
	except Exception as e:
		print "ERROR: Could not find variables file %s or file not YAML-conform" % varFile
		sys.exit (0)
	# At this point we have everything we need

	# Step 1: replace the variables in the file with the right syntax "{{variable_name}}"
	for old in varDict.keys():
		if debug:
			print "Replacing string occurrence %s" % old
		new = "{{" + varDict[old] + "}}"
		data = data.replace (old, new)
	if onlyPayload:
		print data
		sys.exit (0)
	
	# Step 2: generate JavaScript code out the of the parametrised JSON/XML code
	jsVarList = request.generateJSVarList (data)
	jscode = request.generateJS (data, jsVarList)
	if onlyJS:
		print jscode				
		sys.exit (0)

	# Step 3: generate the WFDX file out of the JS code
	wfdx = request.generateWFDX (jscode, taskName, jsVarList)
	print wfdx
