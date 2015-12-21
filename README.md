request - parametrized serialized REST client

Author: Jose Moreno
Version: 0.1

<h1>Why?</h1>

Because I have lots of JSON code for ACI that is hard to reuse, due to the embedded names in them. If you have the complete configuration of a tenant, and want to reuse it for another different tenant, first you have to run tons of search & replace.

<h1>What?</h1>

request is essentially two utilities:
- request.py: it takes a YAML config file where the following is documented:
  * A list of files in JSON or XML format, and the URLs where they are to be posted
  * A list of variables inside of those files, and the values with which the variables should be replaced when posting

- textreplace.py: a helper utility, that substitutes concrete values out of a text file (generated with the API inspector or the Save As button) with variables (with the syntax {{variable_name}}). The resulting parametrized text files can be used as input for request.py. textreplace.py will take the replacements from a very simple YAML replace key file. The goal is to be able to work on complex replacement patterns (for example for long configs) just by modifying this file.

The bulk of improvements of this project focus on request.py. I have to admit I did not create request.py, but received it from colleagues. Kudos to the original author, whoever that might be. I have added the following capabilities to request.py:

v0.1:
- Argparse used for argument reading, so that options can be specified easier
- The option to read a "variables" section out of the yaml file, and replace in each JSON/XML file the variable by its value (option --testVariables)
- The option to parse the JSON/XML for variables, compare them to the variables defined in the YAML file, and report any missing variable that has not been defined in the YAML file
- The option to run with more or less output (option --verbose)

You can find a number of examples in this repository too, including the original file that I got from the API Inspector or the Save As button, and the replace keys I used to generate the parametrized JSON file


