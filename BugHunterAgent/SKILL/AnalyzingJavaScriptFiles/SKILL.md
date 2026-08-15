---
name: js-intelligence-mining
description: |
  Use ONLY when the user explicitly requests deep security analysis of JavaScript
  files from an authorized target domain. Starts with user-provided JS files,
  recursively discovers all additional JS files (imports, chunks, source maps,
  workers), then performs methodical manual JS source analysis — hardcoded secrets,
  reconstructed API endpoints, postMessage handlers, DOM XSS sources/sinks,
  hidden parameters, client-side access control, sensitive storage, source
  map exposure, and known-vulnerable bundled dependencies. Includes controlled
  endpoint testing. Every finding records its source file. Prioritizes files by
  likely relevance before exhaustive reading, and reads every file completely.
  Trigger on "analyze JS," "JavaScript audit," "JS recon," "JavaScript intelligence mining,"
  or when asked to perform security review of JavaScript files for a target.
---

# JavaScript Intelligence Mining

## Purpose

Deep, methodical security analysis of JavaScript files from an explicitly
authorized target. Read every file completely, understand its logic, connect
related functions and variables, identify hidden application behavior, extract
endpoints and parameters, and report security-relevant findings with supporting
evidence. Use reasoning to analyze source — do not rely on automated
vulnerability scanners or fuzzers. Deterministic, non-exploiting aids (regex
navigation, AST-based call-graph tracing, dependency-version lookups) are
permitted where they make manual analysis faster and more reliable — they are
not a substitute for reading and understanding the code.

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
- Use `curl.exe`, PowerShell built-ins, .NET classes, and — where useful for
  deterministic parsing only (see "Permitted Parsing Aids" below) — a local
  JavaScript AST parser. Do not use vulnerability scanners, secret-scanning
  tools, fuzzing frameworks, or browser automation.
- Do not use automated scanners, fuzzing frameworks, secret-scanning tools,
  or browser automation.

### Permitted Parsing Aids (not "automated scanning")

A blanket ban on tooling conflates "don't let a scanner declare
vulnerabilities for you" with "don't use any deterministic aid." The
following are permitted because they don't judge security impact — they only
help a human reader navigate faster and reduce transcription error. They
never replace manual reading, understanding, or the judgment calls in Phase 6:

- **AST-based call-graph tracing** (e.g. a local `acorn`/`espree` parse) to
  mechanically follow a method call to its class constructor, inherited
  `pathPrefix`/`basePath` properties, and parent-class chain, when minified
  single-letter identifiers make this error-prone to trace by eye. Use it to
  *locate* the relevant lines; still read and interpret those lines manually
  before recording an endpoint. Treat its output as a lead, not a finding.
- **Bundled dependency name/version extraction** for the known-vulnerable-
  dependency check in Category 9 below (extracting `name`/`version` strings
  from webpack module metadata, package.json fragments embedded in bundles,
  or license-header comments — not scanning for exploit signatures).
- Existing regex-as-navigation usage described throughout this skill.

If a parser or lookup can't be run in the current environment, fall back to
manual reading — do not skip a file because tooling isn't available.

## Required Workspace Structure

Create this tree before starting, using `{main-domain}` as the primary domain
and `{subdomain-name}` as the subdomain. Every JavaScript file from the same
subdomain shares the same output directory.

For example, given `https://admin.att.com/main.213123asd.js` and
`https://admin.att.com/main.f983mceew.js` on `dashboard.vercel.com` of
`vercel.com`, both use:

```
bug-hunter/vercel.com/dashboard.vercel.com/AnalyzingJavaScriptFiles/
```

```
bug-hunter/
└── {main-domain}/
    └── {subdomain-name}/
        └── AnalyzingJavaScriptFiles/
            ├── endpoint.json
            ├── parameter.json
            ├── inputurljs.txt
            └── notes/
```

**Only these outputs are allowed.** `AnalyzingJavaScriptFiles/` contains
exactly four items — nothing else:

- `inputurljs.txt` — the seed URL list plus every recursively discovered
  JavaScript URL (one per line; `#` starts a comment).
- `endpoint.json` — every reconstructed endpoint (see Phase 7).
- `parameter.json` — every parameter/field identified (see Phase 6
  Category 5).
- `notes/` — all observations, findings, assumptions, interesting behaviors,
  hypotheses, and other useful information discovered while analyzing the
  files. Per-file analysis notes, the discovery index and triage, secrets /
  postMessage / DOM-XSS / access-control / dependency findings, request test
  results, and the final report all live inside `notes/`.

Do not create or save any additional files outside this structure. Runtime
state, category findings, request logs, source-map notes, and reports are
written only into `notes/`.

### Incremental Update Rule

When additional JavaScript files are provided for a subdomain that already
has a workspace under
`bug-hunter/{main-domain}/{subdomain-name}/AnalyzingJavaScriptFiles/`:

1. **Never delete** existing files or directories.
2. **Update** existing JSON/text files by appending new entries and removing
   duplicates (de-duplicate on unique keys like URL, endpoint path, parameter
   name, finding title, etc.).
3. **Add** new findings, endpoints, parameters, secrets, and analysis notes
   into the existing files. Do not overwrite or replace the existing content.
4. **Extract only unique entries** when merging — if an entry with the same
   unique identifier already exists, skip it; if it differs, update it.
5. **Regenerate** the consolidated analysis note in `notes/` after each
   session to reflect the combined state of all analysis.
6. Add new file notes under `notes/` for each newly analyzed JavaScript file.
   Never delete or replace existing note files.

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

## Phase 2 — Recursive JavaScript File Discovery

**Purpose:** Start from the user-provided JavaScript files and recursively discover
every additional JavaScript file referenced within them — imported modules,
dynamically loaded scripts, code-split chunks, Web Worker files, source maps,
and inline JavaScript URLs — until no new files are found. This phase produces
the complete input set for the deep analysis phases that follow.

### Step 1 — Initialize the Discovery Queue

Load the user's initial JavaScript URL list into a discovery queue and a
seen-URL set. Create or clear the discovery state file:

```powershell
$Root = ".\bug-hunter\{main-domain}\{subdomain-name}\AnalyzingJavaScriptFiles"

# Load seed URLs from the user-provided file
$SeedUrls = Get-Content "$Root\inputurljs.txt" |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith("#") }

# Initialize the queue (FIFO) and the global seen set
$Queue = [System.Collections.Generic.Queue[string]]::new()
$Seen  = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)

# Track parent→child relationships for traceability
$DiscoveredFrom = @{}

foreach ($Url in $SeedUrls) {
    if ($Seen.Add($Url)) {
        $Queue.Enqueue($Url)
        $DiscoveredFrom[$Url] = "seed"
    }
}

Write-Host "Seed URLs loaded: $($Queue.Count)"
```

### Step 2 — Recursive JavaScript Reference Discovery

**Purpose:** For every JavaScript file analyzed, inspect its contents to identify
references to other JavaScript resources. This step drives the recursive
discovery loop — every newly discovered file is queued and processed through the
same workflow, allowing the analysis to traverse the entire JavaScript dependency
graph until no new in-scope JavaScript files remain.

#### Reference Types to Identify

For each JavaScript file in memory, examine its contents for:

- **Static imports** — ES module `import ... from './file.js'`, bare
  `import './file.js'`, and CommonJS `require('./file.js')`.
- **Dynamic imports** — `import('./module.js')` and
  `` import(`./module-${name}.js`) `` expressions.
- **Dynamic script loading** — `.src = 'file.js'` and
  `` .src = `file-${key}.js` `` assignments, `document.createElement('script')`
  with a subsequent `.src` assignment, `$.getScript()`, `loadScript()`, and
  `injectScript()` calls.
- **Lazy-loaded chunks and code-split bundles** — Webpack chunk references
  (`__webpack_require__.e()`), Turbopack chunk references
  (`globalThis.TURBOPACK...push()`, `e.l()`), Next.js chunk references
  (`self.__next_s.push()`, `_next/static/` paths), and generic dynamic chunk
  loading with `chunkId` or `chunkFilename` properties.
- **Worker files** — `new Worker('file.js')`,
  `new SharedWorker('file.js')`, and
  `navigator.serviceWorker.register('file.js')`.
- **Injected scripts** — Script elements constructed in JavaScript strings,
  including `<script src="...">` tags inside HTML template literals.
- **Source maps** — `sourceMappingURL=` comments and
  `//# sourceMappingURL=` directives.
- **Asset manifests** — Manifest/chunk-map objects where keys and values
  reference `.js` files.
- **Embedded script URLs** — Absolute and relative `.js` URLs appearing in
  string literals and template literals.

#### Extraction Approach

Use regex patterns only as initial indicators to locate candidate references.
After a pattern match, **manually analyze the surrounding code** to reconstruct
dynamically generated URLs — including concatenated strings, template literals
with interpolated variables, path prefixes, and bundler runtime logic that
assembles URLs at load time. Do not blindly queue every regex match.

#### Queueing Criteria

Before adding any discovered JavaScript file to the processing queue, verify
that:

1. The URL belongs to the authorized target or an explicitly allowed subdomain.
2. The URL resolves to a JavaScript resource — either by a `.js` file extension
   or by a JavaScript content type (`application/javascript`,
   `text/javascript`, `application/x-javascript`) confirmed via a HEAD or GET
   request.
3. The URL has not already been seen or processed (check the `$Seen` set).
4. The URL is not an external third-party library or service outside the
   authorized scope.

#### Recursive Processing

Every newly discovered JavaScript file that passes the queueing criteria must be
added to the analysis queue and processed through this same reference discovery
workflow. This ensures the analysis recursively traverses the full dependency
graph — from the seed files the user provides, through every imported module,
dynamically loaded chunk, worker, and referenced script — terminating only when
no further in-scope JavaScript files remain.

### Step 3 — Resolve Relative URLs

Every extracted URL that is relative must be resolved against the parent file's
base URL before queueing:

```powershell
function Resolve-JsUrl {
    param([string]$ParentUrl, [string]$Candidate)
    # Already absolute
    if ($Candidate -match '^https?://') { return $Candidate }
    # Protocol-relative
    if ($Candidate -match '^//') {
        $proto = ([uri]$ParentUrl).Scheme
        return "$($proto):$Candidate"
    }
    # Root-relative (starts with /)
    if ($Candidate.StartsWith('/')) {
        $base = ([uri]$ParentUrl)
        return "$($base.Scheme)://$($base.Authority)$Candidate"
    }
    # Relative — resolve against the parent's directory
    $baseUri = [uri]$ParentUrl
    $resolved = [uri]::new($baseUri, $Candidate)
    return $resolved.AbsoluteUri
}
```

### Step 4 — Verify Discovered URLs Are JavaScript

Before queueing a candidate URL, perform a lightweight HEAD or GET request
to confirm it is actual JavaScript. Skip any URL that returns HTML, JSON,
an error page, or an empty body:

```powershell
function Test-IsJavaScript {
    param([string]$Url, [string]$Cookie)

    $headers = curl.exe -sS -k -L --connect-timeout 8 --max-time 20 `
      -I -A "Mozilla/5.0" -H "Cookie: $Cookie" $Url 2>$null

    $contentType = ($headers | Select-String -Pattern '(?i)content-type:\s*([^\r\n]+)').Matches.Groups[1].Value
    $status = ($headers | Select-String -Pattern '(?i)^HTTP\/[0-9.]+\s+(\d+)').Matches.Groups[1].Value

    # Accept recognized JavaScript MIME types and 200/304 status
    if ($contentType -match '(javascript|ecmascript)' -and $status -match '^(200|304)$') {
        return $true
    }
    # Also check URL extension as fallback
    if ($Url -match '\.js(\?|$)' -and $status -ne '404') {
        return $true
    }
    return $false
}
```

### Step 5 — The Discovery Loop

Process the queue breadth-first until empty. Record every accepted URL
in the global seen set and the discovery state file. Insert a small default
delay between requests proactively — don't wait to be throttled before
slowing down:

```powershell
$MaxDepth = 10         # Safety limit
$CurrentDepth = 0
$TotalDiscovered = $Queue.Count
$DiscoveryLog = @()
$RequestDelayMs = 250  # Proactive default delay between requests

while ($Queue.Count -gt 0 -and $CurrentDepth -lt $MaxDepth) {
    $BatchSize = $Queue.Count
    Write-Host "`n===== DISCOVERY DEPTH $CurrentDepth ($BatchSize URLs) ====="

    for ($i = 0; $i -lt $BatchSize; $i++) {
        $CurrentUrl = $Queue.Dequeue()
        $ShortUrl = $CurrentUrl -replace '^https?://[^/]+', ''
        Write-Host "  [$($i+1)/$BatchSize] $ShortUrl"

        Start-Sleep -Milliseconds $RequestDelayMs

        # Fetch into memory
        $JsContent = curl.exe -sS -k -L `
          --connect-timeout 10 --max-time 60 `
          -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" `
          -H "Cookie: $SessionCookie" `
          -H "Accept: */*" `
          $CurrentUrl 2>$null

        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($JsContent)) {
            Write-Host "    SKIP: empty or failed"
            continue
        }

        # Skip non-JavaScript responses
        if ($JsContent.Length -lt 50) { continue }
        if ($JsContent -match '^\s*<!DOCTYPE\s+html' -or
            $JsContent -match '^\s*<html') {
            Write-Host "    SKIP: HTML response"
            continue
        }

        # --- EXTRACT REFERENCES ---
        $NewUrls = @()

        # Import/require/dynamic import
        $importMatches = [regex]::Matches($JsContent,
            "(?:import\s*\(?\s*['""]|import\s+.*?\s+from\s+['""]|require\s*\(\s*['""])([^'""]+\.js)")
        foreach ($m in $importMatches) {
            $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value
        }

        # Dynamic script .src
        $srcMatches = [regex]::Matches($JsContent,
            '\.src\s*=\s*[''"]([^''"]+\.js)[''"]')
        foreach ($m in $srcMatches) {
            $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value
        }

        # getScript
        $gsMatches = [regex]::Matches($JsContent,
            '\$\.getScript\s*\(\s*[''"]([^''"]+\.js)[''"]')
        foreach ($m in $gsMatches) {
            $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value
        }

        # Workers
        $workerMatches = [regex]::Matches($JsContent,
            "(?:new\s+(?:Shared)?Worker|navigator\.serviceWorker\.register)\s*\(\s*['""]([^'""]+\.js)['""]")
        foreach ($m in $workerMatches) {
            $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value
        }

        # Turbopack chunk loading: e.l('chunk.js')
        $tpMatches = [regex]::Matches($JsContent,
            "e\.l\s*\(\s*['""]([^'""]+\.js)['""]")
        foreach ($m in $tpMatches) {
            $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value
        }

        # Next.js / Webpack chunk references
        $chunkMatches = [regex]::Matches($JsContent,
            "['""]([^'""]*_next\/static\/[^'""]+\.js)['""]")
        foreach ($m in $chunkMatches) {
            $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value
        }

        # Generic .js URLs in string literals
        $genericMatches = [regex]::Matches($JsContent,
            "['""](https?://[^'""]+\.js(?:\?[^'""]*)?)['""]")
        foreach ($m in $genericMatches) {
            $NewUrls += Resolve-JsUrl $CurrentUrl $m.Groups[1].Value
        }

        # Source maps
        $smMatches = [regex]::Matches($JsContent,
            'sourceMappingURL=([^\s\*]+)')
        foreach ($m in $smMatches) {
            $smUrl = Resolve-JsUrl $CurrentUrl $m.Groups[1].Value.Trim()
            $NewUrls += $smUrl
        }

        # Deduplicate and filter new URLs
        $NewUrls = $NewUrls | Sort-Object -Unique |
            Where-Object { $_ -and $Seen.Add($_) }

        # Verify each new URL is JavaScript before queueing
        foreach ($NewUrl in $NewUrls) {
            if ($NewUrl -notmatch $AuthorizedDomainPattern) {
                Write-Host "    SKIP (out of scope): $NewUrl"
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
    }

    $CurrentDepth++
}

Write-Host "`n===== DISCOVERY COMPLETE: $TotalDiscovered total unique URLs ====="
```

Respect `429 Too Many Requests` and any `Retry-After` header on top of the
proactive delay — increase `$RequestDelayMs` for the remainder of the run if
one is encountered.

### Step 6 — Save the Complete Discovery Index

Write the full sorted list of every discovered JavaScript URL to the output
file. Save the parent→child relationship map for traceability:

```powershell
# Build the URL index with all discovered URLs and their metadata
$UrlIndex = $Seen | Sort-Object | ForEach-Object {
    [PSCustomObject]@{
        url                = $_
        depth              = $CurrentDepth
        discovered_from    = $DiscoveredFrom[$_]
        discovery_order    = [array]::IndexOf([array]$Seen, $_)
        analysis_complete  = $false
    }
}

# Write to notes/discovery-index.json (merge if existing)
$IndexPath = "$Root\notes\discovery-index.json"
if (Test-Path $IndexPath) {
    $Existing = Get-Content $IndexPath -Raw | ConvertFrom-Json
    $Combined = @($Existing) + @($UrlIndex) | Sort-Object url -Unique
    $Combined | ConvertTo-Json -Depth 3 | Out-File -FilePath $IndexPath -Encoding UTF8
} else {
    $UrlIndex | ConvertTo-Json -Depth 3 | Out-File -FilePath $IndexPath -Encoding UTF8
}

Write-Host "Saved $TotalDiscovered URLs to $Root\notes\discovery-index.json"
```

### Step 7 — Deduplicate the URL Index

The `$Seen` HashSet prevents duplicates during discovery. As a final safeguard
after the loop completes, run an explicit deduplication pass on the discovery
index:

```powershell
$IndexPath = "$Root\notes\discovery-index.json"
$IndexData = Get-Content $IndexPath -Raw | ConvertFrom-Json
$Deduplicated = $IndexData | Sort-Object url -Unique
$Deduplicated | ConvertTo-Json -Depth 3 | Out-File -FilePath $IndexPath -Encoding UTF8
Write-Host "After deduplication: $($Deduplicated.Count) unique JavaScript URLs in notes/discovery-index.json"
```

### Step 8 — Extract Domains and Subdomains from JavaScript Content

After processing all JavaScript files in the discovery phase, scan every
response body held in memory for domain names and subdomains. Extract every
hostname that appears in URL strings, string literals, template literals, and
API endpoint references. The goal is to build a complete picture of all
domains and subdomains the application interacts with from the client side.

**Extraction approach:**

- Scan for absolute URLs (`https://`, `http://`, `//`) inside string
  literals, template literals, and concatenated strings across all
  JavaScript files.
- Extract the authority portion (hostname) from each discovered URL.
- Include subdomains explicitly referenced in API base URLs, WebSocket
  endpoints, redirect targets, image/video CDN URLs, and third-party
  integrations.
- Manually review each candidate — do not include domains from comment
  blocks, dead code, test fixtures, or example/documentation strings
  unless they represent real application dependencies.
- Deduplicate all discovered domains and subdomains into a sorted list.

Save the results to `notes\domains-in-javascript.txt`:

```powershell
$DomainFile = "$Root\notes\domains-in-javascript.txt"

# Collect from every JS response seen during discovery
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

    # Extract hostnames from absolute, protocol-relative, and template URLs
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
Write-Host "Domains/subdomains extracted: $($DomainSet.Count) -> $DomainFile"
```

Only record domains discovered from JavaScript content — do not add domains
derived solely from user-provided seed URLs or external knowledge.

### Discovery Guardrails

- **Maximum depth:** Stop at depth 10 (configurable). Each iteration of the
  outer while-loop is one depth level.
- **Domain filter:** Only queue URLs matching the authorized domain pattern.
  Skip third-party CDNs, analytics, and tracking scripts unless explicitly
  in scope.
- **Size check:** Skip responses under 50 bytes (these are empty shells,
  redirect bodies, or error pages).
- **Content-type check:** Skip HTML, JSON, XML, CSS, and image responses.
  Only queue JavaScript responses.
- **Deduplication:** The `$Seen` HashSet guards against re-processing any URL
  already discovered. URLs are compared case-insensitively.
- **Rate limiting:** Apply the proactive default delay (`$RequestDelayMs`)
  between every request, not just after a 429. Vercel and similar platforms
  may still rate-limit — increase the delay if you encounter 429s.

### What NOT to Queue

- Third-party analytics (Google Analytics, Segment, Amplitude, Mixpanel, etc.)
- Ad/tracking pixels
- CDN-hosted libraries from non-authorized domains (cdnjs, unpkg, jsdelivr) —
  note their name/version in `notes\dependencies.md` per Category 9
  without queueing them for full analysis
- Social media widgets
- Chat/intercom widgets from external providers
- URLs that return HTML error pages (Cloudflare blocks, 403, 404, login pages)

---

## Phase 3 — Retrieve JavaScript Without Saving It Locally

**Never download or save JavaScript files to disk.** Do not use `curl.exe -o`,
`curl.exe -O`, `Invoke-WebRequest -OutFile`, `Start-BitsTransfer`, or any other
mechanism that creates a local copy of a JavaScript response.

Retrieve each supplied JavaScript URL into memory and analyze the response
content directly:

```powershell
$JsUrl = "https://authorized.example/static/js/bundle.js"
$HeadersFile = Join-Path $env:TEMP "jsintel-headers.txt"

$JsContent = curl.exe -sS -k -L `
  --connect-timeout 10 `
  --max-time 60 `
  -A "Mozilla/5.0" `
  -D $HeadersFile `
  $JsUrl
```

The variable `$JsContent` is temporary working memory only. Do not write it to
any file. After analyzing that response, clear it before processing the next
URL:

```powershell
$JsContent = $null
Remove-Variable JsContent -ErrorAction SilentlyContinue
```

For each URL, record only metadata and analysis results:

| Field | How to obtain |
|---|---|
| Original URL | From input list |
| Final URL after redirects | From response headers |
| HTTP status | From response headers |
| Content-Type | From response headers |
| Content-Length | From headers or in-memory length |
| Character count | `$JsContent.Length` |
| Analysis timestamp | Current time |

Verify the response is actually JavaScript—not an HTML error page, JSON error,
access-denied page, redirect body, or empty response—before analyzing it.

Do not preserve raw JavaScript source in reports, logs, temporary directories,
or analysis files. Store only short evidence snippets that are necessary to
explain a finding, along with the URL and character offset.

---

## Phase 3.5 — File Triage and Prioritization

**Purpose:** Exhaustive reading of every discovered file is still required
(Phase 4), but real applications can produce dozens to hundreds of chunks —
much of it vendor/library code with no application logic. Triage decides
*sequencing and depth of attention*, not which files get skipped.

Before full reading, do a single lightweight pass over every file in
`notes\discovery-index.json` to compute a priority score and record it in
`notes\triage.json`:

1. **Filename/path signal.** Boost priority for URLs or webpack chunk names
   containing terms like `admin`, `auth`, `login`, `account`, `billing`,
   `payment`, `checkout`, `internal`, `settings`, `user`, `profile`, `api`,
   `config`, `dashboard`. These are far more likely to contain endpoint logic,
   secrets, or access-control checks than a shared UI-component chunk.
2. **Size and uniqueness signal.** Very large chunks that are near-identical
   to a well-known vendor bundle (React, lodash, moment, chart libraries —
   detectable by license-header comments or characteristic top-level function
   names) are lower priority for line-by-line reading, but still get a pass
   for Category 9 (dependency version) and a secrets sweep, since bundled
   vendor code can still contain accidentally-inlined config or keys.
3. **Reference fan-in/fan-out.** Files referenced by many other files (shared
   utility/API-client modules) or that reference many endpoints get boosted —
   they're more likely to be the request-building or auth core.
4. **Entry points.** Seed files provided directly by the user and any file
   named like a main bundle (`main.*.js`, `app.*.js`, `index.*.js`) are always
   high priority.

Record the score and reasoning per file:

```json
{
  "url": "https://authorized.example/static/js/admin.a1b2.js",
  "priority": "high",
  "signals": ["path contains 'admin'", "referenced by main bundle"],
  "read_status": "pending"
}
```

Process files in priority order (high → medium → low). This changes *when*
and *how carefully* each file is read, not whether it's read — every file in
the index must still reach `read_status: complete` per Phase 4's full-read
requirement before the engagement is considered finished. Note in the final
report if time or scope constraints meant lower-priority files received a
lighter pass; do not silently omit them.

---

## Phase 4 — Read Every JavaScript Response Completely

Every JavaScript response must be read **in full from memory**. Do not analyze
only the first lines, regex matches, or selected strings. Process files in
the priority order established in Phase 3.5.

For multi-line content:

```powershell
$Lines = $JsContent -split "`r?`n"
$Lines.Count
$Lines | Select-Object -First 500
$Lines | Select-Object -Skip 500 -First 500
```

For minified single-line content, read it sequentially in character chunks:

```powershell
$ChunkSize = 12000
for ($Offset = 0; $Offset -lt $JsContent.Length; $Offset += $ChunkSize) {
    $Length = [Math]::Min($ChunkSize, $JsContent.Length - $Offset)
    "`n===== OFFSET $Offset =====`n"
    $JsContent.Substring($Offset, $Length)
}
```

When identifier mangling makes tracing a call to its class constructor and
inherited prefixes error-prone by eye (see Category 2's reconstruction
requirement), use a deterministic AST parse to mechanically locate the
constructor and parent-class chain (see "Permitted Parsing Aids" above),
then read and interpret those located lines manually — the parse output is a
navigation aid, not a substitute for understanding what the code does.

Maintain structured notes while moving through the complete in-memory response.
Track unresolved functions, classes, prefixes, request builders, and imported
modules so they can be revisited when later code explains their purpose.

Never save a reformatted, beautified, minified, or original JavaScript copy to
disk. The HTTP response currently held in memory is the source of truth.

---

## Phase 5 — Build a Mental Model

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

## Phase 6 — Nine Security Analysis Categories

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

**Reconstruct complete endpoints from functions, classes, prefixes, inherited
request clients, and string fragments. Never assume that the route literal shown
inside a method is the complete endpoint.**

For every request-producing method:

1. Identify the method name and its arguments.
2. Find the request helper it calls, such as `sendRequest`, `request`, `fetch`,
   `axios`, a generated SDK client, or an inherited base-class method.
3. Find the class constructor and all class properties such as `pathPrefix`,
   `basePath`, `baseUrl`, `resource`, `servicePath`, or `apiVersion`. If
   identifier mangling makes this hard to trace by eye, use an AST-based
   call-graph trace (see "Permitted Parsing Aids") to locate the constructor
   and property assignments, then read them manually.
4. Trace inherited constructors and parent classes to determine additional
   prefixes, including a global `/api` prefix.
5. Resolve imported constants, configuration objects, template literals,
   concatenation, array joins, and computed properties.
6. Combine the pieces in execution order:
   `global API prefix + class pathPrefix + method route + path parameters + query parameters`.
7. Confirm the reconstructed route by comparing sibling methods that use the
   same request helper or class.
8. Record both the literal fragment and the reconstructed complete endpoint.

Example 1:

```javascript
async me(e) {
    return this.sendRequest("GET", "/me", null, [], false, e)
}
constructor(...e) {
    super(...e)
    this.pathPrefix = "/user"
}
```

If the inherited request client adds `/api`, reconstruct:

```text
Literal method route: /me
Class prefix:         /user
Global API prefix:    /api
Complete endpoint:    GET /api/user/me
```

Example 2:

```javascript
async superAccount(e, t) {
    return this.sendRequest(
        "GET",
        "/super_account",
        null,
        [["superId", e]],
        false,
        t
    )
}
constructor(...e) {
    super(...e)
    this.pathPrefix = "/user"
}
```

Reconstruct and record:

```text
GET /api/user/super_account?superId={superId}
```

Do not incorrectly report only `/me` or `/super_account`.

Also inspect generated SDK patterns where the request helper constructs URLs
outside the visible method. Search for definitions and assignments involving:

```text
sendRequest          pathPrefix          basePath
baseURL              apiPrefix           servicePrefix
resourcePath         buildUrl            createRequest
requestConfig        endpointMap         routeMap
```

If a helper cannot be fully resolved, report multiple clearly labeled layers:

```text
Observed route fragment: /me
Resolved class prefix: /user
Probable global prefix: /api
Best reconstructed endpoint: /api/user/me
Confidence: High
Unresolved dependency: inherited sendRequest implementation
```

For each endpoint record: source URL, character offset, containing class,
method/function name, request helper, HTTP method, observed route fragment,
class prefix, inherited/global prefix, complete normalized endpoint, dynamic
path variables, query parameters, headers, auth requirements, request body,
calling UI feature, expected response, privilege context, and reconstruction
confidence.

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

Record every parameter/field identified here in `parameter.json` (one entry
per parameter, deduplicated on parameter name + endpoint).

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

Retrieve the source map into memory without saving it:
```powershell
$MapUrl = "https://authorized.example/static/js/main.123.js.map"
$MapContent = curl.exe -sS -k -L $MapUrl
```

Verify: HTTP status, Content-Type, valid JSON, `sources`, `sourcesContent`,
`names`, `sourceRoot`, webpack paths, original filenames, comments, internal
endpoints, developer notes, potential secrets.

Parse directly from memory:
```powershell
$Map = $MapContent | ConvertFrom-Json
$Map.sources
$Map.sourceRoot
$Map.sourcesContent.Count
```

Do not save the `.map` response or embedded `sourcesContent` to disk. Analyze
embedded source content in memory and retain only structured findings and short
evidence snippets.

If `sourcesContent` is present, analyze every embedded source file using the
same nine categories. A publicly accessible source map is not automatically a
vulnerability — report impact based on sensitive content actually exposed.

### Category 9: Known-Vulnerable Bundled Dependencies

Bundled third-party libraries (React, jQuery, lodash, moment, chart/PDF/date
libraries, polyfills, analytics SDKs) ship with a specific version baked into
the bundle, and older versions can carry publicly known vulnerabilities. This
is a read-only identification step, not exploitation.

For each file (including large vendor chunks deprioritized for line-by-line
reading in Phase 3.5):

1. Extract library name/version signals: webpack module comment headers
   (`/*! package-name v1.2.3 */`), license banners, `package.json` fragments
   sometimes inlined by bundlers, distinctive version-string constants
   (e.g. `VERSION = "1.2.3"` near a recognizable library's characteristic code).
2. Record each `{library, version, source_file}` triple in
   `notes\dependencies.md` — do not guess a version from partial
   evidence; mark it `unresolved` if it can't be confirmed.
3. Cross-reference extracted name/version pairs against publicly known CVEs
   for that library and version (e.g. via a vulnerability database lookup, if
   available in the environment, or general knowledge of well-known CVEs for
   that name/version). This is deterministic lookup against known public
   advisories, not a live exploit scan — do not attempt to trigger or confirm
   exploitability against the target from this step.
4. Report matches as `Informational` or `Low/Medium confidence` findings
   depending on whether the vulnerable code path is actually reachable in how
   the application uses the library — a vulnerable version with an unused
   function is a different risk than one whose vulnerable function is called
   with attacker-influenced input. Do not escalate confidence without tracing
   actual usage.

---

## Phase 7 — Endpoint and Route Normalization

Deduplicate while preserving evidence. Normalize `/api/users/123` and
`/api/users/456` into `/api/users/{id}`. Do not merge routes that may have
different meanings.

Store each endpoint in `endpoint.json` as JSON:
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

## Phase 8 — Controlled Adaptive Exploration

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

## Phase 9 — Request Variations and Error Analysis

When endpoints behave unexpectedly, reason from: HTTP status, response body,
response headers, redirect target, Content-Type, response length, timing
differences, allowed methods, auth state, role differences, error messages,
validation messages.

Use limited variations: GET vs HEAD, GET vs OPTIONS, with/without optional
parameter, valid vs invalid test ID, authenticated vs unauthenticated, owner
vs viewer account, expected vs omitted Content-Type.

Do not fuzz indiscriminately. Apply the proactive default delay between
attempts and retry up to 3 times for transient failures:
```powershell
for ($attempt = 1; $attempt -le 3; $attempt++) {
    curl.exe -sS -k -i --connect-timeout 10 --max-time 30 "https://authorized.example/api/example"
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
}
```
Respect `429 Too Many Requests` and `Retry-After`.

---

## Phase 10 — Evidence Requirements

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

## Phase 11 — Findings Report Format

Write the consolidated report to `notes\final-report.md` (the only report
output — there is no separate reports/ directory). Per-file notes and
findings are recorded in `notes\` as they are discovered; the final report
aggregates them.

### Executive Summary

Number of JS files analyzed, total size, source maps discovered, endpoints
extracted/tested, hidden parameters, potential secrets, bundled dependencies
with known-CVE matches, confirmed findings, items requiring browser
validation, items not tested due to scope/safety, any files that received a
lighter (triage-limited) pass rather than full manual reading.

### Per-File Analysis Template

```markdown
## File: main.123.js
- Original URL:
- Source URL:
- Response size:
- Character count:
- Triage priority:
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

Then list results for all 9 categories (including "No finding" where
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

### Dependency Table
```
| Library | Version | Source File | Known CVEs | Usage Reachable | Confidence |
```

---

## Required Behavior

**You must:**
1. Start from user-provided JavaScript files and recursively discover every
   additional JS file (imports, chunks, dynamic loads, workers, source maps)
   until no new files are found.
2. Verify each discovered URL is JavaScript before queueing. Skip HTML, JSON,
   error pages, and third-party scripts outside scope.
3. Resolve all relative URLs against parent file URLs. Remove duplicates.
4. Save the complete discovered URL list to `notes\discovery-index.json`.
5. Triage files by priority signal before full reading, but still read every
   file completely — triage changes order and depth of attention, never
   whether a file gets read.
6. Read every file completely.
7. Understand the code's purpose before classifying findings.
8. Reconstruct dynamically assembled URLs and request bodies.
9. Correlate related logic across multiple files.
10. Separate evidence from assumptions, exposure from exploitability,
    client-side behavior from server-side authorization.
11. Test only authorized endpoints with non-destructive requests.
12. Redact credentials and sensitive data.
13. Record every request and result.
14. Clearly state what could not be validated.
15. Reconstruct endpoints by tracing request helpers, constructors, class
    prefixes, inherited base clients, and global API prefixes — using an AST
    parse as a navigation aid when mangled identifiers make manual tracing
    error-prone, then interpreting the located code manually.
16. Keep JavaScript and source-map bodies in memory only.
17. Include the source JavaScript filename or URL with every finding.
18. Apply a proactive default delay between requests rather than waiting to
    be rate-limited.
19. Extract and record bundled dependency name/version signals (Category 9)
    and cross-reference against known public CVEs, without attempting to
    exploit or confirm them against the live target.

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
11. Save, download, cache, beautify, or write JavaScript/source-map bodies to disk.
12. Report a route fragment as a complete endpoint before resolving its class
    and inherited request-building context.
13. Exclude the source JavaScript filename or URL from any finding.
14. Skip the recursive discovery phase — always discover additional JS files
    referenced by the seed files before beginning full analysis.
15. Use a vulnerability scanner, fuzzer, or exploit-signature tool to declare
    a finding. Parsing/lookup aids may locate candidate code or known-CVE
    matches; a human read and judgment call is still required before anything
    is reported as a finding.
16. Skip full reading of a file solely because triage marked it low priority
    — triage only affects sequencing, not coverage.

---

## Quick-Start PowerShell Workflow

Create only the `notes` directory — all outputs live under
`AnalyzingJavaScriptFiles/`:

```powershell
$Root = ".\bug-hunter\{main-domain}\{subdomain-name}\AnalyzingJavaScriptFiles"
foreach ($Dir in @(
    "$Root",
    "$Root\notes"
)) {
    New-Item -ItemType Directory -Path $Dir -Force | Out-Null
}
```

After Phase 2 (recursive discovery) and Phase 3.5 (triage), read the full
discovered URL index in priority order and process every file:

```powershell
$IndexData = Get-Content "$Root\notes\discovery-index.json" -Raw | ConvertFrom-Json
$TriageData = Get-Content "$Root\notes\triage.json" -Raw | ConvertFrom-Json -ErrorAction SilentlyContinue
$PriorityOrder = @{ "high" = 0; "medium" = 1; "low" = 2 }

$JsUrls = $IndexData | ForEach-Object { $_.url } |
    Where-Object { $_ -and -not $_.StartsWith("#") } |
    Sort-Object { $p = ($TriageData | Where-Object url -eq $_).priority; $PriorityOrder[$p] ?? 1 }

$RequestDelayMs = 250

foreach ($Url in $JsUrls) {
    Start-Sleep -Milliseconds $RequestDelayMs

    $JsContent = curl.exe -sS -k -L `
      --connect-timeout 10 `
      --max-time 60 `
      -A "Mozilla/5.0" `
      $Url

    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($JsContent)) {
        continue
    }

    # Analyze the complete content here without writing it to disk.
    $CharacterCount = $JsContent.Length

    # Use pattern matches only to navigate, then inspect complete surrounding logic.
    $Patterns = @(
        "pathPrefix", "basePath", "baseURL", "apiPrefix", "sendRequest",
        "sourceMappingURL", "addEventListener\s*\(\s*['""]message",
        "onmessage", "innerHTML", "outerHTML", "insertAdjacentHTML",
        "document\.write", "eval\s*\(", "localStorage", "sessionStorage",
        "FormData", "URLSearchParams", "fetch\s*\(", "axios",
        "XMLHttpRequest", "WebSocket", "/api/", "/internal/", "/admin/",
        "/graphql", "/\*!\s", "VERSION\s*="
    )

    foreach ($Pattern in $Patterns) {
        [regex]::Matches($JsContent, $Pattern)
    }

    $JsContent = $null
    Remove-Variable JsContent -ErrorAction SilentlyContinue
}
```

Never use `-o`, `-O`, `Out-File`, `Set-Content`, `Add-Content`, or
`[System.IO.File]::WriteAllText()` for JavaScript or source-map response bodies.

---

# Final Instruction

Begin with the JavaScript files the user provides. Use Phase 2 to recursively
discover every additional JavaScript file referenced within them — static imports,
dynamic imports, code-split chunks, worker files, source maps, and inline
JavaScript URLs — until no new files remain. Save the complete list to
`notes\discovery-index.json`. Triage the files by likely relevance (Phase 3.5),
then apply the full 9-category analysis (Phase 6) to every single discovered
file in priority order, ensuring every finding records its source JavaScript
filename or URL and that every file — regardless of triage priority —
ultimately receives a complete read.

Approach every JavaScript file as application intelligence, not as a collection
of regex matches. Read the full source. Understand what each module does.
Determine how data enters, is transformed, stored, and sent. Find behavior the
developer did not intend to expose — while keeping all testing authorized,
controlled, evidence-based, and non-destructive.
