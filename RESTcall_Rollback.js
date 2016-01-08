importPackage(java.util);
importPackage(java.lang);
importPackage(java.io);
importPackage(com.cloupia.lib.util);
importPackage(com.cloupia.model.cIM);
importPackage(com.cloupia.service.cIM.inframgr);
importPackage(org.apache.commons.httpclient);
importPackage(org.apache.commons.httpclient.cookie);
importPackage(org.apache.commons.httpclient.methods);
importPackage(org.apache.commons.httpclient.auth);
 
///////////////////////////////////////////////////////////////////////////////
//
//		Author: 	Russ Whitear (rwhitear@cisco.com)
//				
//		Modified:	16.07.14 - Added rollback functionality.
//
///////////////////////////////////////////////////////////////////////////////


//
// Workflow Inputs.
// 
var username = input.apicLogin;
var password = input.apicPassword;
var apicIP = input.apicIP;

var tenantName = input.tenantName;

//
// Static Bodytext Data.
//
var loginData = "<aaaUser name=\"" +username+ "\" pwd=\"" +password+ "\" />";
var logoutData = "<aaaUser name=\"" +username+ "\"  />";

//
// Static URIs.
//
var loginUri      = "/api/mo/aaaLogin.xml";
var logoutUri      = "/api/aaaLogout.xml";

//
// Primary Task URI.
//
var primaryTaskUri = "/api/node/mo/uni/tn-" +tenantName+ ".xml";
 
//
// Primary Task Bodytext Data.
// 
// This is the XML bodytext required by APIC in order to progress. Any variable entries
// need to be substituted with either static or externally entered values.
//
var primaryTaskData = " \
<fvTenant name='" +tenantName+ "' status='created,modified'></fvTenant> \
";

//
// Rollback function.
//
function registerUndoTask(apicIP,username,password,tenantName) {
    // register undo task    
    var undoHandler = "custom_UNDO_apic_tenant_bd_and_private_network";
    var undoContext = ctxt.createInnerTaskContext(undoHandler);
    var undoConfig = undoContext.getConfigObject();
	undoConfig.tenantName = tenantName;
	undoConfig.apicIP = apicIP;
	undoConfig.username = username;
	undoConfig.password = password;

    ctxt.getChangeTracker().undoableResourceModified("Rollback tenant ", 
                tenantName,
                "rollback",
                "Rollback tenant "+tenantName,
                 undoHandler,
                 undoConfig);
}


//
// Main code start.
//

// Create an HTTP connection to the APIC.
var httpClient = new HttpClient();
httpClient.getHostConfiguration().setHost(apicIP, 80, "http");
httpClient.getParams().setCookiePolicy("default");

// Login to APIC.
var httpMethod = new PostMethod(loginUri);
httpMethod.setRequestEntity(new StringRequestEntity(loginData));
httpMethod.addRequestHeader("Content-Type", "text/plain;charset=UTF-8");
httpClient.executeMethod(httpMethod);
 
// Check that login is successful. If so, continue. Otherwise, fail task after logging
// the error code and response. 
var statuscode = httpMethod.getStatusCode();

if (statuscode != 200)
{   
    logger.addError("Failed to login to APIC. HTTP response code: "+statuscode);
    logger.addError("Response = "+httpMethod.getResponseBodyAsString());
 
    httpMethod.releaseConnection();
 
     // Set this task as failed.
     ctxt.setFailed("Request failed.");
} else { logger.addInfo("Logged into APIC successfully.") }


// Login was successful. Perform primary task.

httpMethod = new PostMethod(primaryTaskUri); 
httpMethod.setRequestEntity(new StringRequestEntity(primaryTaskData));
httpMethod.addRequestHeader("Content-Type", "text/plain;charset=UTF-8");   
httpClient.executeMethod(httpMethod); 

// Check status code once again and fail task if necessary.
statuscode = httpMethod.getStatusCode();

if (statuscode != 200)
{   
    logger.addError("Failed to configure APIC. HTTP response code: "+statuscode);
    logger.addError("Response = "+httpMethod.getResponseBodyAsString());
 
    httpMethod.releaseConnection();
 
    // Set this task as failed.
    ctxt.setFailed("Request failed.");
} else { logger.addInfo("Successfully configured APIC task.") }


// Logout from APIC.
    
httpMethod = new PostMethod(logoutUri);
httpMethod.setRequestEntity(new StringRequestEntity(logoutData));
httpMethod.addRequestHeader("Content-Type", "text/plain;charset=UTF-8"); 
httpClient.executeMethod(httpMethod);
 
// Check status code once again and fail task if necessary.
statuscode = httpMethod.getStatusCode();

if (statuscode != 200)
{   
    logger.addError("Failed logout from APIC. HTTP response code: "+statuscode);
    logger.addError("Response = "+httpMethod.getResponseBodyAsString());
 
    httpMethod.releaseConnection();
 
     // Set this task as failed.
     ctxt.setFailed("Request failed.");
} else { 
    logger.addInfo("Successfully logged out from APIC.") 
    
    // All done. Release HTTP connection anyway.
    httpMethod.releaseConnection();
}

//
// Set Output Variables.
//
output.TENANT_NAME = tenantName;


//
// Register Undo Task.
//
registerUndoTask(apicIP,username,password,tenantName);

 
 
