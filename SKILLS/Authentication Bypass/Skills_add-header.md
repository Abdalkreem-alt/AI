# JS Endpoint Discovery + Auth Bypass Scanner

## Background

This technique automates the recon methodology from HackerOne Report **#3538333** (AT&T, Critical, $3,000 bounty) — where sending a malformed `Authorization: Basic` header with no credentials bypassed authentication on multiple API endpoints.

## Workflow

```
Domain → JS Files → Endpoint Extraction → Auth Bypass Testing → Results
```

## How to use

```powershell
# Replace "target.com" with your target domain:
powershell -ExecutionPolicy Bypass -File "C:\Users\MSI\JS-Endpoint-AuthBypass-Scanner.ps1" -Domain "target.com" -DelayMs 300 -OutputFile "target_results.csv"
```

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `-Domain` | **(required)** | Target domain (e.g. `api.example.com`) |
| `-OutputFile` | `auth_bypass_results.txt` | CSV file to save results |
| `-DelayMs` | `500` | Delay between requests (ms) — increase to avoid rate limits |
| `-Https` | `$true` | Use HTTPS (set `-Http:$true` for HTTP) |

## What the scanner does

1. **Fetches the homepage** — downloads the HTML of the target domain
2. **Extracts all JS file URLs** — parses `<script src="...">` tags
3. **Downloads each JS file** — fetches all JavaScript bundles
4. **Extracts API endpoints** — searches for URL-like strings matching API keywords (`api`, `v1`, `auth`, `service`, `admin`, `customer`, `config`, `gateway`, `graphql`, etc.)
5. **Tests 3 auth bypass variants** on each endpoint:
   - `Authorization: Basic` (empty value)
   - `Authorization: Basic ` (trailing space)
   - `Authorization:` (empty header)
6. **Reports results** — identifies which endpoints returned 2xx instead of 4xx

## Reading results

The CSV output contains:

| Column | Meaning |
|---|---|
| `Endpoint` | The path extracted from JS |
| `FullUrl` | Full URL tested |
| `BaselineStatus` | HTTP status without any auth header |
| `BasicStatus` | HTTP status with the malformed header |
| `Bypass` | `YES` if authentication was bypassed |

### Expected behavior

- `BaselineStatus: 401` + `BasicStatus: 200` = **Auth bypass found** (vulnerability)
- `BaselineStatus: 200` + `BasicStatus: 200` = Endpoint is already public (no bypass)
- `BaselineStatus: 404` = Endpoint doesn't exist or path changed

## Example

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\MSI\JS-Endpoint-AuthBypass-Scanner.ps1" -Domain "dynamicdefense-testa.att.com" -DelayMs 1000 -OutputFile "att_results.csv"
```

## Notes

- Add `-DelayMs 1000+` for targets with aggressive rate limiting
- The scanner only sends GET requests — it does **not** send POST/PUT/DELETE to avoid impacting production systems
- False positives are possible; manually verify any bypasses found using:
  ```
  curl.exe -H "Authorization: Basic" "https://target.com/api/endpoint"
  ```
