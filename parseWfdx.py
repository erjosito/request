#!/usr/bin/python

import glob
import json
import os
import os.path
import requests
import sys
import time
import xml.dom.minidom
import argparse
import re
import base64

def getText(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)

def getData(nodelist):
    rc = []
    for node in nodelist:
		rc.append(node.data)
    return ''.join(rc)


if __name__ == "__main__":
	
	# Find arguments and flags
	try:
		parser = argparse.ArgumentParser (description = 'Process .wfdx files exported from UCS Director')
		parser.add_argument('wfdxFile',
						   help='the wfdx file to be parsed')
		parser.add_argument('--verbose', action="store_true",
						   help='if additional output should be shown')
		parser.add_argument('--copy', action="store_true",
						   help='if additional output should be shown')
		args = parser.parse_args()
		wfdxFile = args.wfdxFile
		debug = args.verbose
		copy = args.copy
	except Exception as e:
		parser.print_help ()
		sys.exit (0)
		
	# Part I: parsing an existing WFDX file

	# Load information from WFDX file
	try:
		with open (wfdxFile, 'r' ) as input:
			wfdx = input.read()
	except Exception as e:
		print "ERROR: Could not find file %s" % wfdxFile
		sys.exit (0)
	if debug:
		print " ------------- ORIGINAL FILE -----------------"
		print wfdx
		print " ---------------------------------------------"
		
	# Analyze first layer (XML)
	wfdxXML = xml.dom.minidom.parseString (wfdx)
	if debug:
		print " --------------- ANALYSIS --------------------"
		print "Time:      %s" % getText(wfdxXML.getElementsByTagName("Time")[0].childNodes)
		print "Type:      %s" % getText(wfdxXML.getElementsByTagName("type")[0].childNodes)
	
	# Go for the 2nd layer (JSON)
	wfdxJSON = json.loads (getData (wfdxXML.getElementsByTagName("data")[0].childNodes))
	if debug:
		print "Name:      %s" % wfdxJSON['taskName']
	taskDetails = wfdxJSON ['taskDetails']
	# Escape line breaks and carriage returns
	taskDetails = taskDetails.replace (chr (10), chr (92) + "n")
	taskDetails = taskDetails.replace (chr (13), chr (92) + "r")
	if debug:
		print "Details:   %s" % taskDetails
	
	# And finally, the 3rd one (JSON inside of Base 64)
	wfdxBase64 = wfdxJSON ['taskData']
	wfdxData = base64.b64decode (wfdxBase64)
	wfdxDataJSON = json.loads (wfdxData)
	if debug:
		print "Tree:      %s" % wfdxDataJSON ['registerUnderTree']
		print " ---------------------------------------------"
		
	# Part II: reconstruct a WFDX file
	
	featureAssetEntryData = '![CDATA[{"taskName":"Test","taskLabel":"Test","isActive":true,"taskSummary":"","taskDescription":"","taskDetails":"{{taskDetails}}","taskData":"{{taskData}}"}]]'
	xmlTemplate = '<?xml version="1.0" ?><OrchExportInfo><Time>Tue Jan 05 12:31:03 UTC 2016</Time><User></User><Comments></Comments><UnifiedFeatureAssetInfo><addiInfo></addiInfo><featureAssetEntry><data><{{JSON}}></data></featureAssetEntry><type>CUSTOM_TASKS</type></UnifiedFeatureAssetInfo><version>3.0</version></OrchExportInfo>'
	if copy:
		wfdx = ""
		taskData = base64.b64encode (wfdxData)
		taskJson = featureAssetEntryData.replace ("{{taskData}}", taskData)
		taskJson = taskJson.replace ("{{taskDetails}}", "my task Details")
		taskXml = xmlTemplate.replace ("{{JSON}}", taskJson)
		if debug:
			print " --------------- NEW FILE --------------------"
		print taskXml
		if debug:
			print " ---------------------------------------------"
