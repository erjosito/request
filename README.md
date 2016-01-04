request - parametrized serialized REST client

Author: Jose Moreno
Version: 0.1

<h1>Why?</h1>

Because I have lots of JSON code for ACI that is hard to reuse, due to the embedded names in them. 
If you have the complete configuration of a tenant, and want to reuse it for another different tenant, 
first you have to run tons of search & replace.

The idea of this project is improving request.py (which was originally able to chain
multiple REST requests) so that it can resolve parameters, that way parametrised REST
requests are easier to reuse.

<h1>What?</h1>

request is essentially two utilities:
- request.py: it takes a YAML config file where the following is documented:
  * A list of files in JSON or XML format, and the URLs where they are to be posted
  * A list of variables inside of those files, and the values with which the variables should be replaced when posting

- textreplace.py: a helper utility, that substitutes concrete values out of a text file (generated with the API inspector 
or the Save As button) with variables (with the syntax {{variable_name}}). The resulting parametrized text files can be used as input for request.py. textreplace.py will take the replacements from a very simple YAML replace key file. The goal is to be able to work on complex replacement patterns (for example for long configs) just by modifying this file.

<h1>How?</h1>
You just need Python 2.7, and a couple of libraries (check the import statements of request.py for the complete list)

You can find a number of examples in this repository too, including in some cases the original file that I got from 
the API Inspector or the Save As button, and the replace keys I used to generate the parametrized JSON file with textreplace.py

<h1>Version control</h1>

The bulk of improvements of this project focus on request.py. I have to admit I did not create request.py, 
but received it from colleagues. Kudos to the original author, whoever that might be.

<h2>v0.1</h2>
Improvements over the original request.py:
- Argparse used for argument reading, so that options and arguments can be specified easier
- request -h for help on command usage (actually a function of argparse)
- The option to read a "variables" section out of the yaml file, and replace in each JSON/XML file the variable by its value (option --testVariables)
- The option to parse the JSON/XML for variables, compare them to the variables defined in the YAML file, and report any missing variable that has not been defined in the YAML file
- The option to run with more or less output (option --verbose)
- One level of variables recursion supported (see the example "tenant_recursive", quotes need to be used)
- URLs can be parametrised too




