#!/usr/bin/python

import sys
import yaml
import argparse

# Find arguments and flags
try:
	parser = argparse.ArgumentParser (description = 'Replaces specific strings with variable names in text files')
	parser.add_argument('srcFile',
					   help='the source file with text to be parsed')
	parser.add_argument('varFile',
					   help='a YAML file with variables to be used in replacements')
	parser.add_argument('--verbose', action="store_true",
					   help='if additional output should be shown')
	parser.add_argument('--noOutput', action="store_true",
					   help='does not output the replaced text, it does show the verbose info')
	args = parser.parse_args()
	txtFile = args.srcFile
	varFile = args.varFile
	verbose = args.verbose
	noOutput = args.noOutput
except Exception as e:
	parser.print_help ()
	sys.exit (0)

def replace_all (text, myDict):

	for var in myDict:
		for key in var:
			old = key
			new = "{{" + var[key] + "}}"
			if verbose:
				print "Replacing %s with %s" % (old, new)
			text = text.replace (old, new)
	return text

# Open Variables file and assign contents to myDict
try:
	with open (varFile, 'r') as vars:
		myDict = yaml.safe_load (vars)
		if verbose:
			print "The following dictionary has been loaded: %s" % str (myDict)
except Exception as e:
    print "Can't open file %s: %s" % (varFile, str (e))

# Open and process Source File
try:
	with open (txtFile, 'r') as src:
		data = src.read()
except Exception as e:
    print "Can't open file %s: %s" % (txtFile, str (e))
# Replace the variables according to the dictionary
newdata = replace_all (data, myDict)
if not noOutput:
	print newdata
