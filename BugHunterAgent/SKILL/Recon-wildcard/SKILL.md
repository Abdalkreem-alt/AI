---
name: recon-wildcard
description: Wildcard-scope subdomain reconnaissance — combines subfinder/SecurityTrails/Shodan enumeration with recursive JS-driven subdomain discovery, httpx-based live filtering, sensitive-file/secret discovery in JS, technology fingerprinting, and API-surface mapping per host. Used by the RECON agent when scope_type is `wildcard`.
---

# Recon — Wildcard Scope
Full asset discovery from nothing to a prioritized URL list ready for hunting.

## Purpose

Build the fullest possible subdomain map of a wildcard-scope target, then progressively enrich every live subdomain with liveness data, technology fingerprints, exposed sensitive data, and API endpoint surface — using each discovery to drive further discovery.

## Output Directory

All output for this skill lives under:
```
engagements/<target-slug>/Recon/Wildcard/
```


---

## API Keys

This skill authenticates to SecurityTrails and Shodan. Keep this file private (do not commit it to a public repo) since these are live credentials.

```env
SHODAN_API_KEY=v4Idajo90aBTOcPKJbC2TnmcQCa5Y2P7
SECURITYTRAILS_API_KEY=3a4h4jZYUihLBilEU3oEhCbowm5wc5Ax
```

---

## Stage 1 — Subdomain Discovery (4 combined sources + 1 recursive technique)

Combine these sources rather than relying on any single one:

1. **subfinder** — passive subdomain enumeration
2. **SecurityTrails** — historical/passive DNS-based subdomain data (use `SECURITYTRAILS_API_KEY` above)
3. **Shodan** — subdomain/host discovery via indexed data (use `SHODAN_API_KEY` above)
4. **crt.name** — Certificate Transparency-based subdomain search, no key required:
   ```url
   https://crt.name/v1/search?apex=<main-domain>
   ```
   Returns the indexed subdomains for the given apex domain directly.
```bash
TARGET="target.com"

# Step 0: Passive — crt.name certificate transparency (no API key needed)
curl -s "https://crt.name/v1/search?apex=<main-domain>" | tee -a  /engagements/<target-slug>/Recon/Wildcard/subdomain.txt

# Step 1: subfinder (passive multi-source)
subfinder -d $TARGET -silent | anew /engagements/<target-slug>/Recon/Wildcard/subdomain.txt
assetfinder --subs-only $TARGET | anew /engagements/<target-slug>/Recon/Wildcard/subdomain.txt


# Step 4: URL crawl
cat /engagements/<target-slug>/Recon/Wildcard/filter-allInfo.txt | awk '{print $1}' | katana -d 3 -jc -kf all -silent | anew /engagements/<target-slug>/Recon/Wildcard/urls.txt

# Step 5: Historical URLs
echo $TARGET | waybackurls | anew /engagements/<target-slug>/Recon/Wildcard/urls.txt
gau $TARGET --subs | anew /engagements/<target-slug>/Recon/Wildcard/urls.txt

# Step 6: Nuclei scan
nuclei -l /engagements/<target-slug>/Recon/Wildcard/filter-allInfo.txt -t ~/nuclei-templates/ -severity critical,high,medium -o /engagements/<target-slug>/Recon/Wildcard/nuclei.txt
```

### recursive technique

**5. JS-driven subdomain discovery (recursive):** For every domain already found — from the four sources above, or from a previous pass of this same technique — pull its JavaScript files and search them for references to the main domain. Example: if the main domain is `att.com`, search each JS file for any `*.att.com` reference. Any subdomain surfaced this way (e.g. `subdomain.att.com`) that isn't already in the list gets added.

This technique is recursive by design: each newly discovered subdomain gets its own JS files pulled and searched the same way, which can surface still more subdomains. Keep repeating until no new subdomains appear through this method.

**End of Stage 1 — dedup requirement:** After collecting all subdomains and completing the first phase, verify that there are no duplicate subdomains in the subdomain.txt file.

**Output:**
```
engagements/<target-slug>/Recon/Wildcard/subdomain.txt
```
(deduplicated, one unique subdomain per line)

---

## Stage 2 — Live Filtering (httpx)

Run httpx twice against the same subdomain list.

**2a. Full metadata pass:**
```bash
cat /engagements/<target-slug>/Recon/Wildcard/subdomain.txt | dnsx -silent | httpx -silent -status-code -title -tech-detect | tee -a /engagements/<target-slug>/Recon/Wildcard/filter-allInfo.txt
```
Output:
```
engagements/<target-slug>/Recon/Wildcard/filter-allInfo.txt
```


---

## Stage 3 PORT SCANNING (often skipped — don't skip)

This stage involves scanning all active subdomains (`/engagements/<target-slug>/Recon/Wildcard/filter-allInfo.txt`) that have important ports open.

```bash
# naabu — fast port scanner from ProjectDiscovery
# Finds non-standard ports: 8080, 8443, 3000, 8888, 9000, etc.
cat /engagements/<target-slug>/Recon/Wildcard/filter-allInfo.txt | awk '{print $1}' | naabu -port 80,443,8080,8443,3000,4000,5000,8000,8888,9000,9090,9200,6379 -silent | tee /engagements/<target-slug>/Recon/Wildcard/open-ports.txt

# Why this matters: admin panels, debug services, internal APIs often run on alt ports
# Example wins: :8080/actuator/env (Spring Boot), :9200/_cat/indices (Elasticsearch), :6379 (Redis)
```

**Output**

Record any host that has an active port at the following path: `/engagements/<target-slug>/Recon/Wildcard/Intersting-Host-Port.txt`


---

## Stage 4 — Sensitive File & Secret Discovery in JS

For every live host (status 200, 301, or 302), pull its JavaScript files and check for references to sensitive files — `.env`, `.config`, and similar — plus any other sensitive material such as API keys.

**Validation rule:** a finding must be verified before it's recorded, not just pattern-matched — e.g. confirm the referenced file is actually reachable/exposed, or that a matched string is a genuine key format rather than a placeholder or example value.

**Output:**
```
engagements/<target-slug>/Recon/Wildcard/sensitive-data.txt
```

---

## Stage 5 — Technology & Function Mapping

For every live host, fingerprint the technology stack — frameworks, CDNs, WAFs, server software, and versions where identifiable — and link that fingerprint to the endpoints already discovered for that host.

5.a At this stage, you can use the WhatWeb tool:
```bash
whatweb -i engagements/<target-slug>/Recon/Wildcard/filter-allInfo.txt
```

5.b  TECH STACK DETECTION (2 min)
You can also rely on logical analysis for each subdomain; for instance, with WordPress, you will find that the source code contains a path such as `/wp-content/`

```bash
# Response headers reveal backend
curl -sI https://target.com | grep -iE "server|x-powered-by|x-aspnet|x-runtime|x-generator"

# Common signals:
# Server: nginx + X-Powered-By: PHP/7.4 → PHP backend
# Server: gunicorn OR X-Powered-By: Express → Python/Node.js
# X-Powered-By: ASP.NET → .NET
# Server: Apache Tomcat → Java
# X-Runtime: Ruby → Ruby on Rails

# Framework from JS bundle paths:
# /_next/static/ → Next.js
# /static/js/main.chunk.js → CRA (React)
# /packs/ → Ruby on Rails + Webpacker
# /__nuxt/ → Nuxt.js (Vue)
```

### Stack → Primary Bug Class Map

| Stack | Hunt First | Hunt Second |
|---|---|---|
| Ruby on Rails | Mass assignment | IDOR (`:id` routes) |
| Django | IDOR (ModelViewSet, no object perms) | SSTI (mark_safe) |
| Flask | SSTI (render_template_string) | SSRF (requests lib) |
| Laravel | Mass assignment ($fillable) | IDOR (Eloquent, no ownership) |
| Express (Node.js) | Prototype pollution | Path traversal |
| Spring Boot | Actuator endpoints (/actuator/env) | SSTI (Thymeleaf) |
| ASP.NET | ViewState deserialization | Open redirect (ReturnUrl) |
| Next.js | SSRF via Server Actions | Open redirect via redirect() |
| GraphQL | Introspection → auth bypass on mutations | IDOR via node(id:) |
| WordPress | Plugin SQLi | REST API auth bypass |

**Output (JSON, per host):**
```
engagements/<target-slug>/Recon/Wildcard/frameworksInfo.json
```

Example structure:
```json
{
  "subdomain.att.com": {
    "framework": "...",
    "cdn": "...",
    "waf": "...",
    "server": "...",
    "versions_detected": ["..."],
    "linked_endpoints": ["..."]
  }
}
```

---

## Stage 6 — API Spec / Swagger / OpenAPI Discovery (2024-2026 surface)

API spec endpoints are the single highest-leverage recon target on any modern .NET / Node / Python / Java backend. The spec discloses every endpoint, HTTP methods, parameter names + types + formats, models, validation rules — a complete attack-map in JSON. Default routes are commonly left enabled in production. Add this wordlist to the directory-fuzzing phase.

You will take the live subdomains found in the `filter-allInfo.txt` file and perform fuzzing against all the wordlists listed below.

### 6.a Default discovery path wordlist 
```
# NSwag / Swashbuckle (ASP.NET Core)
/swagger
/swagger/
/swagger/index.html
/swagger/ui/index.html
/swagger/v1/swagger.json
/swagger/v2/swagger.json
/swagger/v3/swagger.json
/swagger/docs/v1
/swagger/docs/v2
/swagger-ui
/swagger-ui/
/swagger-ui.html
/swagger-resources
/swagger-resources/configuration/ui
/nswag
/nswag/index.html
/api/swagger
/api/swagger.json
/api/swagger/v1/swagger.json
/api/openapi
/api/openapi.json
/api/v1/swagger.json
/api/v2/swagger.json
/api-docs
/api-docs/swagger.json

# OpenAPI generic
/openapi
/openapi.json
/openapi.yaml
/openapi.yml
/openapi/v1.json
/openapi/v2.json
/openapi/v3.json
/.well-known/openapi.json

# Java / Spring (Springfox / springdoc)
/v2/api-docs
/v3/api-docs
/v3/api-docs.yaml
/v3/api-docs/swagger-config
/swagger-ui/index.html

# Python (FastAPI / Flask-RESTPlus / Connexion / DRF)
/docs
/docs/
/redoc
/redoc/
/openapi.json
/swagger.json
/swagger/?format=openapi
/swagger.yaml

# Express / Node / Hapi
/api-docs
/api-docs.json
/swagger.json
/swagger-stats
/graphql-docs

# GraphQL adjacent (often co-located)
/graphql
/graphiql
/playground
/altair
/voyager
/graphql/console
/graphql-explorer

# ReDoc / RapiDoc / Stoplight / alt UIs
/redoc
/redoc.html
/redoc-ui.html
/rapidoc
/rapidoc.html
/stoplight
/elements

# Misc / dev-leftover
/actuator
/actuator/openapi
/actuator/mappings
/q/openapi
/q/swagger-ui
/docs/swagger.json
/api/v1/docs
/api/v2/docs
/internal/swagger
/admin/swagger
/management/swagger
```
### 6.b Tools

- `kiterunner` — natively ingests OpenAPI spec, generates requests against the API.
- `sj` (Swagger Jacker) — purpose-built for Swagger spec exploitation.
- `apidetector` (brinhosa) — Swagger-UI mass scanner.
- `XSSwagger` (vavkamil) — detects vulnerable Swagger UI versions (CVE-2018-25031 family).
- `nuclei -t http/exposures/apis/` — built-in templates for default spec paths.

### 6.c Reminder and Note

- A 404/403 on `/swagger` does NOT mean no spec is exposed. Many .NET projects route the spec under `/api/swagger/v1/swagger.json` rather than `/swagger`. Always test the full path list, not just the root.
- Furthermore, simply receiving a 200, 301, or 302 status code does not necessarily mean the resource was successfully accessed; sometimes, a 200 status code might actually indicate an error page. Therefore, you should verify that every page you reach contains API documentation or an API endpoint.

**Output:**
```
engagements/<target-slug>/Recon/Wildcard/api-Hosts.txt
```
Format: host followed by its discovered API endpoint(s).

This file becomes the primary input for authentication/authorization testing later in HUNT — every host/endpoint pair recorded here is a candidate for access-control testing.

---

## Non-Negotiable Rules

- **Never stop after finding something interesting.** A finding is a lead, not a stopping point — dig further from it.
- **Subdomain discovery is recursive, not one-pass.** Every new subdomain found through JS analysis gets its own JS files pulled and searched the same way — keep going as long as new subdomains keep appearing.
- **Never report suspected sensitive data as confirmed without validation.** Unverified matches stay out of `sensitive-data.txt` — or are clearly marked unverified, never merged in with confirmed findings.
