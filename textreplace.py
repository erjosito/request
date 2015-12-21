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
	args = parser.parse_args()
	txtFile = args.srcFile
	varFile = args.varFile
except Exception as e:
	parser.print_help ()
	sys.exit (0)

def replace_all (text, myDict):
	for old, new in myDict.iteritems ():
		new = "{{" + new + "}}"
		text = text.replace (old, new)
	return text

# Open Variables file and assign contents to myDict
try:
	with open (varFile, 'r') as vars:
		myDict = yaml.safe_load (vars)
		print myDict
except Exception as e:
    print "Can't open file %s: %s" % (varFile, str (e))

# Open and process Source File
try:
	with open (txtFile, 'r') as src:
		for line in src:
			new_line = replace_all (line, myDict)
			# Strip the last line character (CR), otherwise it is two CRs
			print new_line [0 : len (new_line) - 1]
except Exception as e:
    print "Can't open file %s: %s" % (txtFile, str (e))