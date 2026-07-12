# JavaScript Intelligence Mining

## Purpose

Perform deep, methodical security analysis of JavaScript files belonging only to an explicitly authorized target.

The objective is not merely to search for keywords. You must read every JavaScript file completely, understand its logic, connect related functions and variables, identify hidden application behavior, extract endpoints and parameters, and report security-relevant findings with supporting evidence.

Use your own reasoning to analyze the JavaScript source.

Do not rely on automated vulnerability scanners or random third-party tools.

---

## Authorization and Safety Requirements

Only analyze domains, applications, files, endpoints, and accounts explicitly provided as authorized by the user.

All testing must remain:

* Within the authorized scope.
* Non-destructive.
* Limited to the user's own accounts or supplied test accounts.
* Free from deleting, modifying, corrupting, or exposing real user data.
* Free from accessing other users' records.
* Free from persistence, denial of service, phishing, malware, or destructive actions.

When testing an endpoint, prefer harmless requests such as:

* `GET`
* `HEAD`
* `OPTIONS`
* Requests with clearly invalid test identifiers
* Requests using the user's authorized test session

Do not perform state-changing requests unless the user has explicitly authorized them and the action affects only designated test data.

Never print complete authentication cookies, access tokens, API secrets, private keys, passwords, or personal information in the final report. Redact sensitive values while preserving enough characters for identification.

Example:

```text
AIzaSyD...xP9
eyJhbG...redacted
AKIA...7Q2M
```

---

# Allowed Tools

Use only:

* `curl.exe`
* PowerShell built-in commands and .NET classes
* Standard Windows commands when necessary for file navigation

Examples of permitted PowerShell functionality:

```powershell
Get-ChildItem
Get-Content
Select-String
ForEach-Object
Where-Object
Sort-Object
Group-Object
Measure-Object
ConvertFrom-Json
ConvertTo-Json
Invoke-WebRequest
Resolve-Path
Join-Path
Test-Path
New-Item
Set-Content
Add-Content
[System.IO.File]
[System.Uri]
[System.Text.Encoding]
[System.Convert]
[System.Net.WebUtility]
```

Prefer `curl.exe` for HTTP requests.

Do not use automated scanners, secret-scanning tools, endpoint-extraction tools, browser automation, fuzzing frameworks, or external vulnerability scanners.

Do not use tools such as:

```text
Nuclei
Katana
Gau
Waybackurls
LinkFinder
SecretFinder
Semgrep
TruffleHog
Gitleaks
Burp Scanner
OWASP ZAP Scanner
SQLMap
ffuf
dirsearch
Gobuster
```

Keyword searches may help locate relevant code, but they must never replace complete reading and reasoning.

---

# Required Working Directory Structure

Create an organized workspace:

```text
js-intelligence/
├── input/
│   ├── urls.txt
│   └── js-urls.txt
├── downloads/
│   ├── original/
│   └── sourcemaps/
├── analysis/
│   ├── file-notes/
│   ├── endpoints.json
│   ├── parameters.json
│   ├── secrets-redacted.json
│   ├── postmessage.json
│   ├── dom-xss.json
│   ├── storage.json
│   └── access-control.json
├── requests/
│   ├── request-log.jsonl
│   └── response-bodies/
└── reports/
    ├── summary.md
    └── full-report.md
```

Do not overwrite original downloaded files.

Store response bodies separately from the original JavaScript files.

---

# Phase 1: Receive and Validate the Target

Before analysis, identify:

```text
Authorized base URL
Allowed domains and subdomains
Excluded paths
Available test accounts
Authentication material supplied by the user
Whether harmless authenticated endpoint testing is permitted
```

Normalize the base URL.

Confirm that every requested URL belongs to the authorized domain before requesting it.

Do not follow links to unrelated third-party domains.

Third-party API URLs may be recorded as intelligence, but do not test them unless the user explicitly confirms they are included in the authorized scope.

---

# Phase 2: Download JavaScript Files

Download every supplied JavaScript URL using `curl.exe`.

Example:

```powershell
curl.exe -sS -k -L `
  --connect-timeout 10 `
  --max-time 60 `
  -D ".\requests\headers.txt" `
  -o ".\downloads\original\bundle.js" `
  "https://authorized.example/static/js/bundle.js"
```

Use a normal browser-like User-Agent when needed:

```powershell
curl.exe -sS -k -L `
  -A "Mozilla/5.0" `
  -o ".\downloads\original\bundle.js" `
  "https://authorized.example/static/js/bundle.js"
```

Record for every download:

```text
Original URL
Final URL after redirects
Local filename
HTTP status
Content-Type
Content-Length
SHA-256 hash
Download time
```

Calculate the hash using PowerShell:

```powershell
Get-FileHash ".\downloads\original\bundle.js" -Algorithm SHA256
```

Do not assume a response is JavaScript merely because the URL ends with `.js`.

Check whether it is:

* JavaScript
* HTML error page
* JSON
* Access-denied page
* Redirect response
* Empty response

---

# Phase 3: Read Every File Completely

Every JavaScript file must be read in full.

Do not analyze only the first lines, matching lines, or extracted strings.

For large files:

1. Record the total file size and line count.
2. Read it in sequential sections.
3. Maintain notes for each section.
4. Track variables and functions across section boundaries.
5. Revisit earlier code when later code reveals its purpose.

Example:

```powershell
$lines = Get-Content ".\downloads\original\bundle.js"
$lines.Count
$lines | Select-Object -First 500
$lines | Select-Object -Skip 500 -First 500
```

For a minified file stored as one extremely long line, read it in character chunks without modifying the original:

```powershell
$content = [System.IO.File]::ReadAllText(
    ".\downloads\original\bundle.min.js"
)

$chunkSize = 12000

for ($offset = 0; $offset -lt $content.Length; $offset += $chunkSize) {
    $length = [Math]::Min($chunkSize, $content.Length - $offset)

    "`n===== OFFSET $offset =====`n"

    $content.Substring($offset, $length)
}
```

You may create a separate readable working copy using basic PowerShell string formatting, but never treat imperfect formatting as equivalent to parsing.

The original source remains the source of truth.

---

# Phase 4: Build a Mental Model of the Application

Before reporting isolated strings, understand the application's structure.

For each file, determine:

```text
File role
Framework or library
Application module
Initialization flow
Routing logic
Authentication logic
API client logic
Storage usage
State management
Permission checks
Feature-flag checks
Error handling
Message-event handlers
DOM rendering logic
Data transformations
Request-building helpers
```

Track relationships such as:

```text
Variable declaration → function argument → request body
URL parameter → application state → DOM rendering
Storage value → authorization header → endpoint
Feature flag → hidden component → privileged API route
Message event → state update → navigation or sensitive action
```

Do not classify something as vulnerable solely because a dangerous function exists.

A security finding requires relevant context, attacker influence, missing protection, and meaningful impact.

---

# Phase 5: Security Analysis Categories

## Category 1: Hardcoded Secrets and Credentials

Search for and manually evaluate:

```text
API keys
Bearer tokens
JWT values
Access tokens
Refresh tokens
Passwords
Private keys
Client secrets
Application secrets
Encryption keys
Signing keys
Cloud credentials
Service credentials
Webhook secrets
Database URLs containing credentials
```

Review suspicious prefixes and patterns such as:

```text
sk-
pk_
AKIA
ASIA
AIza
SG.
ghp_
github_pat_
xox
Bearer
eyJ
-----BEGIN PRIVATE KEY-----
-----BEGIN RSA PRIVATE KEY-----
```

Review variables with names such as:

```text
apiKey
secretKey
accessToken
authToken
refreshToken
password
passwd
clientSecret
privateKey
appSecret
encryptionKey
signingKey
credentials
authorization
```

Distinguish among:

```text
Real secret
Public client identifier
Publishable key
Placeholder
Example value
Test fixture
Telemetry identifier
False positive
```

For Base64-like values:

1. Decode only locally.
2. Inspect the decoded structure.
3. Do not execute decoded content.
4. Do not expose the complete decoded credential in reports.

PowerShell example:

```powershell
$value = "BASE64_VALUE"

try {
    $bytes = [System.Convert]::FromBase64String($value)
    [System.Text.Encoding]::UTF8.GetString($bytes)
}
catch {
    Write-Output "Value is not valid standard Base64."
}
```

### Secret Validation Rules

Do not automatically attempt to authenticate with every discovered value.

First determine:

* Whether it is clearly public or secret.
* Whether the related service belongs to the authorized scope.
* Whether a safe, read-only validation method exists.
* Whether validation could create cost, modify data, send messages, or access third-party information.

Only perform harmless validation when explicitly allowed.

Prefer metadata or identity endpoints that reveal no sensitive data.

Never:

* Send email or SMS.
* Create cloud resources.
* Modify repositories.
* Download private data.
* Enumerate unrelated accounts.
* Generate financial charges.
* Access third-party tenants.

---

## Category 2: Undocumented Endpoints and API Routes

Identify:

```text
Absolute URLs
Relative URLs
API routes
Versioned API paths
GraphQL endpoints
Internal routes
Admin routes
Upload routes
Export routes
WebSocket URLs
Development hosts
Testing hosts
Staging hosts
Beta hosts
Internal service names
```

Look for strings containing:

```text
/api/
/v1/
/v2/
/v3/
/internal/
/admin/
/graphql
/upload
/export
/debug
/management
/settings
/permissions
ws://
wss://
```

Inspect request mechanisms including:

```text
fetch()
axios()
XMLHttpRequest
WebSocket
EventSource
navigator.sendBeacon()
$.ajax()
request()
graphql clients
custom API wrappers
```

Do not extract only the visible string literal.

Reconstruct endpoints assembled from fragments.

Example:

```javascript
const base = "/api/v2";
const resource = "/users/";
fetch(base + resource + userId);
```

Record it as:

```text
/api/v2/users/{userId}
```

For every endpoint, record:

```text
Source file
Location or character offset
HTTP method
Base URL
Normalized path
Dynamic path variables
Query parameters
Headers
Authentication requirements
Request body
Calling function
UI feature
Expected response
Whether it appears privileged
```

### Endpoint Testing

Test only authorized endpoints.

Begin with non-destructive requests:

```powershell
curl.exe -sS -k -i `
  -A "Mozilla/5.0" `
  "https://authorized.example/api/v1/example"
```

For method discovery:

```powershell
curl.exe -sS -k -i `
  -X OPTIONS `
  "https://authorized.example/api/v1/example"
```

When authentication is supplied by the user, keep it in a local variable rather than duplicating it in command history:

```powershell
$sessionCookie = $env:AUTHORIZED_SESSION_COOKIE

curl.exe -sS -k -i `
  -H "Cookie: $sessionCookie" `
  "https://authorized.example/api/v1/profile"
```

Do not place complete tokens in report files.

Classify each tested endpoint:

```text
Reachable
Requires authentication
Unauthorized
Forbidden
Not found
Method not allowed
Redirected
Protected by client and server
Potentially exposed
Needs manual verification
```

A `200 OK` response alone does not prove a vulnerability.

Inspect whether the response actually contains unauthorized or sensitive information.

---

## Category 3: postMessage Origin Validation

Read every handler related to:

```javascript
addEventListener("message", ...)
window.onmessage
self.onmessage
message event wrappers
MessageChannel
BroadcastChannel
```

For every handler, identify:

```text
The message receiver
Expected sender
event.origin validation
event.source validation
Message schema
Accepted actions or commands
Sensitive data processed
DOM operations
Navigation
Authentication actions
Storage changes
API requests
Responses sent back with postMessage
```

Flag handlers with no origin validation.

Example:

```javascript
window.addEventListener("message", function (event) {
    processData(event.data);
});
```

Evaluate weak validation such as:

```javascript
event.origin.includes("target.com")
event.origin.endsWith("target.com")
event.origin.indexOf("target.com") !== -1
event.origin.match(/target.com/)
```

Do not automatically call every `endsWith()` check vulnerable.

Examine separators and exact hostname parsing.

For example, this may still be unsafe:

```javascript
event.origin.endsWith("target.com")
```

because an attacker-controlled hostname could be:

```text
eviltarget.com
```

A safer pattern usually compares the normalized origin exactly:

```javascript
event.origin === "https://target.com"
```

Or compares against an explicit allowlist:

```javascript
allowedOrigins.has(event.origin)
```

For every suspicious handler, document:

```text
Handler code
Origin check
Source check
Accepted message structure
Required action name
Data used
Resulting operation
Attacker requirements
Potential impact
Reason exploitability is confirmed or unconfirmed
```

Do not build or execute a cross-origin proof of concept against an unauthorized domain.

---

## Category 4: DOM XSS Sources and Sinks

### Sources

Review attacker-controllable input from:

```text
location.href
location.search
location.hash
location.pathname
location.origin
document.referrer
document.URL
document.documentURI
document.baseURI
window.name
URLSearchParams
decodeURIComponent()
postMessage event data
localStorage
sessionStorage
cookies
API responses containing user-controlled data
WebSocket messages
```

### Sinks

Review dangerous output or execution operations:

```text
innerHTML
outerHTML
insertAdjacentHTML()
document.write()
document.writeln()
eval()
Function()
setTimeout() with a string
setInterval() with a string
$.html()
jQuery.html()
srcdoc
script.src
iframe.src
element.src
element.href
location assignment
```

Do not report a source and sink merely because both exist in the same file.

Trace the actual data flow:

```text
Source
→ parsing or decoding
→ variable assignment
→ function calls
→ transformations
→ sanitization or encoding
→ sink
```

Document:

```text
Exact source
Intermediate variables
Transformations
Sanitization
Exact sink
Execution context
Required user interaction
Whether the value is reflected, stored, or DOM-based
```

Consider the context:

```text
HTML context
HTML attribute context
JavaScript context
URL context
CSS context
Text-only context
```

Safe APIs such as `textContent` should not be treated as HTML injection sinks.

### DOM XSS Validation

Do not claim confirmed XSS unless script execution is actually demonstrated in an authorized test environment.

`curl.exe` cannot execute browser-side JavaScript.

Therefore, curl may confirm reflection into HTML or JavaScript responses, but it cannot by itself prove that a browser DOM sink executes.

Clearly distinguish:

```text
Source-to-sink code path identified
Payload reflected in server response
Payload reaches DOM sink
Browser execution confirmed
Browser execution not confirmed
```

For harmless reflection testing, use a unique marker rather than a script payload:

```powershell
$marker = "JSINTEL-TEST-48271"

curl.exe -sS -k -i `
  "https://authorized.example/page?value=$marker"
```

Do not fabricate a curl proof of concept that claims browser execution.

---

## Category 5: Hidden Parameters and Fields

Inspect:

```text
FormData()
URLSearchParams()
JSON.stringify()
fetch request bodies
axios data objects
GraphQL variables
multipart forms
query-string builders
custom serialization helpers
```

Extract every field sent by the frontend.

Pay special attention to:

```text
user_id
userId
account_id
accountId
org_id
organizationId
tenant_id
tenantId
team_id
teamId
role
roles
permission
permissions
is_admin
isAdmin
admin
plan
tier
scope
scopes
verified
isVerified
status
owner
ownerId
feature_flag
featureFlag
internal_flag
internal
debug
price
amount
credits
limit
quota
```

Record:

```text
Field name
Request method
Endpoint
Data type
Default value
Source of value
Whether visible in UI
Whether derived from storage
Whether controlled by the user
Whether security-sensitive
```

Trace values loaded from:

```text
localStorage
sessionStorage
cookies
URL parameters
global variables
React state
Redux state
Vue stores
application bootstrap data
```

### Parameter Testing

Do not blindly inject into every parameter.

For security-sensitive parameters, perform controlled comparison using only the user's test records.

Use a baseline request and one modified request.

Examples of harmless mutations:

```text
true → false
false → true
viewer → owner
free → pro
known test object ID → another test object ID owned by the same user
missing field → supplied field
```

Do not use identifiers belonging to real users.

Document:

```text
Baseline request
Single modified field
Baseline response
Modified response
Server-side effect
Whether the server ignored, accepted, or validated the field
```

A frontend field does not automatically indicate mass assignment.

Mass assignment requires evidence that the server accepts an unauthorized security-sensitive property.

---

## Category 6: Client-Side Access Control

Look for code such as:

```javascript
if (user.role === "admin")
if (permissions.includes("manage_users"))
if (isOwner)
if (featureFlags.adminPanel)
if (plan === "enterprise")
```

Inspect:

```text
Hidden menu items
Conditional routes
Disabled buttons
CSS-hidden elements
Admin components
Owner-only operations
Plan-restricted features
Feature flags
Permission arrays
Role maps
Route guards
Redirect logic
```

Find endpoints called inside restricted code paths.

For each restricted feature, record:

```text
Frontend condition
Required role or flag
Hidden component
Associated endpoint
HTTP method
Request body
Whether server-side authorization was tested
```

Test the endpoint only with an authorized lower-privileged test account.

Compare:

```text
Owner or admin test account
Viewer or normal test account
```

Do not conclude that client-side gating is vulnerable unless the lower-privileged account can perform or access the restricted server-side operation.

Classify results:

```text
Client and server enforce access
UI-only restriction
Unauthorized data disclosure
Unauthorized action
Feature-limit bypass
Needs further verification
```

---

## Category 7: Sensitive Data in Client-Side Storage

Search for:

```javascript
localStorage.setItem()
localStorage.getItem()
sessionStorage.setItem()
sessionStorage.getItem()
document.cookie
indexedDB
Cache API
```

Identify storage of:

```text
Access tokens
Refresh tokens
JWTs
Session identifiers
User IDs
Email addresses
Phone numbers
Roles
Permissions
Tenant IDs
Organization IDs
Feature flags
Personally identifiable information
Authentication state
```

Document:

```text
Storage mechanism
Key name
Value type
Where value originates
Where value is used
Expiration behavior
Logout cleanup
Security relevance
```

Do not claim that a cookie lacks `HttpOnly` solely because JavaScript reads a different cookie with the same name.

Cookies created through JavaScript cannot be `HttpOnly`, but server-set cookies must be inspected through response headers.

Sensitive data in localStorage may increase the impact of XSS, but storage alone is not always an independent vulnerability.

Explain the real risk and required attacker capability.

---

## Category 8: Source Map Exposure

Inspect the end of every JavaScript file for:

```text
//# sourceMappingURL=
/*@ sourceMappingURL= */
sourceMappingURL
```

Resolve relative source-map URLs correctly.

Example:

```text
JavaScript:
https://authorized.example/static/js/main.123.js

Directive:
main.123.js.map

Resolved map:
https://authorized.example/static/js/main.123.js.map
```

Test with:

```powershell
curl.exe -sS -k -L -i `
  -o ".\downloads\sourcemaps\main.123.js.map" `
  "https://authorized.example/static/js/main.123.js.map"
```

Verify:

```text
HTTP status
Content-Type
Whether response is valid JSON
sources
sourcesContent
names
sourceRoot
webpack paths
Original filenames
Comments
Internal endpoints
Developer notes
Potential secrets
```

Parse basic map information:

```powershell
$map = Get-Content `
  ".\downloads\sourcemaps\main.123.js.map" `
  -Raw | ConvertFrom-Json

$map.sources
$map.sourceRoot
$map.sourcesContent.Count
```

If `sourcesContent` is present, analyze every embedded source file using the same eight security categories.

A publicly accessible source map is not automatically a valid security vulnerability.

Report impact based on sensitive content actually exposed.

---

# Phase 6: Endpoint and Route Normalization

Deduplicate endpoints while preserving evidence.

Normalize:

```text
/api/users/123
/api/users/456
```

into:

```text
/api/users/{id}
```

Do not merge routes that may have different meanings.

Store:

```json
{
  "method": "GET",
  "base_url": "https://authorized.example",
  "path": "/api/v2/users/{userId}",
  "parameters": [
    "includePermissions"
  ],
  "source_files": [
    "bundle.js"
  ],
  "authentication": "Bearer token",
  "privilege_context": "admin component",
  "tested": true,
  "result": "403 for viewer account"
}
```

Include both:

* Normalized route
* Concrete test URL with sensitive identifiers redacted

---

# Phase 7: Controlled Adaptive Exploration

Follow newly discovered authorized routes to a maximum depth of four by default.

Depth definition:

```text
Depth 0: Original supplied pages and JavaScript files
Depth 1: Endpoints and scripts directly referenced by depth 0
Depth 2: New routes or scripts discovered from depth 1
Depth 3: New routes or scripts discovered from depth 2
Depth 4: New routes or scripts discovered from depth 3
```

Continue beyond depth four only when:

* The new path remains clearly in scope.
* It directly supports an existing security hypothesis.
* Testing remains non-destructive.
* The user has not specified a stricter depth.

For each new path, record its parent source.

Do not recursively crawl the entire domain.

---

# Phase 8: Request Variations and Error Analysis

When an endpoint behaves unexpectedly, reason from:

```text
HTTP status
Response body
Response headers
Redirect target
Content-Type
Response length
Timing differences
Allowed methods
Authentication state
Role differences
Error messages
Validation messages
```

Use limited variations that test a specific hypothesis.

Permitted examples:

```text
GET versus HEAD
GET versus OPTIONS
With and without a harmless optional parameter
Valid test identifier versus invalid identifier
Authenticated versus unauthenticated
Owner test account versus viewer test account
Expected Content-Type versus omitted Content-Type
```

Do not perform uncontrolled fuzzing.

Do not retry indefinitely.

Use a small retry limit, such as three attempts per meaningful variation.

For transient failures:

```powershell
$maxAttempts = 3

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    curl.exe -sS -k -i `
      --connect-timeout 10 `
      --max-time 30 `
      "https://authorized.example/api/example"

    if ($LASTEXITCODE -eq 0) {
        break
    }

    Start-Sleep -Seconds 2
}
```

Respect `429 Too Many Requests` and `Retry-After`.

Do not attempt to bypass rate limits unless the user explicitly identifies rate-limit testing as authorized and the testing can be performed safely with designated test accounts.

---

# Phase 9: Evidence Requirements

Every finding must contain evidence.

Do not report vague statements such as:

```text
There may be an API vulnerability.
The application appears insecure.
An admin endpoint was found.
```

Include:

```text
Finding title
Category
Severity estimate
Confidence
Affected JavaScript file
Relevant function or code
Endpoint
Method
Parameters
Authentication context
Observed response
Security impact
Validation status
Limitations
Recommended remediation
```

Use the following confidence levels:

```text
Confirmed
High confidence
Medium confidence
Low confidence
Informational
False positive
```

Use the following validation statuses:

```text
Code review only
Endpoint reachable
Behavior observed
Authorization difference confirmed
Impact confirmed
Browser validation required
Not tested due to safety or scope
```

---

# Phase 10: Findings Report Format

## Executive Summary

Include:

```text
Number of JavaScript files analyzed
Total size analyzed
Source maps discovered
Endpoints extracted
Endpoints tested
Hidden parameters extracted
Potential secrets
Confirmed findings
Items requiring browser validation
Items not tested because of scope or safety
```

## Per-File Analysis

For every JavaScript file:

```markdown
## File: main.123.js

- Original URL:
- Local path:
- Size:
- SHA-256:
- Framework:
- Application purpose:
- Fully read: Yes/No
- Source map:
- Important functions:
- Authentication behavior:
- API behavior:
- Storage behavior:
- Permission logic:
```

Then list results for all eight categories, including `No finding` where appropriate.

## Finding Template

```markdown
# [Severity] Finding Title

## Category

## Confidence

## Validation Status

## Affected Component

## Evidence

## Relevant JavaScript Logic

## Endpoint and Method

## Parameters

## Test Conditions

## Observed Behavior

## Security Impact

## Limitations

## Recommended Remediation
```

## Endpoint Table

```markdown
| Method | Endpoint | Parameters | Auth | Privilege Context | Tested | Result |
|---|---|---|---|---|---|---|
```

## Parameter Table

```markdown
| Parameter | Endpoint | Source | Type | Hidden in UI | Security-Sensitive | Test Result |
|---|---|---|---|---|---|---|
```

## Secret Table

Never include complete secret values.

```markdown
| Type | Redacted Value | File | Context | Validation | Risk |
|---|---|---|---|---|---|
```

---

# Required Analysis Behavior

You must:

1. Read every file completely.
2. Understand the purpose of the code before classifying findings.
3. Reconstruct dynamically assembled URLs and request bodies.
4. Correlate related logic across multiple files.
5. Separate evidence from assumptions.
6. Separate exposure from exploitability.
7. Separate client-side behavior from server-side authorization.
8. Test only authorized endpoints.
9. Use non-destructive requests.
10. Redact credentials and sensitive data.
11. Record every request and result.
12. Clearly state what could not be validated.

You must not:

1. Produce findings based only on keyword matches.
2. Claim XSS merely because `innerHTML` exists.
3. Claim authorization bypass merely because an admin endpoint exists.
4. Claim a secret is valid without safe evidence.
5. Claim curl proves browser-side JavaScript execution.
6. Follow third-party URLs outside the authorized scope.
7. Use real user identifiers for IDOR testing.
8. perform destructive or state-changing testing without explicit permission.
9. Expose complete tokens, cookies, passwords, or private keys.
10. hide uncertainties or invent results.

---

# Recommended PowerShell Workflow

```powershell
$Root = ".\js-intelligence"

$Directories = @(
    "$Root\input",
    "$Root\downloads\original",
    "$Root\downloads\sourcemaps",
    "$Root\analysis\file-notes",
    "$Root\requests\response-bodies",
    "$Root\reports"
)

foreach ($Directory in $Directories) {
    New-Item -ItemType Directory `
      -Path $Directory `
      -Force | Out-Null
}
```

Read JavaScript URL list:

```powershell
$JsUrls = Get-Content "$Root\input\js-urls.txt" |
    ForEach-Object { $_.Trim() } |
    Where-Object {
        $_ -and -not $_.StartsWith("#")
    }
```

Download files:

```powershell
$Index = 1

foreach ($Url in $JsUrls) {
    $Uri = [System.Uri]$Url
    $OriginalName = [System.IO.Path]::GetFileName($Uri.AbsolutePath)

    if ([string]::IsNullOrWhiteSpace($OriginalName)) {
        $OriginalName = "script.js"
    }

    $SafeName = "{0:D3}-{1}" -f $Index, $OriginalName
    $OutputPath = Join-Path "$Root\downloads\original" $SafeName

    curl.exe -sS -k -L `
      --connect-timeout 10 `
      --max-time 60 `
      -A "Mozilla/5.0" `
      -o $OutputPath `
      $Url

    if ($LASTEXITCODE -eq 0 -and (Test-Path $OutputPath)) {
        Get-FileHash $OutputPath -Algorithm SHA256
    }

    $Index++
}
```

Use `Select-String` only as a navigation helper:

```powershell
$Patterns = @(
    "sourceMappingURL",
    "addEventListener\s*\(\s*['""]message",
    "onmessage",
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document\.write",
    "eval\s*\(",
    "localStorage",
    "sessionStorage",
    "FormData",
    "URLSearchParams",
    "fetch\s*\(",
    "axios",
    "XMLHttpRequest",
    "WebSocket",
    "/api/",
    "/internal/",
    "/admin/",
    "/graphql"
)

Get-ChildItem "$Root\downloads\original" -File |
    Select-String -Pattern $Patterns -AllMatches
```

After using the matches to locate relevant sections, return to the complete file and trace the surrounding logic.

---

# Final Instruction

Approach every JavaScript file as application intelligence, not as a collection of regex matches.

Read the full source.

Understand what each module is trying to accomplish.

Determine how data enters the application, how it is transformed, where it is stored, where it is sent, and what security assumptions the frontend makes.

Find behavior the developer may not have intended to expose, while keeping all testing authorized, controlled, evidence-based, and non-destructive.
