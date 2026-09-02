---
name: multi-hunter
description: The MultiHunter engagement skill. Load when running, coordinating, or resuming a multi-agent security-testing pipeline (recon, map, think, exploit, prove, report) on an authorized target — when using the mh CLI, when reading or writing an engagement blackboard, or when the director/any specialist agent needs the canonical workflow, blackboard schema, and handoff contract. Use ONLY for authorized, in-scope engagements.
---

# MultiHunter — engagement coordination

This skill is the canonical reference for the MultiHunter multi-agent security
testing system. It defines the workflow, the shared blackboard, and the
handoff contract that every agent in the team follows. Agents do not need to
re-derive the system each run — load this skill and follow it.

## The team

| Agent | Mode | Responsibility | Outputs |
|---|---|---|---|
| `director` | primary | Orchestrates the pipeline, dispatches specialists, enforces scope | engagement.json, log.json |
| `recon` | subagent | Attack-surface discovery | surface/{assets,endpoints,js,secrets}.json |
| `map` | subagent | Auth / roles / tenants / objects / trust boundaries | model/{auth,app}.json |
| `think` | subagent | Deep logic analysis → attack-path hypotheses | analysis/attack-paths.json |
| `exploit` | subagent | Hypothesis-driven testing (IDOR/SSRF/authz/auth/injection) | testing/{hypotheses,results}.json |
| `prove` | subagent | Reproducible PoCs, impact confirmation, false-positive elimination | findings/*.json, evidence/<id>/ |
| `report` | subagent | Professional disclosure report (H1 first) | reports/<target>-report.md |
| `jsintel` | subagent | JS intelligence (endpoints, secrets, postMessage, DOM XSS) | surface/js.json |
| `apianalyst` | subagent | API contract (GraphQL/OpenAPI/gRPC/shadow) | analysis/api-contract.json |
| `duplicatecheck` | subagent | Duplicate detection vs public + intra-engagement | findings/*.json dup_check |

## The workflow

```
recon ──► jsintel ─┐
   │               ▼
   └──► apianalyst► map ──► think ──► exploit ──► prove ──► duplicatecheck ──► report
                 ▲                              │
                 └────── new surface / paths ◄──┘
```

Non-linear by design: exploit discoveries feed back into think (new attack
paths) and recon (new surface). The director decides when to re-enter a stage.
The pipeline is a DAG with feedback, not a strict line.

## The blackboard (shared state)

Every engagement lives in `~/Targets/<target>/`. It is both human-readable
(markdown) and machine-readable (JSON). The `mh` CLI is the deterministic API
over this folder — agents should prefer `mh` over hand-editing JSON.

```
engagement.json     master index: phase cursor, stage_status, handoffs, counts
scope.md / scope.json   program scope + rules (only in-scope assets get tested)
surface/  assets.json · endpoints.json · js.json · secrets.json
model/    app.json · auth.json
analysis/ attack-paths.json · api-contract.json
testing/  hypotheses.json · results.json
findings/ <id>.json · <id>.md · index.json
evidence/ <id>/            sanitized proof files
reports/  <target>-report.md
log.json  append-only event log
```

Key rules:

- **Every artifact is appended, never clobbered** by a later stage unless it
  is the stage's own output. `mh ingest` dedups on a natural key.
- **Every finding carries a triage verdict** (`PASS` / `DOWNGRADE` / `KILL`)
  before it may appear in a report.
- **Secrets and cookies are always redacted** before anything is written to
  the blackboard.

## The handoff contract

Every specialist ends its reply with one fenced ```json``` block:

```json
{
  "agent": "<name>",
  "status": "complete",
  "counts": {"<artifact>": <n>},
  "artifacts_written": ["<relative paths>"],
  "highlights": ["one-line discoveries"],
  "recommended_next": ["<stage>"],
  "blockers": ["what stopped you"]
}
```

The director reads `artifacts_written`, `highlights`, and `recommended_next`
to choose the next dispatch. A specialist that reports a blocker is either
re-dispatched with context or the operator is asked.

## Scope discipline (every agent, always)

1. Only test assets in `scope.json`. Out-of-scope discoveries are recorded as
   observed-but-untested or skipped.
2. Use provided test accounts; respect program rate limits.
3. Stop any test that touches production data or real user PII.
4. Hypothesis-driven testing only — no blind brute force over the surface.
5. If scope is ambiguous, ask the operator. Never guess.

## mh CLI cheat-sheet

```
mh new <target>                 scaffold an engagement
mh status <target>              phase, stage status, counts
mh run <target> <stage>         render the full agent task for a stage
mh handoff <target> <stage>     record a completed stage, advance the phase cursor
mh ingest <target> <kind> --file x.json   merge artifacts
mh add-finding <target> --file finding.json|finding.md
mh dedup <target>               mark duplicates (deterministic pass)
mh triage <target>              run the 7-Question Gate on findings
mh report <target>              assemble the HackerOne report
mh export <target>              bundle report + findings
mh log <target>                 tail the event log
```

## 7-Question Gate (before any report)

1. Can an attacker use this RIGHT NOW with a real HTTP request?
2. Is the impact on the program's accepted-impact list?
3. Is the asset in scope?
4. Does it work without privileged access an attacker can't get?
5. Is this not already known or documented behavior?
6. Can impact be proved beyond "technically possible"?
7. Is this not on the never-submit list (self-XSS, rate-limit-only,
   clickjacking, CSRF-on-logout, missing headers)?

One NO on Q1/Q3/Q4/Q7 = KILL. Q2/Q5 NO = DOWNGRADE. Only PASS and DOWNGRADE
findings reach the report.

## Knowledge layer

The agent prompts reference the Claude-BugHunter skill bundle (83 skills) as
the per-class knowledge layer — `hunt-idor`, `hunt-ssrf`, `triage-validation`,
`evidence-hygiene`, `report-writing`, etc. Those skills are the "what to look
for / how to prove it" encyclopedia; the agent files are the "who does what /
how it hands off" coordination. Load the relevant hunt skill per hypothesis
before testing, and `triage-validation` + `evidence-hygiene` before prove.