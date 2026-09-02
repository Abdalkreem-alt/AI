# Workflow — running an engagement

This is the operator's guide to driving a MultiHunter engagement from start to
report.

## 1. Authorize and scope

Before anything: confirm the target is **in scope** of a program you are
authorized to test. Only then scaffold an engagement.

```text
/pipeline acme.com --program hackerone
```

or, manually:

```text
mh new acme.com --program hackerone
/mh-scope acme.com          # fill in-scope, out-of-scope, accepted impact, rules, test accounts
```

The scope file is the enforcement boundary — Recon and Exploit will refuse to
touch out-of-scope assets. If you have test accounts, add them to `scope.json`
(`test_accounts`) and note the roles in `model/auth.json` when Map runs.

## 2. Recon the surface

```text
mh run acme.com recon
```

The Recon agent discovers subdomains, probes live hosts, fingerprints tech,
collects JS, scans for secrets, and ranks everything P1 / P2 / KILL. It ends
with a handoff recommending whether to run `jsintel` / `apianalyst` next.

Run the deep passes when suggested:

```text
mh run acme.com jsintel
mh run acme.com apianalyst
```

These update `surface/` and `analysis/api-contract.json` and feed the model.

## 3. Model the application

```text
mh run acme.com map
```

Map figures out the auth mechanism, roles, tenants, object ownership, and trust
boundaries — using the provided accounts and app behavior, no attacks. Output:
`model/auth.json` and `model/app.json`.

## 4. Reason about attack paths

```text
mh run acme.com think
```

Think maps endpoints → functions → workflows, looks for feature interactions
and logic flaws, and writes ranked, **testable** hypotheses to
`analysis/attack-paths.json`. Think never sends attack traffic.

## 5. Test hypotheses

```text
mh run acme.com exploit
```

Exploit executes each hypothesis with minimal, deliberate requests (two-account
IDOR swaps, SSRF callback via Burp Collaborator, method/param swaps on authz,
one-payload-per-sink injection). Confirmed signals become candidates; rejected
hypotheses are closed; new surface loops back to think. Results land in
`testing/results.json`; statuses in `testing/hypotheses.json`.

If exploit reports new attack paths, the Director re-runs think on the delta
before proceeding.

## 6. Prove candidates

```text
mh run acme.com prove
```

Prove independently reproduces each candidate, confirms real-world impact,
kills false positives, captures redacted evidence under `evidence/<id>/`, and
runs the 7-Question Gate. Confirmed findings:

```text
mh add-finding acme.com --file findings/F-001.json    # or --file findings/F-001.md
mh triage acme.com
```

## 7. Clear duplicates

```text
mh run acme.com duplicatecheck
mh dedup acme.com
```

Duplicatecheck compares against the public/known space (hacktivity, disclosed
reports, web) and the engagement. Findings that collide are marked
`duplicate_of` and dropped from reporting.

## 8. Report

```text
mh run acme.com report
mh report acme.com --platform h1 --out reports/acme.com-report.md
```

The report is written from validated findings only (triage PASS/DOWNGRADE,
non-duplicate). Review it, re-check the pre-submission checklist, apply final
evidence hygiene, then submit through HackerOne.

## Full-pipeline automation

```text
/pipeline acme.com
```

runs the whole thing with the Director making the loop decisions. Watch the
handoffs — the Director prints stage completions and highlights as they land.
At any point, `mh status acme.com` shows phase/stage/counts and `mh log
acme.com` shows the event trail.

## Pause and resume

Everything is on disk. Kill a run, `mh status`, and re-run the stage that was
interrupted (`mh run acme.com <stage>`) — state persists.

## Discipline rules

- One hypothesis = a handful of precise requests, never a wordlist sweep.
- Never continue a test that touches production data or real user PII — stop
  and note it.
- Redact cookies/tokens/PII in every artifact and evidence file.
- Only PASS/DOWNGRADE, non-duplicate findings enter the report.