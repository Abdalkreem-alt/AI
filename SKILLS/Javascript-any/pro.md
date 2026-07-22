---
name: js-intelligence-mining
description: |
  Use ONLY when the user explicitly requests deep security analysis of JavaScript
  files from an authorized target domain. Starts with user-provided JS files,
  recursively discovers all additional JS files (imports, chunks, workers, source
  maps), then performs methodical manual JS source analysis — hardcoded secrets,
  reconstructed API endpoints, postMessage handlers, DOM XSS sources/sinks,
  hidden parameters, client-side access control, sensitive storage, and source
  map exposure. Includes controlled endpoint testing. Every finding records its
  source file. Not an automated scanner — reads every file completely and traces
  data flows.
  Trigger on "analyze JS," "JavaScript audit," "JS recon," "JavaScript intelligence mining,"
  or when asked to perform security review of JavaScript files for a target.
---

# JavaScript Intelligence Mining (v2)

## Core Design Principle

This skill is built on the finding that **context engineering** is the single
highest-impact lever for coding agent performance on long-running analysis tasks
(Anthropic Best Practices, 2025; "Lost in the Middle", Liu et al., TACL 2023).
Every phase below is designed to:

1. **Keep context clean** — isolate exploration, delegate deep dives to subagents,
   aggressively clear memory between unrelated files.
2. **Position critical information at context boundaries** — summaries at the
   top of outputs, findings at the end, so attention is highest where it matters.
3. **Verify before moving on** — each phase has explicit exit criteria. You do
   not advance until the current phase produces a passing check.

---

## Phase 0 — Workspace Setup and Authorization (ENTRY GATE)

**Entry condition**: User has provided at least one authorized target URL.
**Exit condition**: workspace directories exist, authorization confirmed, session
 tokens validated.

### 0.1 Collect Authorization

Before ANY network request, ask the user for ALL of:

| Field | Required? | Purpose |
|-------|-----------|---------|
| Authorized base URL(s) | MANDATORY | Scope boundary |
| Allowed subdomains | MANDATORY | Prevents scope creep |
| Excluded paths | Optional | Avoid known-safe areas |
| Test account credentials | Recommended | For authenticated testing |
| Session cookie / Bearer token | Recommended | For authenticated JS retrieval |
| Endpoint testing permitted? | MANDATORY | Yes/No — gates Phase 6 testing |

**If any mandatory field is missing, STOP and ask. Do not proceed.**

### 0.2 Validate Session

Send one authenticated GET to the base URL. Verify 2xx response. If auth
material is rejected, STOP and report to user.

### 0.3 Create Workspace

```powershell
$MainDomain = "{main-domain}"       # e.g. "att.com"
$Subdomain  = "{subdomain-name}"    # e.g. "admin" or "www"
$Root = ".\js-intelligence\$MainDomain\$Subdomain"

foreach ($Dir in @(
    "$Root\input",
    "$Root\runtime\source-map-notes",
    "$Root\analysis\file-notes",
    "$Root\requests\response-bodies",
    "$Root\reports"
)) {
    New-Item -ItemType Directory -Path $Dir -Force | Out-Null
}
```

### 0.4 Initialize Output Files

Create empty JSON arrays for all analysis artifacts:

```powershell
$Artifacts = @(
    "$Root\analysis\endpoints.json",
    "$Root\analysis\parameters.json",
    "$Root\analysis\secrets-redacted.json",
    "$Root\analysis\postmessage.json",
    "$Root\analysis\dom-xss.json",
    "$Root\analysis\storage.json",
    "$Root\analysis\access-control.json"
)
foreach ($File in $Artifacts) {
    if (-not (Test-Path $File)) { "[]" | Out-File -FilePath $File -Encoding UTF8 }
}
```

**Verification checkpoint**: Run `Get-ChildItem -Recurse $Root` and confirm
all directories and files exist. If any are missing, recreate before advancing.

---

## Phase 1 — Recursive JavaScript Discovery Loop

**Entry condition**: workspace exists, user's seed JS URLs written to
`input/js-urls.txt`.
**Exit condition**: `runtime/url-index.json` contains all discovered URLs,
 verified as JavaScript, with parent→child traceability. No undiscovered
 references remain.

### Loop Design

```
┌─────────────────────────────────────────────────────────┐
│                     DISCOVERY LOOP                       │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │ Dequeue  │───▶│  Fetch   │───▶│ Extract refs     │   │
│  │ URL      │    │  to RAM  │    │ (imports, chunks, │   │
│  └──────────┘    └──────────┘    │  workers, maps)   │   │
│       ▲                          └───────┬──────────┘   │
│       │                                  │              │
│       │         ┌──────────┐    ┌───────▼──────────┐   │
│       └─────────│ Enqueue  │◀───│ Resolve + Filter │   │
│    (if unseen  │ new URLs │    │ + Verify JS      │   │
│     + in scope)└──────────┘    └──────────────────┘   │
│                                                          │
│  Depth limit: 10   │   Verify each URL before queueing   │
└─────────────────────────────────────────────────────────┘
```

### 1.1 Initialize Discovery State

```powershell
$Root = ".\js-intelligence\{main-domain}\{subdomain-name}"

$SeedUrls = Get-Content "$Root\input\js-urls.txt" |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith("#") }

$Queue = [System.Collections.Generic.Queue[string]]::new()
$Seen  = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)
$DiscoveredFrom = @{}

foreach ($Url in $SeedUrls) {
    if ($Seen.Add($Url)) {
        $Queue.Enqueue($Url)
        $DiscoveredFrom[$Url] = "seed"
    }
}

Write-Host "Seed URLs loaded: $($Queue.Count)"
```

### 1.2 Reference Extraction Rules

For each JavaScript file in memory, extract references order by priority:

| Priority | Reference Type | Pattern | Queue? |
|----------|---------------|---------|--------|
| 1 | Source maps | `sourceMappingURL=...` | Always (parse later) |
| 2 | Static imports | `import ... from '...'` | After in-scope check |
| 3 | Dynamic imports | `import('./...')` | After in-scope check |
| 4 | Webpack chunks | `__webpack_require__.e()` | Trace chunk ID to URL |
| 5 | Next.js chunks | `_next/static/...` | After domain check |
| 6 | Turbopack chunks | `e.l('...')`, `TURBOPACK...push()` | After domain check |
| 7 | Workers | `new Worker('...')` | After in-scope check |
| 8 | Script .src | `.src = '...'` | After manual review |
| 9 | getScript calls | `$.getScript('...')` | After in-scope check |
| 10 | Generic .js strings | `'https://.../*.js'` | HEAVY filtering required |

**Critical rule**: Regex matches are NAVIGATION AIDS only. For every match,
read the surrounding 20+ lines to understand whether it produces a real,
reachable JavaScript URL. Dynamic URL assembly (template literals, string
concatenation with variables, bundler runtime logic) requires manual
reconstruction. Never queue a regex match without understanding its context.

### 1.3 URL Resolution

```powershell
function Resolve-JsUrl {
    param([string]$ParentUrl, [string]$Candidate)
    if ($Candidate -match '^https?://') { return $Candidate }
    if ($Candidate -match '^//') {
        $proto = ([uri]$ParentUrl).Scheme
        return "$($proto):$Candidate"
    }
    if ($Candidate.StartsWith('/')) {
        $base = ([uri]$ParentUrl)
        return "$($base.Scheme)://$($base.Authority)$Candidate"
    }
    $baseUri = [uri]$ParentUrl
    $resolved = [uri]::new($baseUri, $Candidate)
    return $resolved.AbsoluteUri
}
```

### 1.4 Queueing Gate

Before enqueueing a candidate URL, ALL of these must be true:

- [ ] URL matches the authorized domain pattern (exact domain or explicitly allowed subdomain)
- [ ] URL returns JavaScript content-type OR has `.js` extension
- [ ] URL is NOT in `$Seen` (case-insensitive)
- [ ] URL is NOT a known third-party (analytics, CDN, social widgets — see blocklist)
- [ ] Response body is NOT HTML, JSON error, empty, or under 50 bytes

**Blocklist** (never queue): `google-analytics.com`, `googletagmanager.com`,
`segment.com`, `amplitude.com`, `mixpanel.com`, `cdnjs.cloudflare.com`,
`unpkg.com`, `jsdelivr.net`, `facebook.net`, `doubleclick.net`,
`hotjar.com`, `intercom.io`, `zendesk.com`

### 1.5 Discovery Loop Execution

```powershell
$MaxDepth = 10
$CurrentDepth = 0
$TotalDiscovered = $Queue.Count

while ($Queue.Count -gt 0 -and $CurrentDepth -lt $MaxDepth) {
    $BatchSize = $Queue.Count
    Write-Host "`n===== DEPTH $CurrentDepth ($BatchSize URLs) ====="

    for ($i = 0; $i -lt $BatchSize; $i++) {
        $CurrentUrl = $Queue.Dequeue()
        Write-Host "  [$($i+1)/$BatchSize] $($CurrentUrl -replace '^https?://[^/]+','')"

        $JsContent = curl.exe -sS -k -L `
          --connect-timeout 10 --max-time 60 `
          -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" `
          -H "Cookie: $SessionCookie" `
          -H "Accept: */*" `
          $CurrentUrl 2>$null

        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($JsContent)) { continue }
        if ($JsContent.Length -lt 50) { continue }
        if ($JsContent -match '^\s*<!DOCTYPE\s+html|^\s*<html') { continue }

        # --- EXTRACT REFERENCES (apply rules from 1.2) ---
        $NewUrls = @()

        # Source maps (P1)
        $smMatches = [regex]::Matches($JsContent, 'sourceMappingURL=([^\s\*]+)')
        foreach ($m in $smMatches) {
            $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value.Trim()
        }

        # Static imports (P2)
        $importMatches = [regex]::Matches($JsContent,
            "(?:import\s*\(?\s*['""]|import\s+.*?\s+from\s+['""]|require\s*\(\s*['""])([^'""]+\.js)")
        foreach ($m in $importMatches) { $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value }

        # Dynamic script loading (P8)
        $srcMatches = [regex]::Matches($JsContent, '\.src\s*=\s*[''"]([^''"]+\.js)[''"]')
        foreach ($m in $srcMatches) { $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value }

        # Workers (P7)
        $workerMatches = [regex]::Matches($JsContent,
            "(?:new\s+(?:Shared)?Worker|navigator\.serviceWorker\.register)\s*\(\s*['""]([^'""]+\.js)['""]")
        foreach ($m in $workerMatches) { $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value }

        # Webpack/Next.js chunks (P4-P5)
        $chunkMatches = [regex]::Matches($JsContent,
            "['""]([^'""]*_next\/static\/[^'""]+\.js)['""]")
        foreach ($m in $chunkMatches) { $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value }

        # Turbopack chunks (P6)
        $tpMatches = [regex]::Matches($JsContent, "e\.l\s*\(\s*['""]([^'""]+\.js)['""]")
        foreach ($m in $tpMatches) { $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value }

        # Deduplicate
        $NewUrls = $NewUrls | Sort-Object -Unique | Where-Object { $_ -and $Seen.Add($_) }

        # Enqueue with scope verification
        foreach ($NewUrl in $NewUrls) {
            if ($NewUrl -notmatch $AuthorizedDomainPattern) {
                Write-Host "    SKIP: out of scope"
                $Seen.Remove($NewUrl) | Out-Null
                continue
            }
            $Queue.Enqueue($NewUrl)
            $DiscoveredFrom[$NewUrl] = $CurrentUrl
            $TotalDiscovered++
            Write-Host "    + $($NewUrl -replace '^https?://[^/]+','')"
        }

        $JsContent = $null
        Remove-Variable JsContent -ErrorAction SilentlyContinue

        # Rate limiting
        Start-Sleep -Milliseconds 200
    }
    $CurrentDepth++
}

Write-Host "`n===== DISCOVERY COMPLETE: $TotalDiscovered URLs ====="
```

### 1.6 Save and Deduplicate the Index

```powershell
$IndexPath = "$Root\runtime\url-index.json"
$UrlIndex = $Seen | Sort-Object | ForEach-Object {
    [PSCustomObject]@{
        url = $_
        depth = $CurrentDepth
        discovered_from = $DiscoveredFrom[$_]
        discovery_order = [array]::IndexOf([array]$Seen, $_)
        analysis_complete = $false
    }
}

if (Test-Path $IndexPath) {
    $Existing = Get-Content $IndexPath -Raw | ConvertFrom-Json
    $Combined = @($Existing) + @($UrlIndex) | Sort-Object url -Unique
    $Combined | ConvertTo-Json -Depth 3 | Out-File -FilePath $IndexPath -Encoding UTF8
} else {
    $UrlIndex | ConvertTo-Json -Depth 3 | Out-File -FilePath $IndexPath -Encoding UTF8
}

# Explicit dedup pass
$IndexData = Get-Content $IndexPath -Raw | ConvertFrom-Json
$Deduplicated = $IndexData | Sort-Object url -Unique
$Deduplicated | ConvertTo-Json -Depth 3 | Out-File -FilePath $IndexPath -Encoding UTF8
```

### 1.7 Extract JavaScript-Revealed Domains

```powershell
$DomainFile = ".\js-intelligence\$MainDomain\domaininjavascript.txt"
$DomainSet = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)

foreach ($Url in $Seen) {
    $JsContent = curl.exe -sS -k -L `
      --connect-timeout 10 --max-time 60 `
      -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" `
      -H "Cookie: $SessionCookie" `
      -H "Accept: */*" `
      $Url 2>$null

    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($JsContent)) { continue }
    if ($JsContent.Length -lt 50) { continue }

    $Matches = [regex]::Matches($JsContent,
        '(?:(?:https?://)|(?://))([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*(?:\.[a-zA-Z]{2,}))(?:/[^\s"'']*)?'
    )
    foreach ($Match in $Matches) {
        $Hostname = $Match.Groups[1].Value.ToLowerInvariant()
        if ($Hostname -and $Hostname -notmatch '^(localhost|0\.0\.0\.0|127\.\d+\.\d+\.\d+|::1|example\.com|example\.org)$') {
            $DomainSet.Add($Hostname) | Out-Null
        }
    }
    $JsContent = $null
    Remove-Variable JsContent -ErrorAction SilentlyContinue
}
$DomainSet | Sort-Object | Out-File -FilePath $DomainFile -Encoding UTF8
```

**Verification checkpoint**: Confirm `url-index.json` exists and contains > 0
entries. Confirm count matches `$TotalDiscovered`. If zero URLs discovered and
user provided valid seeds, report a discovery failure. If discovery count
exceeds 200 URLs, warn user and ask whether to continue (context risk).

---

## Phase 2 — Deep File Analysis Loop

**Entry condition**: `url-index.json` populated, all URLs verified as JavaScript.
**Exit condition**: every file in `url-index.json` has `analysis_complete = true`,
all 8 categories populated in `analysis/*.json`.

### Context Budget Awareness

This phase is the highest context consumer. Apply these rules:

1. **Process 5-10 files, then run verification** — regenerate reports and
   check for consistency gaps.
2. **Use subagents for large files** — if a file exceeds 500K characters,
   delegate to a subagent with a focused prompt for a single analysis category.
3. **Clear working memory after each file** — set `$JsContent = $null` and
   invoke garbage collection before loading the next file.
4. **Prefetch findings before deep analysis** — on the first pass of each
   file, scan for the 8 category indicators (see 2.1). On the second pass,
   trace each indicator to its full context.

### 2.1 Two-Pass Analysis Protocol

**Pass 1 — Surface Scan** (fast, per file):
1. Fetch file into memory.
2. Validate it's JavaScript (not HTML/JSON error page).
3. Scan for all 8 category indicators (secrets prefixes, endpoint patterns,
   postMessage handlers, DOM sinks, storage APIs, access control checks,
   source map directives, parameter builders).
4. Record character offsets for every match.
5. Save to `analysis/file-notes/{sanitized-filename}.json` with status
   `surface_scan_complete`.
6. Clear memory.

**Pass 2 — Deep Trace** (thorough, per finding):
1. Re-fetch the file.
2. For each indicator from Pass 1, read the surrounding 50+ lines.
3. Trace data flow: source → intermediate → sink.
4. For endpoints: resolve class prefixes, global prefixes, inherited bases.
5. Apply the 8-category classification rules (Phase 3).
6. Write structured findings to the appropriate `analysis/*.json`.
7. Clear memory.

### 2.2 File Processing

For multi-line content:
```powershell
$Lines = $JsContent -split "`r?`n"
$Lines | Select-Object -First 500
$Lines | Select-Object -Skip 500 -First 500
```

For minified single-line content:
```powershell
$ChunkSize = 12000
for ($Offset = 0; $Offset -lt $JsContent.Length; $Offset += $ChunkSize) {
    $Length = [Math]::Min($ChunkSize, $JsContent.Length - $Offset)
    $JsContent.Substring($Offset, $Length)
}
```

**Never write JavaScript or source-map content to disk.** All analysis happens
in memory. Only findings, evidence snippets (under 200 chars), and file/offset
references are persisted.

### 2.3 File Metadata Record

For every analyzed file, record:
```json
{
  "original_url": "https://...",
  "final_url": "https://...",
  "http_status": 200,
  "content_type": "application/javascript",
  "character_count": 452000,
  "framework": "Next.js 14",
  "role": "API client - user management",
  "fully_read": true,
  "source_map_url": "https://...",
  "source_map_accessible": true,
  "source_map_sources_count": 47,
  "analysis_complete": true,
  "categories_analyzed": ["secrets", "endpoints", "postmessage", "dom-xss", "parameters", "access-control", "storage", "sourcemap"]
}
```

---

## Phase 3 — Eight Category Deep Analysis

**Entry condition**: Pass 1 surface scan complete for the current file.
**Exit condition**: findings written (or "no finding" recorded) for all 8
categories for the current file.

### Decision Tree for Claims

Before reporting ANY finding, walk this tree:

```
Indicator found?
├── YES → Is it in active code (not comments, dead code, test fixtures)?
│   ├── YES → Trace the full data flow (source → transforms → sink).
│   │   ├── Flow confirmed → Is there an attacker-controllable input?
│   │   │   ├── YES → Is there a missing protection (validation, sanitization, auth check)?
│   │   │   │   ├── YES → Report finding with confidence
│   │   │   │   └── NO → Record as "reviewed, protected" (no finding)
│   │   │   └── NO → Record as "no attacker influence" (no finding)
│   │   └── Flow not traceable → Record as "needs further analysis"
│   └── NO → Skip (false positive)
└── NO → Record "no finding" for this category
```

### Category 1 — Hardcoded Secrets

**Indicators** (variable names): `apiKey`, `secretKey`, `accessToken`,
`authToken`, `refreshToken`, `password`, `passwd`, `clientSecret`,
`privateKey`, `appSecret`, `encryptionKey`, `signingKey`, `credentials`

**Indicators** (value prefixes): `sk-`, `pk_`, `AKIA`, `ASIA`, `AIza`,
`SG.`, `ghp_`, `github_pat_`, `xox`, `Bearer eyJ`, `-----BEGIN`

**Discrimination rules**:
- Public keys (e.g., `pk_live_` for Stripe) are NOT secrets — mark as
  "publishable key, informational only"
- Placeholders like `YOUR_API_KEY_HERE`, `xxxxxxxx`, `test_key_` are NOT
  secrets
- Firebase `apiKey` in `firebaseConfig` objects is a public identifier, not
  a secret — mark as informational unless in non-Firebase context
- Base64-decode to inspect: `[System.Convert]::FromBase64String($value)`

**Validation**: Only validate if explicitly authorized. Use read-only API
calls. Never create resources, send messages, or modify data.

**Output schema**:
```json
{
  "type": "api_key",
  "redacted_value": "AIzaSyD...xP9",
  "file_url": "https://...",
  "char_offset": 12345,
  "variable_name": "firebaseApiKey",
  "context": "Found in firebase.initializeApp() config object",
  "is_real_secret": false,
  "validation_status": "informational - Firebase public key",
  "risk": "informational"
}
```

### Category 2 — Endpoint Reconstruction

**The most complex category.** The core rule:

> Never report a route fragment as a complete endpoint. Reconstruct the full
> URL by tracing the request through its helper, class constructor, inherited
> base, and global configuration.

**Reconstruction protocol** (execute in order):

1. **Find the request call**: `this.sendRequest("GET", "/me", ...)`
2. **Find the request helper**: trace `sendRequest` to its definition — it
   may prepend `this.baseURL`, `this.apiPrefix`, or inject headers.
3. **Find the constructor**: `constructor() { this.pathPrefix = "/user" }`
4. **Find inherited constructors**: `super(...)` → parent class
   `this.resource = "/api/v2"` → grandparent `this.baseUrl = "https://..."`
5. **Resolve dynamic values**: template literals `` `/user/${id}/profile` ``,
   array joins `[prefix, suffix].join('/')`, imported constants.
6. **Combine in execution order**: `{baseUrl}{inheritedPrefix}{pathPrefix}{route}{queryParams}`
7. **Verify by comparing sibling methods** — if 3 methods in the same class
   all use `this.sendRequest`, they all share the same prefix chain.

**Confidence levels for reconstructed endpoints**:
- **Confirmed**: full trace complete, all prefixes resolved, sibling methods
  consistent
- **High**: prefix chain resolved but request helper implementation not
  fully visible (e.g., in a separate chunk)
- **Medium**: some prefixes resolved from naming conventions rather than
  explicit code
- **Low**: only the route fragment visible, no prefix chain resolved

**Output schema**:
```json
{
  "http_method": "GET",
  "route_fragment": "/me",
  "class_prefix": "/user",
  "inherited_prefix": "/api/v2",
  "base_url": "https://api.example.com",
  "full_endpoint": "GET https://api.example.com/api/v2/user/me",
  "path_params": [],
  "query_params": [],
  "headers": {"Authorization": "Bearer token"},
  "body_params": null,
  "reconstruction_confidence": "high",
  "source_file": "https://.../bundle.js",
  "char_offset": 45230,
  "containing_class": "UserService",
  "method_name": "me",
  "privilege_context": "authenticated user",
  "calling_feature": "Profile page",
  "tested": false,
  "test_result": null
}
```

### Category 3 — postMessage Handlers

**Indicators**: `addEventListener("message",...)`, `window.onmessage`,
`self.onmessage`, `MessageChannel`, `BroadcastChannel`

**Analysis decision tree**:
```
Handler found?
├── YES → Has origin validation?
│   ├── NO → HIGH severity (missing origin check)
│   └── YES → Is it weak validation?
│       ├── YES (includes/endsWith/indexOf/match without ^/$) → MEDIUM severity
│       └── NO (strict === check or Set.has) → Record as "properly validated"
└── NO → Record "no finding"
```

**Weak validation patterns**:
- `event.origin.includes("target.com")` — bypass with `attacker.com/target.com`
- `event.origin.endsWith("target.com")` — bypass with `eviltarget.com`
- `event.origin.indexOf("target.com") !== -1` — bypass with `evil.target.com.attacker.com`
- `event.origin.match(/target.com/)` — same as includes

**Strong validation pattern**: `event.origin === "https://expected.example.com"`

**Output schema**:
```json
{
  "receiver": "window",
  "handler_location": "global scope",
  "has_origin_check": false,
  "origin_check_detail": null,
  "origin_check_strength": "none",
  "has_source_check": false,
  "accepted_commands": ["NAVIGATE", "REFRESH"],
  "sensitive_operations": ["location.href assignment"],
  "exploitable": "potentially",
  "attacker_requirements": "Victim visits attacker page; attacker opens target in iframe/popup and postMessages the command",
  "impact": "Open redirect via postMessage",
  "source_file": "https://...",
  "char_offset": 89200
}
```

### Category 4 — DOM XSS Sources and Sinks

**Evidence-chain requirement**: You MUST trace the complete path from source
to sink before reporting. A finding requires:

1. **Source identified** (exact variable/API call, character offset)
2. **Data transformations documented** (every function, assignment, and
   sanitizer between source and sink)
3. **Sink identified** (exact DOM API, execution context)
4. **Sanitization assessed** (what, if any, protections are applied)
5. **Context classified** (HTML context, attribute context, JS context,
   URL context, CSS context, or text-only)

**If any link in the chain is missing, the finding is "needs further analysis,"
not "confirmed."**

**Sinks with their execution contexts**:
| Sink | Context | Exploitation difficulty |
|------|---------|------------------------|
| `innerHTML` | HTML | Medium (needs HTML tags) |
| `outerHTML` | HTML | Medium |
| `insertAdjacentHTML()` | HTML | Medium |
| `document.write()` | HTML (during parse) | Medium |
| `eval()` | JavaScript | Hard (needs valid JS) |
| `Function()` | JavaScript | Hard |
| `setTimeout(str)` | JavaScript | Hard |
| `location = x` | URL | Easy (javascript: or data:) |
| `script.src` | URL → JS | Medium |
| `iframe.src` | URL → HTML | Medium |
| `a.href` with `javascript:` | URL → JS | Medium |

**Reflection testing** (Phase 5): Use a unique marker, not a script payload:
```powershell
$marker = "JSINTEL-TEST-48271"
curl.exe -sS -k -i "https://authorized.example/search?q=$marker"
```

**Output schema**:
```json
{
  "source": "location.hash",
  "source_offset": 12340,
  "transformations": [
    "decodeURIComponent() at offset 12400",
    "assigned to variable 'query' at offset 12450"
  ],
  "sanitization": "none detected",
  "sink": "innerHTML",
  "sink_offset": 12900,
  "execution_context": "HTML",
  "requires_user_interaction": true,
  "trigger": "User visits URL with hash fragment containing HTML payload",
  "reflected_or_stored": "reflected (DOM-based)",
  "reflection_tested": false,
  "browser_execution_confirmed": false,
  "curl_cannot_prove": true,
  "confidence": "high",
  "source_file": "https://...",
  "category_notes": "source-to-sink path confirmed; browser execution not tested"
}
```

### Category 5 — Hidden Parameters

**Indicators**: `FormData()`, `URLSearchParams()`, `JSON.stringify()`,
`fetch()`, `axios`, `$.ajax`, request body assembly functions.

**High-value parameter names** (report all instances, prioritize these):
`user_id`, `userId`, `account_id`, `accountId`, `org_id`, `tenant_id`,
`role`, `roles`, `permission`, `permissions`, `is_admin`, `isAdmin`,
`admin`, `plan`, `tier`, `scope`, `scopes`, `verified`, `isVerified`,
`status`, `owner`, `ownerId`, `feature_flag`, `featureFlag`,
`internal_flag`, `internal`, `debug`, `price`, `amount`, `credits`,
`limit`, `quota`

**Trace the parameter's origin**:
- Is the value hardcoded? → Low risk (requires code modification)
- Is the value from user input (URL, form, storage)? → Higher risk
- Is the value from server response? → Depends on server trust
- Is the value from localStorage/sessionStorage/cookie? → Higher risk
  (attacker may be able to modify)

**Output schema**:
```json
{
  "parameter_name": "role",
  "endpoint": "POST /api/v1/users",
  "endpoint_source": "fetch() call in UserSettings.tsx",
  "data_type": "string",
  "default_value": "user",
  "value_source": "user profile from server response",
  "visible_in_ui": false,
  "user_controllable": false,
  "security_sensitive": true,
  "source_file": "https://...",
  "char_offset": 23400,
  "tested": false,
  "test_mutation": null,
  "test_result": null
}
```

### Category 6 — Client-Side Access Control

**Indicators**: `if (user.role === "admin")`, `if (permissions.includes(...))`,
`if (isOwner)`, `if (featureFlags.adminPanel)`, `if (plan === "enterprise")`,
route guards, conditional rendering, CSS `display:none` on admin elements

**Analysis protocol**:
1. Identify the condition (role check, permission array, feature flag).
2. Identify what is gated (UI component, route, button, API call).
3. Extract the endpoint called inside the gated code.
4. Test the endpoint WITHOUT the condition being met (using a lower-privileged
   test account). This tests server-side enforcement.

**Critical rule**: A hidden admin button is NOT a vulnerability on its own.
The question is: *does the API endpoint behind that button reject the
low-privileged user?* If yes → properly enforced. If no → access control
vulnerability.

**Classification**:
| Scenario | Classification |
|----------|---------------|
| UI hidden + API rejects low-priv user | Properly enforced (no finding) |
| UI hidden + API accepts low-priv user | Access control vulnerability (HIGH) |
| UI visible but disabled + API rejects | UI bug only (LOW) |
| UI visible but disabled + API accepts | Access control vulnerability (MEDIUM) |
| No UI at all + API accepts low-priv user | Access control vulnerability (HIGH) |

**Output schema**:
```json
{
  "condition": "user.role === 'admin'",
  "condition_type": "role_check",
  "gated_element": "AdminPanel component (React route guard)",
  "gated_endpoint": "GET /api/admin/users",
  "http_method": "GET",
  "ui_only_restriction": true,
  "server_enforcement_tested": false,
  "test_account_role": null,
  "test_result": null,
  "classification": "needs verification",
  "source_file": "https://...",
  "char_offset": 67000
}
```

### Category 7 — Client-Side Storage

**Indicators**: `localStorage.setItem/getItem`, `sessionStorage.setItem/getItem`,
`document.cookie`, `indexedDB`, Cache API

**For each storage operation, determine**:
1. What is stored (key name, value type)
2. Where the value comes from (server response, user input, computed)
3. Where the value is used (auth header, API request, DOM rendering)
4. Whether the value is sensitive (token, PII, role, permission)
5. Whether the storage mechanism is appropriate (HttpOnly cookies for tokens)

**Risk matrix**:
| Storage | Content | Risk |
|---------|---------|------|
| localStorage | JWT access token | HIGH (accessible to any JS on origin; increases XSS impact) |
| localStorage | User role "admin" | HIGH (client-modifiable; if server trusts it) |
| localStorage | User display name | LOW (non-sensitive PII at most) |
| sessionStorage | Session ID | MEDIUM (cleared on tab close but accessible to JS) |
| JavaScript-set cookie | Auth token | MEDIUM (cannot be HttpOnly) |
| Server-set cookie (HttpOnly) | Auth token | Proper (no finding) |

**Output schema**:
```json
{
  "storage_mechanism": "localStorage",
  "key_name": "auth_token",
  "value_type": "JWT",
  "value_source": "POST /api/login response body",
  "value_consumer": "Authorization header on all API requests",
  "is_sensitive": true,
  "storage_appropriate": false,
  "should_be_httponly_cookie": true,
  "risk": "HIGH - JWT in localStorage increases XSS impact to full account takeover",
  "source_file": "https://...",
  "char_offset": 45100
}
```

### Category 8 — Source Map Exposure

**Discovery**: Inspect file end for `//# sourceMappingURL=` or
`/*@ sourceMappingURL= */`.

**If a source map is accessible**:
1. Fetch it into memory (never save to disk).
2. Parse as JSON.
3. Check `sourcesContent` presence (this is where real code lives).
4. Analyze embedded source files using ALL 7 other categories.
5. Run the same analysis depth on embedded sources as on the bundle.

**Impact assessment**: A publicly accessible source map is NOT automatically
a vulnerability. Impact depends on what the source map reveals:
- Dev comments with credentials → HIGH
- Internal API routes not otherwise discoverable → MEDIUM
- Business logic details → LOW (unless revealing auth bypass)
- Just minified-to-original mapping → Informational

---

## Phase 4 — Endpoint Normalization

Consolidate all endpoints from Category 2 across all files.

**Normalization rules**:
- `/api/users/123` and `/api/users/456` → `/api/users/{id}`
- `/api/users/123/profile` → `/api/users/{id}/profile`
- Do NOT merge `/api/users/{id}` with `/api/users/{id}/admin` unless context
  confirms they're the same endpoint with different params.

**Deduplicate** on: `{method} {normalized_path} {base_url}`

---

## Phase 5 — Controlled Endpoint Testing

**ONLY if user authorized endpoint testing in Phase 0.**

**Testing prioritization**:
1. **P0 — Access control endpoints** (admin routes accessible to low-priv user)
2. **P1 — IDOR-susceptible endpoints** (routes with `{userId}`, `{orderId}`)
3. **P2 — Hidden parameters** (parameters not visible in UI)
4. **P3 — Unauthenticated access** (routes missing auth requirement)
5. **P4 — Newly discovered endpoints** (not in public docs)

**Test request template**:
```powershell
$Method = "GET"  # or HEAD, OPTIONS
$Url = "https://authorized.example/api/v2/users/12345"
$Token = $env:AUTHORIZED_BEARER_TOKEN
$Cookie = $env:AUTHORIZED_SESSION_COOKIE

$Response = curl.exe -sS -k -i `
  --connect-timeout 10 --max-time 30 `
  -X $Method `
  -H "Authorization: Bearer $Token" `
  -H "Cookie: $Cookie" `
  -A "Mozilla/5.0" `
  $Url 2>$null
```

**Response classification**:
| HTTP Status | Classification | Action |
|-------------|---------------|--------|
| 200 | Reachable | Record response body traits (JSON keys, length) |
| 301/302 | Redirect | Follow redirect target; record destination |
| 401 | Requires auth | Test with auth token; compare |
| 403 | Forbidden | Auth is enforced (good sign for security) |
| 404 | Not found | Record; may need different parameter values |
| 405 | Method not allowed | Try OPTIONS to see allowed methods |
| 429 | Rate limited | Wait for Retry-After; reduce request rate |

**Retry logic**: 3 attempts max for transient errors (2s between attempts).

**Log every request** to `requests/request-log.jsonl`:
```json
{"timestamp":"2026-07-22T10:30:00Z","method":"GET","url":"https://...","status":200,"response_length":1234,"response_summary":"JSON with keys: id,name,email"}
```

**Testing stopping conditions**: If you encounter 3 consecutive 429s, pause
for 60 seconds. If you encounter a 403 or security block page, do not retry
that endpoint. If you receive HTML login page on a route that should be API,
mark as "redirects to login — likely properly authenticated."

---

## Phase 6 — Cross-File Correlation

Before finalizing the report, correlate findings across files:

1. **Endpoint → Storage**: does a token stored in localStorage (Cat 7) get
   sent as Authorization header (Cat 2)?
2. **Endpoint → Access Control**: does an admin endpoint (Cat 6) appear to
   be accessible without the role check from the gating component?
3. **postMessage → DOM**: does a postMessage handler (Cat 3) write
   unvalidated data to innerHTML (Cat 4)?
4. **Secret → Endpoint**: does a hardcoded API key (Cat 1) get embedded in
   a request to an internal service (Cat 2)?
5. **Parameter → Access Control**: does a hidden parameter like `role=admin`
   (Cat 5) get sent to an admin endpoint (Cat 6)?

**For each correlation, check**: do the two findings appear in the same file
or in files loaded by the same page? Correlations across files that are never
loaded together are lower severity.

---

## Phase 7 — Report Generation

### 7.1 File Notes

For each analyzed file, write to `analysis/file-notes/{sanitized-filename}.md`:
```markdown
# File: {original_url}
- **Role**: {what this file does in the application}
- **Framework**: {detected framework/bundler}
- **Character count**: {size}
- **Categories with findings**: {list}
- **Categories without findings**: {list}
- **Source map**: {URL or "none"}
```

### 7.2 Summary Report (`reports/summary.md`)

**Structure** (critical info FIRST — context engineering principle):
```markdown
# JS Intelligence Report — {domain}/{subdomain}
**Date**: {timestamp}
**Files analyzed**: {count}
**Total characters**: {sum}

## Critical Findings (P0)
{findings with severity CRITICAL or confidence "Confirmed" + HIGH impact}

## High Severity Findings (P1)
{findings with severity HIGH}

## Medium Severity Findings (P2)
{findings with severity MEDIUM}

## Informational
{findings with severity LOW or INFORMATIONAL}

## Statistics
| Category | Findings | Tested | Confirmed |
|----------|----------|--------|-----------|
| Secrets | N | N | N |
| Endpoints | N | N | N |
| postMessage | N | N/A | N |
| DOM XSS | N | N | N |
| Hidden Parameters | N | N | N |
| Access Control | N | N | N |
| Storage | N | N/A | N |
| Source Maps | N | N/A | N |

## Items Not Tested (scope/safety)
{list}

## Items Requiring Browser Validation
{list}
```

### 7.3 Full Report (`reports/full-report.md`)

**Structure**:
```markdown
# Full JS Intelligence Report

## Executive Summary
{3-5 sentence overview of the engagement}

## Scope
- Authorized domains: ...
- Files analyzed: N
- Endpoints extracted: N
- Endpoints tested: N

## Findings
{finding template for each confirmed/high-confidence finding}

## Endpoint Index
| Method | Endpoint | Source File | Auth | Tested | Result |
|--------|----------|-------------|------|--------|--------|

## Parameter Index
| Parameter | Endpoint | Source | Hidden | Security-Sensitive |
|-----------|----------|--------|--------|--------------------|

## Source Map Index
| JS File | Map URL | Accessible | Sources | Sensitive Content |
|---------|---------|------------|---------|-------------------|

## File Index
| File | Size | Role | Categories with Findings |
|------|------|------|--------------------------|
```

### Finding Template
```markdown
## [{Severity}] {Title}

| Field | Value |
|-------|-------|
| **Category** | {category} |
| **Confidence** | {confidence} |
| **Validation** | {validation_status} |
| **Source File** | {url} |
| **Character Offset** | {offset} |

### Evidence
{short code snippet, < 200 chars, showing the relevant logic}

### Data Flow
{source → intermediate → sink, if applicable}

### Security Impact
{what an attacker could achieve, what they need}

### Test Results
{if tested: status, request, response summary}
{if not tested: reason}

### Limitations
{what could not be verified, what assumptions were made}

### Remediation
{concrete fix recommendation}
```

---

## Agentic Loop Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                     JSI-MINING AGENT LOOP                           │
│                                                                      │
│  Phase 0 ──▶ Phase 1 ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4           │
│  Setup      Discovery   File       8-Category  Normalize             │
│  (gate)     (loop)      Analysis   Analysis    Endpoints             │
│              │           (loop)     (8 passes)                       │
│              │              │          │          │                  │
│              ▼              ▼          ▼          ▼                  │
│         [VERIFY]      [VERIFY]   [VERIFY]   [VERIFY]                │
│         url-index     file-notes findings   deduped                  │
│         populated     complete   written    endpoints                │
│                                                                      │
│              │                                                       │
│              ▼                                                       │
│         Phase 5 ──▶ Phase 6 ──▶ Phase 7                              │
│         Testing    Cross-File  Reports                               │
│         (opt)      Correlation (output)                              │
│              │          │          │                                 │
│              ▼          ▼          ▼                                 │
│         [VERIFY]   [VERIFY]   [VERIFY]                               │
│         log.jsonl  correlations summary.md                           │
│         not empty   documented  generated                            │
│                                                                      │
│  Each [VERIFY] is a HARD GATE. Do not advance until verified.        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Context Management Rules

These rules prevent the agent from exceeding its context budget during
long-running analysis:

1. **After every 5 files processed**, run `reports/summary.md` regeneration
   and check for consistency. This is both verification and context flush.
2. **For files > 500K characters**, use a subagent to perform a single
   category of analysis (e.g., "extract only endpoints from this file").
   The subagent returns structured findings; the main agent never loads the
   full file.
3. **Between phases**, clear working memory and restart. Phase transitions
   are natural context reset points.
4. **If the same finding appears in 3+ files**, promote it to a section
   header and stop re-analyzing it per-file.
5. **Prefetch with HEAD before GET** for all candidate URLs — saves the
   context cost of loading non-JS responses.

---

## Quick-Start Execution Order

```powershell
# 1. Phase 0 — Setup
$Root = ".\js-intelligence\{main-domain}\{subdomain-name}"
# Create directories per Phase 0.3

# 2. Phase 1 — Discovery
# Run 1.1 through 1.7 above

# 3. Phase 2 — File Analysis Loop
$IndexData = Get-Content "$Root\runtime\url-index.json" -Raw | ConvertFrom-Json
$JsUrls = $IndexData | ForEach-Object { $_.url } |
    Where-Object { $_ -and -not $_.StartsWith("#") }

foreach ($Url in $JsUrls) {
    $JsContent = curl.exe -sS -k -L `
      --connect-timeout 10 --max-time 60 `
      -A "Mozilla/5.0" `
      $Url

    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($JsContent)) { continue }

    # Pass 1 — surface scan (Phase 2.1)
    # Pass 2 — deep trace (Phase 3, 8 categories)
    # Incremental write to analysis/*.json

    $JsContent = $null
    Remove-Variable JsContent -ErrorAction SilentlyContinue
}

# 4. Phase 4 — Normalize and deduplicate endpoints

# 5. Phase 5 — Test endpoints (if authorized)

# 6. Phase 6 — Cross-file correlation

# 7. Phase 7 — Generate reports
```

---

## Required Behaviors (Checklist)

### MUST DO
- [ ] Collect full authorization details before any request (Phase 0)
- [ ] Recursively discover ALL referenced JS files before deep analysis (Phase 1)
- [ ] Verify each discovered URL is JavaScript before queueing
- [ ] Read EVERY file completely (Phase 2)
- [ ] Trace full data flows before reporting findings (Phase 3 decision tree)
- [ ] Reconstruct endpoints by tracing request helpers, constructors, prefixes
- [ ] Report both route fragments AND reconstructed complete endpoints
- [ ] Record source file URL and character offset with every finding
- [ ] Separate evidence from assumptions
- [ ] Distinguish client-side behavior from server-side enforcement
- [ ] Redact all credentials (keep only enough characters for identification)
- [ ] Log every test request to `requests/request-log.jsonl`
- [ ] State clearly what could NOT be validated
- [ ] Keep all JavaScript and source-map content in memory only
- [ ] Run verification checkpoints between phases

### MUST NOT DO
- [ ] Report findings based on keyword matches alone
- [ ] Claim XSS because `innerHTML` exists (require full source→sink trace)
- [ ] Claim auth bypass because admin endpoint exists (require testing)
- [ ] Claim secret validity without safe, read-only evidence
- [ ] Claim `curl.exe` output proves browser-side JS execution
- [ ] Follow/test URLs outside the authorized scope
- [ ] Use real user identifiers for IDOR testing
- [ ] Perform destructive or state-changing requests without explicit permission
- [ ] Expose complete tokens, cookies, passwords, or private keys
- [ ] Save, download, cache, or write JavaScript/source-map bodies to disk
- [ ] Hide uncertainties or invent results
- [ ] Skip the recursive discovery phase
- [ ] Skip the verification checkpoint at any phase boundary
