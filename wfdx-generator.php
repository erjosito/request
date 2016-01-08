<html>
<header>
<title>UCSD WFDX generator page</title>
<!--
Created by Jose Moreno, josemor@cisco.com, January 2016

This page is used as simple GUI for the capability of automatically generating WFDX files out of JSON/XML payloads.
It has been used in the following config (if you do it in a different way, you might need to tweak something):
* Together with apache2 and php5, on a CentOS machine
* This file has been stored in the root WWW directory /var/www/html
* It stores the results in a subdirectory, /var/www/html/wfdx
* The Python script with the main logic is in /root/request (cloned from github.com/erjosito/request)

You can find the latest version of this code in https://github.com/erjosito/request
-->
</header>
<body>
<font face="verdana"><center>
<img src="apic-dc_hero_banner.jpg">
<br>
<table width='100%' border=0><tr><td width='20%'></td><td width='60%'>
<h1>Automatic generation of UCSD custom tasks for ACI automation</h1>

<p>
This page can be used to automatically generate WFDX files containing custom tasks that can be imported in UCS Director. 
You just need to capture some ACI REST calls (for example with the API Inspector or the Save As function), and paste them in 
the text boxes below.
</p>

<?php
$json = "";
$variables="";
$name="";
if ($_SERVER["REQUEST_METHOD"] == "POST") {
  $json = $_POST["JSON"];
  $rollbackjson = $_POST["rollbackJSON"];
  $variables = $_POST["variables"];
  $taskName = $_POST["taskName"];
  $rollbackName = $_POST["rollbackName"];
  $name = $_POST["fileName"];

  // Create a directory for this task
  $rootdir = "/var/www/html/wfdx";
  $workdir = $rootdir . "/" . $name;
  exec ("/usr/bin/mkdir " . $workdir);
  exec ("cd " . $workdir);

  // Dump the text areas into files
  $commitJsonFile = $workdir . "/" . $name . ".comm.json";
  file_put_contents ($commitJsonFile, $json);
  $rollbackJsonFile = $workdir . "/" . $name . ".roll.json";
  file_put_contents ($rollbackJsonFile, $rollbackjson);
  $varsFile = $workdir . "/" . $name . ".yml";
  file_put_contents ($varsfile, $variables);

  // Do the magic (actually, invoke a Python script that does the magic)
  $outputFile = $workdir . "/" . $name . ".wfdx";
  if (strlen ($rollbackName) > 0) {
      exec ("/usr/bin/python /root/request/genWFDX.py  -d " . $commitJsonFile . " -v " . $varsFile . " -n " . $taskName . " -r " . $rollbackJsonFile . " -q " . $rollbackName . " >" . $outputFile);
  } else {
      exec ("/usr/bin/python /root/request/genWFDX.py  -d " . $commitJsonFile . " -v " . $varsFile . " -n " . $taskName . " >" . $outputFile);
  }
}
?>

<?php
if ($_SERVER["REQUEST_METHOD"] == "POST") {
    if (file_exists ($outputFile)) {
        $target = 'wfdx/' . $name . '/' . $name . '.wfdx';
        echo '<p><b>This is the link to your generated file: <a href="' . $target . '">wfdx file</a></b>. Right-click on the link, save the WFDX file in your computer, and import it into UCS Director<p>';
    }
}
?>

<form method='post' action="<?php echo htmlspecialchars($_SERVER["PHP_SELF"]); ?>">
  <p>Please paste here some XML or JSON code to be sent to APIC over a POST REST call:<br>
  <textarea name='JSON' id='JSON' cols='80' rows='10'><?php echo $json; ?></textarea><br>
  <br>
  <p><b>Optionally</b> paste here some XML or JSON code for rollback:<br>
  <textarea name='rollbackJSON' id='rollbackJSON' cols='80' rows='10'><?php echo $rollbackjson; ?></textarea><br>
  <br>
  <p>Please write here the strings to be translated to variables, for example, "myTenantName: tenantName" (one variable per line):<br>
  <textarea name='variables' id='variables' cols='80' rows='5'><?php echo $variables; ?></textarea><br>
  <br>
  Enter here a descriptive name for the custom task (like createTenant):
  <input type='text' name='taskName' id='taskName' value='<?php echo $taskName; ?>'><br>
  <br>
  If you entered rollback code, enter here a descriptive name for the rollback task (like deleteTenant):
  <input type='text' name='rollbackName' id='rollbackName' value='<?php echo $rollbackName; ?>'><br>
  <br>
  And lastly, a name for the generated file (it is recommended to prefix it with your CEC user ID):
  <input type='text' name='fileName' id='fileName' value='<?php echo $name; ?>'><br>
  <br>
  <input type="submit" value="Submit">
</form>

<br>
<br>
<br>
<h3>Examples of the required inputs above</h3>
<p>JSON code:</p>
<p>
<font face='courier'>
    {
      "fvTenant": {
        "attributes": {
          "descr": "", 
          "dn": "uni/tn-HelloWorld", 
          "name": "HelloWorld", 
          "ownerKey": "", 
          "ownerTag": ""
        }, 
        "children": [
          {
            "fvRsTenantMonPol": {
              "attributes": {
                "tnMonEPGPolName": ""
              }
            }
          }
        ]
      }
    }
</font>
</p>
<br>

<p>Optional rollback JSON code:</p>
<p>
<font face='courier'>
{"fvTenant":
  {"attributes":
    {"dn":"uni/tn-HelloWorld",
     "status":"deleted"
    },"children":[]
  }
}</font>
</p>
<br>

<p>Variables:</p>
<p><font face='courier'>
HelloWorld: tenantName
</font></p>

</td><td width='20%'></td></tr></table>
</center></font>
</body>
</html>

