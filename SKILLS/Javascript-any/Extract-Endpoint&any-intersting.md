---
name: js-intelligence-mining
description: |
  Use ONLY when the user explicitly requests deep security analysis of JavaScript
  files from an authorized target domain. Performs methodical manual JS source
  analysis — hardcoded secrets, undocumented API endpoints, postMessage handlers,
  DOM XSS sources/sinks, hidden parameters, client-side access control, sensitive
  storage, and source map exposure. Includes controlled endpoint testing.
  Not an automated scanner — reads every file completely and traces data flows.
  Trigger on "analyze JS," "JavaScript audit," "JS recon," "JavaScript intelligence mining,"
  or when asked to perform security review of JavaScript files for a target.
---

# JavaScript Intelligence Mining

## Purpose

Deep, methodical security analysis of JavaScript files from an explicitly
authorized target. Read every file completely, understand its logic, connect
related functions and variables, identify hidden application behavior, extract
endpoints and parameters, and report security-relevant findings with supporting
evidence. Use reasoning to analyze source — do not rely on automated scanners
or third-party tools.

## Safety and Authorization

- Only analyze domains, applications, files, endpoints, and accounts
  explicitly authorized by the user.
- All testing is non-destructive, limited to user-owned or test accounts.
- Prefer GET, HEAD, OPTIONS, or requests with clearly invalid test identifiers.
- Do not perform state-changing requests unless explicitly authorized and only
  against designated test data.
- **Never print complete tokens, cookies, API secrets, private keys, or
  passwords.** Redact with enough characters for identification
  (e.g. `AIzaSyD...xP9`, `eyJhbG...redacted`).
- Do not follow or test third-party URLs outside the authorized scope.
- Use only `curl.exe`, PowerShell built-ins, and .NET classes.
- Do not use automated scanners, fuzzing frameworks, secret-scanning tools,
  or browser automation.

## Required Workspace Structure

Create this tree before starting:

```
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

---

## Phase 1 — Receive and Validate the Target

Before any analysis, collect from the user:

- Authorized base URL
- Allowed domains and subdomains
- Excluded paths
- Available test accounts
- Authentication material (session cookie, token, etc.)
- Whether harmless authenticated endpoint testing is permitted

Normalize the base URL. Confirm every requested URL belongs to the authorized
domain before requesting it. Third-party API URLs may be recorded as
intelligence but never tested unless explicitly in scope.

---

## Phase 2 — Download JavaScript Files

Download every supplied JavaScript URL using `curl.exe`:

```powershell
curl.exe -sS -k -L `
  --connect-timeout 10 `
  --max-time 60 `
  -A "Mozilla/5.0" `
  -D ".\requests\headers.txt" `
  -o ".\downloads\original\001-bundle.js" `
  "https://authorized.example/static/js/bundle.js"
```

For each download, record:

| Field | How to obtain |
|---|---|
| Original URL | From input list |
| Final URL after redirects | From response headers dump |
| Local filename | Assigned sequential name |
| HTTP status | From response headers dump |
| Content-Type | From response headers dump |
| Content-Length | From response headers dump |
| SHA-256 hash | `Get-FileHash -Algorithm SHA256` |
| Download timestamp | Current time |

Verify the response is actually JavaScript — not an HTML error page, JSON
response, access-denied page, redirect, or empty body — before proceeding.

---

## Phase 3 — Read Every File Completely

Every JavaScript file must be read **in full**. Do not analyze only the first
lines or grep matches.

For files with many lines:
```powershell
$lines = Get-Content ".\downloads\original\bundle.js"
$lines.Count
$lines | Select-Object -First 500
$lines | Select-Object -Skip 500 -First 500
```

For minified single-line files, read in character chunks without modifying the
original:
```powershell
$content = [System.IO.File]::ReadAllText(".\downloads\original\bundle.min.js")
$chunkSize = 12000
for ($offset = 0; $offset -lt $content.Length; $offset += $chunkSize) {
    $length = [Math]::Min($chunkSize, $content.Length - $offset)
    "`n===== OFFSET $offset =====`n"
    $content.Substring($offset, $length)
}
```

The original file is the source of truth. A reformatted working copy is a
reading aid only.

---

## Phase 4 — Build a Mental Model

Before reporting isolated strings, understand the application's structure.
For each file determine:

```
File role            Framework/library        Application module
Initialization flow  Routing logic             Authentication logic
API client logic     Storage usage             State management
Permission checks    Feature-flag checks       Error handling
Message handlers     DOM rendering             Data transformations
Request builders
```

Track relationships:
```
Variable declaration → function argument → request body
URL parameter → application state → DOM rendering
Storage value → authorization header → endpoint
Feature flag → hidden component → privileged API route
Message event → state update → navigation or sensitive action
```

A security finding requires context, attacker influence, missing protection,
and meaningful impact — not just the presence of a dangerous function.

---

## Phase 5 — Eight Security Analysis Categories

### Category 1: Hardcoded Secrets and Credentials

Search for and manually evaluate:

- API keys, Bearer tokens, JWTs, access/refresh tokens, passwords, private keys
- Client secrets, encryption keys, signing keys
- Cloud credentials (AWS, GCP, Firebase), service credentials, webhook secrets
- Database URLs containing credentials

Review suspicious prefixes: `sk-`, `pk_`, `AKIA`, `ASIA`, `AIza`, `SG.`,
`ghp_`, `github_pat_`, `xox`, `Bearer`, `eyJ`, `-----BEGIN PRIVATE KEY-----`

Review variable names: `apiKey`, `secretKey`, `accessToken`, `authToken`,
`refreshToken`, `password`, `passwd`, `clientSecret`, `privateKey`,
`appSecret`, `encryptionKey`, `signingKey`, `credentials`, `authorization`

Distinguish real secrets from public identifiers, publishable keys,
placeholders, examples, test fixtures, telemetry IDs, and false positives.

For Base64 values, decode locally only for inspection:
```powershell
try {
    $bytes = [System.Convert]::FromBase64String($value)
    [System.Text.Encoding]::UTF8.GetString($bytes)
} catch { "Not valid standard Base64." }
```

Secret validation must be safe, read-only, and explicitly allowed. Never send
email/SMS, create cloud resources, modify repos, download private data, or
access third-party tenants.

### Category 2: Undocumented Endpoints and API Routes

Identify absolute URLs, relative URLs, API routes, versioned paths, GraphQL
endpoints, internal/admin/upload/export routes, WebSocket URLs, dev/staging/beta
hosts, and internal service names.

Inspect request mechanisms: `fetch()`, `axios()`, `XMLHttpRequest`, `WebSocket`,
`EventSource`, `navigator.sendBeacon()`, `$.ajax()`, `request()`, GraphQL
clients, and custom API wrappers.

**Reconstruct endpoints assembled from fragments:**
```javascript
const base = "/api/v2";
const resource = "/users/";
fetch(base + resource + userId);
// Record as: /api/v2/users/{userId}
```

For each endpoint record: source file, HTTP method, base URL, normalized path,
dynamic path variables, query parameters, headers, auth requirements, request
body, calling function, UI feature, expected response, and privilege context.

Test only authorized endpoints with non-destructive requests (GET, HEAD,
OPTIONS). When auth is supplied, keep tokens in local variables:
```powershell
$sessionCookie = $env:AUTHORIZED_SESSION_COOKIE
curl.exe -sS -k -i -H "Cookie: $sessionCookie" "https://authorized.example/api/v1/profile"
```

Classify each: reachable, requires auth, unauthorized, forbidden, not found,
method not allowed, redirected, protected, potentially exposed, needs
verification. A `200 OK` alone does not prove a vulnerability.

### Category 3: postMessage Origin Validation

Read every handler related to `addEventListener("message", ...)`,
`window.onmessage`, `self.onmessage`, `MessageChannel`, `BroadcastChannel`.

For each handler identify: receiver, expected sender, `event.origin`
validation, `event.source` validation, message schema, accepted actions/commands,
sensitive data processed, DOM operations, navigation, auth actions, storage
changes, API requests, and response postMessages.

Flag handlers with **no origin validation**.

Evaluate weak validation:
- `event.origin.includes("target.com")`
- `event.origin.endsWith("target.com")` — note `eviltarget.com` bypass
- `event.origin.indexOf("target.com") !== -1`
- `event.origin.match(/target.com/)`

A safer pattern: `event.origin === "https://target.com"` or
`allowedOrigins.has(event.origin)`.

For each suspicious handler document: code, origin check, source check,
message structure, required action name, data used, resulting operation,
attacker requirements, potential impact, and whether exploitability is
confirmed or unconfirmed.

### Category 4: DOM XSS Sources and Sinks

**Sources:** `location.href`, `location.search`, `location.hash`,
`location.pathname`, `document.referrer`, `document.URL`, `window.name`,
`URLSearchParams`, `decodeURIComponent()`, postMessage event data,
`localStorage`, `sessionStorage`, cookies, API responses, WebSocket messages.

**Sinks:** `innerHTML`, `outerHTML`, `insertAdjacentHTML()`,
`document.write()`, `document.writeln()`, `eval()`, `Function()`,
`setTimeout/setInterval` with string, `$.html()`, `srcdoc`, `script.src`,
`iframe.src`, `element.src/href`, `location` assignment.

Do not report a finding just because a source and sink co-exist. Trace the
actual data flow: source → parsing → variable assignment → function calls →
transformations → sanitization → sink.

Document: exact source, intermediate variables, transformations, sanitization,
exact sink, execution context, required user interaction, and whether
reflected/stored/DOM-based.

Consider the context (HTML, attribute, JavaScript, URL, CSS, text-only).
Safe APIs like `textContent` are not injection sinks.

**`curl.exe` cannot prove browser-side JS execution.** Clearly distinguish:
source-to-sink path identified, payload reflected in server response, payload
reaches DOM sink, browser execution confirmed vs. not confirmed.

For reflection testing use a unique marker, not a script payload:
```powershell
$marker = "JSINTEL-TEST-48271"
curl.exe -sS -k -i "https://authorized.example/page?value=$marker"
```

### Category 5: Hidden Parameters and Fields

Inspect `FormData()`, `URLSearchParams()`, `JSON.stringify()`, fetch/axios
request bodies, GraphQL variables, multipart forms, query-string builders,
custom serialization helpers.

Extract every field sent by the frontend, paying special attention to:
`user_id`, `userId`, `account_id`, `accountId`, `org_id`, `tenant_id`, `role`,
`roles`, `permission`, `permissions`, `is_admin`, `isAdmin`, `admin`,
`plan`, `tier`, `scope`, `scopes`, `verified`, `isVerified`, `status`,
`owner`, `ownerId`, `feature_flag`, `featureFlag`, `internal_flag`,
`internal`, `debug`, `price`, `amount`, `credits`, `limit`, `quota`.

For each record: field name, request method, endpoint, data type, default
value, source of value, whether visible in UI, whether derived from storage,
whether user-controlled, whether security-sensitive.

Trace values loaded from `localStorage`, `sessionStorage`, cookies, URL
parameters, global variables, React/Redux state, Vue stores, bootstrap data.

For parameter testing use controlled comparison with the user's test records
only. Examples of harmless mutations: `true→false`, `viewer→owner`,
`free→pro`, known test object ID → another test object ID owned by same user.
Document baseline request, modified field, baseline response, modified
response, and whether the server ignored/accepted/validated.

### Category 6: Client-Side Access Control

Look for: `if (user.role === "admin")`, `if (permissions.includes(...))`,
`if (isOwner)`, `if (featureFlags.adminPanel)`, `if (plan === "enterprise")`.

Inspect hidden menu items, conditional routes, disabled buttons, CSS-hidden
elements, admin components, owner-only operations, plan-restricted features,
feature flags, permission arrays, role maps, route guards, redirect logic.

Find and record endpoints called inside restricted code paths. For each:
frontend condition, required role/flag, hidden component, associated endpoint,
HTTP method, request body, and whether server-side authorization was tested.

Test only with an authorized lower-privileged test account. Compare
owner/admin vs. viewer/normal. Do not conclude UI-only restriction is
vulnerable unless the lower-privileged account can perform the restricted
server-side operation.

Classify: client+server enforce access, UI-only restriction, unauthorized data
disclosure, unauthorized action, feature-limit bypass, needs further
verification.

### Category 7: Sensitive Data in Client-Side Storage

Search for `localStorage.setItem/getItem`, `sessionStorage.setItem/getItem`,
`document.cookie`, `indexedDB`, Cache API.

Identify storage of: access/refresh tokens, JWTs, session identifiers, user
IDs, emails, phone numbers, roles, permissions, tenant/org IDs, feature flags,
PII, authentication state.

Document: storage mechanism, key name, value type, where value originates,
where value is used, expiration behavior, logout cleanup, security relevance.

Cookies set by JavaScript cannot be `HttpOnly` — ensure you distinguish these
from server-set cookies. Sensitive data in localStorage may increase XSS
impact but is not always an independent vulnerability. Explain the real risk
and required attacker capability.

### Category 8: Source Map Exposure

Inspect the end of every JS file for `//# sourceMappingURL=` or
`/*@ sourceMappingURL= */`. Resolve relative source-map URLs correctly:

```
JavaScript:  https://authorized.example/static/js/main.123.js
Directive:   main.123.js.map
Resolved:    https://authorized.example/static/js/main.123.js.map
```

Test with:
```powershell
curl.exe -sS -k -L -i `
  -o ".\downloads\sourcemaps\main.123.js.map" `
  "https://authorized.example/static/js/main.123.js.map"
```

Verify: HTTP status, Content-Type, valid JSON, `sources`, `sourcesContent`,
`names`, `sourceRoot`, webpack paths, original filenames, comments, internal
endpoints, developer notes, potential secrets.

Parse:
```powershell
$map = Get-Content ".\downloads\sourcemaps\main.123.js.map" -Raw | ConvertFrom-Json
$map.sources
$map.sourceRoot
$map.sourcesContent.Count
```

If `sourcesContent` is present, analyze every embedded source file using the
same eight categories. A publicly accessible source map is not automatically a
vulnerability — report impact based on sensitive content actually exposed.

---

## Phase 6 — Endpoint and Route Normalization

Deduplicate while preserving evidence. Normalize `/api/users/123` and
`/api/users/456` into `/api/users/{id}`. Do not merge routes that may have
different meanings.

Store each endpoint as JSON:
```json
{
  "method": "GET",
  "base_url": "https://authorized.example",
  "path": "/api/v2/users/{userId}",
  "parameters": ["includePermissions"],
  "source_files": ["bundle.js"],
  "authentication": "Bearer token",
  "privilege_context": "admin component",
  "tested": true,
  "result": "403 for viewer account"
}
```

---

## Phase 7 — Controlled Adaptive Exploration

Follow newly discovered authorized routes to a maximum depth of 4:

- **Depth 0:** Original JS files and pages
- **Depth 1:** Endpoints/scripts directly referenced by depth 0
- **Depth 2:** New routes/scripts from depth 1
- **Depth 3:** New routes/scripts from depth 2
- **Depth 4:** New routes/scripts from depth 3

Go deeper only if the path is clearly in scope, supports a security
hypothesis, testing is non-destructive, and no stricter depth is specified.
Record each new path with its parent source. Do not recursively crawl the
entire domain.

---

## Phase 8 — Request Variations and Error Analysis

When endpoints behave unexpectedly, reason from: HTTP status, response body,
response headers, redirect target, Content-Type, response length, timing
differences, allowed methods, auth state, role differences, error messages,
validation messages.

Use limited variations: GET vs HEAD, GET vs OPTIONS, with/without optional
parameter, valid vs invalid test ID, authenticated vs unauthenticated, owner
vs viewer account, expected vs omitted Content-Type.

Do not fuzz indiscriminately. Retry up to 3 times for transient failures:
```powershell
for ($attempt = 1; $attempt -le 3; $attempt++) {
    curl.exe -sS -k -i --connect-timeout 10 --max-time 30 "https://authorized.example/api/example"
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
}
```
Respect `429 Too Many Requests` and `Retry-After`.

---

## Phase 9 — Evidence Requirements

Every finding must include: title, category, severity estimate, confidence,
affected JavaScript file, relevant function/code, endpoint, method,
parameters, authentication context, observed response, security impact,
validation status, limitations, and recommended remediation.

### Confidence levels
`Confirmed`, `High confidence`, `Medium confidence`, `Low confidence`,
`Informational`, `False positive`

### Validation statuses
`Code review only`, `Endpoint reachable`, `Behavior observed`,
`Authorization difference confirmed`, `Impact confirmed`,
`Browser validation required`, `Not tested due to safety or scope`

---

## Phase 10 — Findings Report Format

### Executive Summary

Number of JS files analyzed, total size, source maps discovered, endpoints
extracted/tested, hidden parameters, potential secrets, confirmed findings,
items requiring browser validation, items not tested due to scope/safety.

### Per-File Analysis Template

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

Then list results for all 8 categories (including "No finding" where
appropriate).

### Finding Template

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

### Endpoint Table
```
| Method | Endpoint | Parameters | Auth | Privilege Context | Tested | Result |
```

### Parameter Table
```
| Parameter | Endpoint | Source | Type | Hidden in UI | Security-Sensitive | Test Result |
```

### Secret Table (never include full values)
```
| Type | Redacted Value | File | Context | Validation | Risk |
```

---

## Required Behavior

**You must:**
1. Read every file completely.
2. Understand the code's purpose before classifying findings.
3. Reconstruct dynamically assembled URLs and request bodies.
4. Correlate related logic across multiple files.
5. Separate evidence from assumptions, exposure from exploitability,
   client-side behavior from server-side authorization.
6. Test only authorized endpoints with non-destructive requests.
7. Redact credentials and sensitive data.
8. Record every request and result.
9. Clearly state what could not be validated.

**You must not:**
1. Produce findings based only on keyword matches.
2. Claim XSS merely because `innerHTML` exists.
3. Claim authorization bypass merely because an admin endpoint exists.
4. Claim a secret is valid without safe evidence.
5. Claim curl proves browser-side JavaScript execution.
6. Follow third-party URLs outside the authorized scope.
7. Use real user identifiers for IDOR testing.
8. Perform destructive or state-changing testing without permission.
9. Expose complete tokens, cookies, passwords, or private keys.
10. Hide uncertainties or invent results.

---

## Quick-Start PowerShell Workflow

Create directories:
```powershell
$Root = ".\js-intelligence"
foreach ($Dir in @("$Root\input", "$Root\downloads\original",
    "$Root\downloads\sourcemaps", "$Root\analysis\file-notes",
    "$Root\requests\response-bodies", "$Root\reports")) {
    New-Item -ItemType Directory -Path $Dir -Force | Out-Null
}
```

Download JS files:
```powershell
$JsUrls = Get-Content "$Root\input\js-urls.txt" |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith("#") }
$Index = 1
foreach ($Url in $JsUrls) {
    $Uri = [System.Uri]$Url
    $OriginalName = [System.IO.Path]::GetFileName($Uri.AbsolutePath)
    if ([string]::IsNullOrWhiteSpace($OriginalName)) { $OriginalName = "script.js" }
    $SafeName = "{0:D3}-{1}" -f $Index, $OriginalName
    $OutputPath = Join-Path "$Root\downloads\original" $SafeName
    curl.exe -sS -k -L --connect-timeout 10 --max-time 60 -A "Mozilla/5.0" -o $OutputPath $Url
    if ($LASTEXITCODE -eq 0 -and (Test-Path $OutputPath)) {
        Get-FileHash $OutputPath -Algorithm SHA256
    }
    $Index++
}
```

Navigation helper (use matches to locate relevant sections, then read
surrounding context from the complete file):
```powershell
$Patterns = @(
    "sourceMappingURL", "addEventListener\s*\(\s*['""]message", "onmessage",
    "innerHTML", "outerHTML", "insertAdjacentHTML", "document\.write",
    "eval\s*\(", "localStorage", "sessionStorage", "FormData",
    "URLSearchParams", "fetch\s*\(", "axios", "XMLHttpRequest",
    "WebSocket", "/api/", "/internal/", "/admin/", "/graphql"
)
Get-ChildItem "$Root\downloads\original" -File |
    Select-String -Pattern $Patterns -AllMatches
```

---

# Final Instruction

Approach every JavaScript file as application intelligence, not as a collection
of regex matches. Read the full source. Understand what each module does.
Determine how data enters, is transformed, stored, and sent. Find behavior the
developer did not intend to expose — while keeping all testing authorized,
controlled, evidence-based, and non-destructive.
