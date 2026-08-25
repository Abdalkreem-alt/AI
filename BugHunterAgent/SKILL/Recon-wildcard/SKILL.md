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

```
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
   ```
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
cat /tmp/live.txt | awk '{print $1}' | katana -d 3 -jc -kf all -silent | anew /tmp/urls.txt

# Step 5: Historical URLs
echo $TARGET | waybackurls | anew /tmp/urls.txt
gau $TARGET --subs | anew /tmp/urls.txt

echo "[+] Total URLs: $(wc -l < /tmp/urls.txt)"

# Step 6: Nuclei scan
nuclei -l /tmp/live.txt -t ~/nuclei-templates/ -severity critical,high,medium -o /tmp/nuclei.txt
```

**5. JS-driven subdomain discovery (recursive):** For every domain already found — from the four sources above, or from a previous pass of this same technique — pull its JavaScript files and search them for references to the main domain. Example: if the main domain is `att.com`, search each JS file for any `*.att.com` reference. Any subdomain surfaced this way (e.g. `subdomain.att.com`) that isn't already in the list gets added.

This technique is recursive by design: each newly discovered subdomain gets its own JS files pulled and searched the same way, which can surface still more subdomains. Keep repeating until no new subdomains appear through this method.

**End of Stage 1 — dedup requirement:** once all five sources/techniques have run, merge every result and extract only the unique set before writing the final file (e.g. `sort -u`). `subdomain.txt` must never contain duplicate lines.

**Output:**
```
engagements/<target-slug>/Recon/Wildcard/subdomain.txt
```
(deduplicated, one unique subdomain per line)

---

## Stage 2 — Live Filtering (httpx)

Run httpx twice against the same subdomain list.

**2a. Full metadata pass:**
```
cat /engagements/<target-slug>/Recon/Wildcard/subdomain.txt | dnsx -silent | httpx -silent -status-code -title -tech-detect | tee -a /engagements/<target-slug>/Recon/Wildcard/filter-allInfo.txt
```
Output:
```
engagements/<target-slug>/Recon/Wildcard/filter-allInfo.txt
```


---

## Stage 3 — Sensitive File & Secret Discovery in JS

For every live host (status 200, 301, or 302), pull its JavaScript files and check for references to sensitive files — `.env`, `.config`, and similar — plus any other sensitive material such as API keys.

**Validation rule:** a finding must be verified before it's recorded, not just pattern-matched — e.g. confirm the referenced file is actually reachable/exposed, or that a matched string is a genuine key format rather than a placeholder or example value.

**Output:**
```
engagements/<target-slug>/Recon/Wildcard/sensitive-data.txt
```

---

## Stage 4 — Technology & Function Mapping

For every live host, fingerprint the technology stack — frameworks, CDNs, WAFs, server software, and versions where identifiable — and link that fingerprint to the endpoints already discovered for that host.

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

## Stage 5 — Authentication & Authorization Surface (API Host Mapping)

This is the most important stage in this skill. For every live host, go deep into its JavaScript files again — this time specifically hunting for **API endpoints**. Any host where API endpoints are found gets recorded along with the endpoint(s) discovered for it.

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
