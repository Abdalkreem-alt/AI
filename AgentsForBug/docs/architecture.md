# Architecture

MultiHunter is a coordination layer over the Claude-BugHunter skill bundle. It
turns a single-agent "hunt prompt" into a team of specialized opencode
subagents that share a common, on-disk blackboard.

## Layers

```
┌──────────────────────────────────────────────────────────────────┐
│  Director (primary agent) — orchestrates, dispatches, enforces   │
│  scope, decides re-entry. Driven by /pipeline.                   │
├──────────────────────────────────────────────────────────────────┤
│  Specialist agents (subagents) — recon, map, think, exploit,     │
│  prove, report + jsintel, apianalyst, duplicatecheck             │
├──────────────────────────────────────────────────────────────────┤
│  Blackboard (shared state) — ~/Targets/<target>/, JSON + MD.     │
│  Deterministic API: mh CLI (orchestrator/*.py).                  │
├──────────────────────────────────────────────────────────────────┤
│  Knowledge layer — vendored Claude-BugHunter: 83 skills + 37     │
│  disclosed-report pattern libraries (knowledge/cbh-*).           │
└──────────────────────────────────────────────────────────────────┘
```

## Why a blackboard

Subagents in opencode run in isolated contexts. The blackboard is the shared
memory: each stage reads what it needs, writes its output, and returns a compact
handoff. This gives three properties a single-prompt approach lacks:

- **Auditability** — every artifact, finding, and verdict is a file. An
  engagement can be paused, resumed, or reviewed by a triager mid-run.
- **Composition** — a stage never re-derives another stage's work. Think reasons
  over Map's model; Exploit tests Think's hypotheses; Prove validates Exploit's
  candidates.
- **Deterministic gates** — dedup, triage, and report assembly are code, not
  model whims.

## Data model

The engagement folder layout:

```
engagement.json      master index: phase cursor, stage_status, handoffs, counts, log
scope.md / scope.json    scope enforcement boundary
surface/             recon+jsintel: assets, endpoints, js, secrets
model/               map: app (components, objects, trust boundaries), auth (mechanisms, roles)
analysis/            think: attack-paths.json · apianalyst: api-contract.json
testing/             exploit: hypotheses.json, results.json
findings/            prove: <id>.json, <id>.md, index.json
evidence/            prove: <id>/ sanitized proof files
reports/             report: <target>-report.md
```

Artifacts are appended (never clobbered across stages) and deduped on a natural
key (`host`, `url`, `id`, ...). Findings flow `candidate → confirmed →
(report)` or `→ rejected / duplicate / false_positive`.

## Workflow (DAG with feedback)

```
recon ──► jsintel ─┐
   │               ▼
   └──► apianalyst► map ──► think ──► exploit ──► prove ──► duplicatecheck ──► report
                 ▲                              │
                 └────── new surface / paths ◄──┘
```

- **Dependencies**: recon before map/think; map before think; think before
  exploit; prove before report; duplicatecheck before report.
- **Feedback**: exploit discoveries (shadow endpoints, new params, new
  workflows) re-enter think and recon. The Director owns the loop and uses the
  handoffs' `recommended_next` to decide.
- **Stage agents** are described in `agents/*.md`. Each is self-contained: its
  body is a valid standalone prompt (rendered by `mh run <target> <stage>` for
  headless runs).

## The handoff contract

Every specialist returns:

```json
{
  "agent": "<name>",
  "status": "complete",
  "counts": {"<artifact>": <n>},
  "artifacts_written": ["..."],
  "highlights": ["..."],
  "recommended_next": ["..."],
  "blockers": []
}
```

`recommended_next` is the Director's dispatch queue; `blockers` are honored
(ask the operator or re-dispatch with context).

## Deterministic gates

- **Dedup** (`orchestrator/dedup.py`) — normalized (endpoint, class, method,
  param) collisions + title similarity; marks `duplicate`.
- **7-Question Gate** (`orchestrator/cli.py` `run_triage`) — signal-scored
  PASS / DOWNGRADE / KILL, persisted into each finding's `triage`.
- **Report assembly** (`orchestrator/reportgen.py`) — renders the H1 report from
  non-duplicate, non-rejected findings with CVSS 3.1 vectors and a
  pre-submission checklist.

## Knowledge layer

`knowledge/cbh-skills/` (83 skills) and `knowledge/cbh-reports/` (37 pattern
libraries) are vendored from Claude-BugHunter. The specialist prompts reference
the relevant `hunt-*` skills per hypothesis and mandate `triage-validation` +
`evidence-hygiene` before prove. Install copies them to `~/.agents/skills/`
where opencode auto-scans them, so every agent can load the right encyclopedia
entry on demand.

## Scope enforcement

- `scope.json` is the single source of truth. Recon refuses to record
  out-of-scope assets as testable; exploit refuses to send requests to them.
- The Director re-checks scope before every dispatch.
- Evidence hygiene (redaction) is enforced in the prove and report prompts and
  echoed by the report's pre-submission checklist.

## Files

| Path | Purpose |
|---|---|
| `agents/*.md` | Agent definitions (prompt + opencode frontmatter) |
| `commands/*.md` | Slash commands (`/pipeline`, `/mh-status`, `/mh-scope`) |
| `skills/multi-hunter/SKILL.md` | Coordinating skill (workflow, blackboard, contract) |
| `orchestrator/blackboard.py` | Engagement state API |
| `orchestrator/cli.py` | `mh` CLI + 7-Question Gate |
| `orchestrator/dedup.py` | Duplicate detection |
| `orchestrator/reportgen.py` | Report assembly |
| `orchestrator/promptlib.py` | Agent-task rendering from agent files + snapshot |
| `scripts/vendor-skills.*` | Vendor the Claude-BugHunter knowledge layer |
| `scripts/install.*` | Install agents/commands/skills/CLI into opencode |
| `tests/` | Stdlib unittest suite |

## Design decisions

1. **Coordination in the prompts, gates in the code.** The model decides what
   to test (and how to reason); the code decides what is a finding, a duplicate,
   and whether it may be reported.
2. **Agents are files, not config blobs.** `agents/*.md` doubles as the opencode
   subagent definition and as the standalone prompt for headless `mh run`.
3. **Stdlib only.** The orchestrator mirrors Claude-BugHunter's engine
   philosophy: zero-dependency, run anywhere, self-tests inline.
4. **No automated exploitation.** MultiHunter is hypothesis-driven by design;
   the Exploit agent sends deliberate, minimal requests. This keeps engagements
   gentle and reports defensible.