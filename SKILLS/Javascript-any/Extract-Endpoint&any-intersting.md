---
name: js-secrets-scanner
description: |
  Use when analyzing JavaScript files for security recon — extracting API endpoints,
  leaked API keys, hardcoded passwords/auth tokens, cloud secrets (AWS, GCP, Firebase),
  internal IPs, database connection strings, webhooks, and authentication methods.
  Trigger on any task involving JS file analysis, secret scanning, endpoint discovery,
  or bug bounty recon.
---

# JS Secrets & Endpoint Scanner

## Background

Automates JavaScript file recon for bug bounty hunters and penetration testers.
Downloads JS bundles from a target domain, then systematically extracts:

- **API endpoints** (REST, GraphQL, WebSocket)
- **API keys & tokens** (Stripe, Firebase, AWS, GitHub, Slack, Discord, etc.)
- **Hardcoded credentials** (passwords, secrets, JWT tokens)
- **Cloud infrastructure** (S3 buckets, Firebase URLs, GCP resources)
- **Authentication methods** (Bearer, Basic, OAuth, JWT, custom auth)
- **Internal/private resources** (internal IPs, localhost references, staging URLs)
- **Webhooks & callbacks** (Slack, Discord, Stripe webhooks)
- **Database connection strings** (MongoDB, PostgreSQL, MySQL, Redis)

## Workflow

```
Target URL → JS File Discovery → Content Extraction → Pattern Analysis → Reports
```

## How to use

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\MSI\.opencode\skills\js-secrets-scanner\JS-Secrets-Scanner.ps1" -Target "https://example.com"
```

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `-Target` | **(required)** | Full target URL (e.g. `https://example.com`) |
| `-OutputDir` | `JS_Secrets_Results` | Directory to save results |
| `-DelayMs` | `500` | Delay between requests (ms) |
| `-Recursive` | `$false` | Follow JS file references from within JS files |
| `-UserAgent` | `Mozilla/5.0...` | Custom User-Agent string |

## What the scanner does

### Phase 1: JS Discovery
1. Fetches the target homepage and parses all `<script src="...">` tags
2. Extracts inline JavaScript from `<script>` blocks
3. Discovers JS files from source maps, import URLs, and dynamic imports
4. Downloads every JS file found

### Phase 2: Endpoint Extraction
Searches for URL patterns matching:
- `/api/`, `/v1/`, `/v2/`, `/v3/`, `/rest/`, `/graphql`
- `/auth`, `/login`, `/oauth`, `/token`
- `/admin`, `/config`, `/health`, `/status`, `/debug`
- `/internal`, `/private`, `/service`, `/gateway`, `/proxy`
- `/customer`, `/user`, `/account`, `/profile`
- `/search`, `/query`, `/webhook`, `/callback`
- `/upload`, `/download`, `/export`, `/import`
- `/ws`, `/socket`, `/stream`, `/events`

### Phase 3: Secret & Credential Scanning

| Pattern | What it finds |
|---|---|
| `AIza[0-9A-Za-z-_]{35}` | Firebase API keys |
| `sk_live_` / `sk_test_` / `pk_live_` / `pk_test_` | Stripe API keys |
| `AKIA[0-9A-Z]{16}` | AWS Access Keys |
| `-----BEGIN (RSA|EC|DSA) PRIVATE KEY-----` | Private keys / certs |
| `ghp_` / `gho_` / `ghu_` / `ghs_` / `ghr_` | GitHub tokens |
| `xox[baprs]-` | Slack tokens/bots |
| `discord(_app)?_secret` / Discord webhook URLs | Discord secrets |
| `https://hooks.slack.com/` | Slack webhooks |
| `https://[^"]+\.firebaseio\.com` | Firebase databases |
| `mongodb://` / `mongodb+srv://` | MongoDB connection strings |
| `postgresql://` / `postgres://` | PostgreSQL connection strings |
| `mysql://` / `mariadb://` | MySQL/MariaDB connection strings |
| `redis://` / `rediss://` | Redis connection strings |
| `amqp://` / `rabbitmq://` | Message queue connections |
| `(password\|passwd\|pwd)\s*[:=]\s*["'][^"']+["']` | Hardcoded passwords |
| `(secret\|api_key\|apikey)\s*[:=]\s*["'][^"']+["']` | Generic secrets/keys |
| `Bearer\s+([A-Za-z0-9\-._~+/]+=*)` | Bearer / JWT tokens |
| `Basic\s+[A-Za-z0-9+/]+=` | Basic auth credentials (Base64) |
| `10\.\d{1,3}\.\d{1,3}\.\d{1,3}` | Internal IPs (RFC 1918) |
| `192\.168\.\d{1,3}\.\d{1,3}` | Local network IPs |
| `172\.(1[6-9]\|2[0-9]\|3[01])\.\d{1,3}\.\d{1,3}` | Docker/internal IPs |
| `localhost[:/]` | Localhost references |
| `([a-z0-9-]+\.ngrok\.io)` | Ngrok tunnels (dev exposures) |
| `([a-z0-9-]+\.s3\.amazonaws\.com)` | S3 bucket URLs |
| `s3://[a-z0-9-]+` | S3 bucket paths |
| `https://[^"]*\.cloudfront\.net` | CloudFront distributions |
| `https://[^"]*\.execute-api\.[^"]+\.amazonaws\.com` | API Gateway endpoints |
| `(jwt\|JWT)\s*[:=]\s*["'][A-Za-z0-9\-_.]+["']` | JWT tokens |
| `eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+` | Raw JWT tokens |

### Phase 4: Auth Method Detection
Identifies how the application authenticates with APIs:
- `Authorization: Bearer` — token-based auth
- `Authorization: Basic` — basic auth (base64)
- `Authorization: Digest` — digest auth
- `x-api-key` / `X-API-Key` — custom header auth
- `x-auth-token` — custom token auth
- `oauth` / `OAuth` — OAuth flows
- `jwt` / `JWT` — JSON Web Tokens
- `cookie` / `Cookie` — cookie/session based auth
- `firebase` — Firebase Auth references

### Phase 5: Reporting
Generates multiple output files:

**`endpoints.csv`** — All discovered API endpoints
| Column | Meaning |
|---|---|
| `SourceFile` | JS file where endpoint was found |
| `Endpoint` | The extracted URL or path |
| `EndpointType` | REST, GraphQL, WebSocket, Admin, etc. |
| `Context` | Surrounding code snippet (50 chars) |

**`secrets.csv`** — All discovered secrets and credentials
| Column | Meaning |
|---|---|
| `SourceFile` | JS file where secret was found |
| `SecretType` | e.g. API Key, Password, JWT, AWS Key, Stripe Key |
| `Value` | The leaked secret (truncated) |
| `Context` | Surrounding code snippet (50 chars) |
| `Severity` | Critical / High / Medium / Low |

**`auth_methods.csv`** — Detected authentication methods
| Column | Meaning |
|---|---|
| `SourceFile` | JS file where auth method was found |
| `AuthType` | Bearer, Basic, API Key, OAuth, JWT, etc. |
| `Value` | The auth value or pattern found |
| `Context` | Surrounding code snippet (50 chars) |

**`summary.json`** — Consolidated JSON summary of all findings

## Reading results

- **Severity: Critical** — Private keys, cloud credentials, database passwords, JWT tokens with signatures
- **Severity: High** — API keys for paid services (Stripe, AWS, etc.), hardcoded passwords, internal IPs
- **Severity: Medium** — Bearer tokens, Firebase URLs, S3 bucket references, internal endpoints
- **Severity: Low** — Auth header patterns, generic API endpoints, localhost references

## Example

```powershell
# Basic scan
powershell -ExecutionPolicy Bypass -File "C:\Users\MSI\.opencode\skills\js-secrets-scanner\JS-Secrets-Scanner.ps1" -Target "https://target.com"

# Slow scan to avoid rate limits
powershell -ExecutionPolicy Bypass -File "C:\Users\MSI\.opencode\skills\js-secrets-scanner\JS-Secrets-Scanner.ps1" -Target "https://api.target.com" -DelayMs 1500 -OutputDir "target_scan_results"

# Recursive scan (follows JS imports)
powershell -ExecutionPolicy Bypass -File "C:\Users\MSI\.opencode\skills\js-secrets-scanner\JS-Secrets-Scanner.ps1" -Target "https://target.com" -Recursive

# Custom user agent
powershell -ExecutionPolicy Bypass -File "C:\Users\MSI\.opencode\skills\js-secrets-scanner\JS-Secrets-Scanner.ps1" -Target "https://target.com" -UserAgent "Mozilla/5.0 (compatible; MyScanner/1.0)"
```

## Notes

- This scanner is **read-only** — it only sends GET requests and never modifies anything on the target
- Increase `-DelayMs` to 1000+ for targets with aggressive rate limiting
- False positives are possible — always manually verify findings, especially for generic patterns
- Use the `.context` columns in output CSVs to understand how each match is used in code
- The scanner does NOT execute JavaScript — it only performs static analysis
- For recursive mode, the scanner follows `import()`, `require()`, and source map URLs within JS files
- Export results to share with your team or import into bug bounty tracking tools
