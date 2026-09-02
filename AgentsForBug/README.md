# MultiHunter

A **multi-agent security testing system** built on top of
[`elementalsouls/Claude-BugHunter`](https://github.com/elementalsouls/Claude-BugHunter).
Instead of one big "hunt" prompt, a team of specialized agents works through a
structured, hypothesis-driven pipeline — **recon → map → think → exploit →
prove → report** — sharing context through a common engagement blackboard so
every stage builds on the last.

> Only test targets that are explicitly authorized and within the scope of the
> relevant security program. MultiHunter enforces scope in the blackboard, but
> authorization is yours to hold.

## The agent team

| Agent | Responsibility |
|---|---|
| **Director** | Orchestrates the pipeline, dispatches specialists, enforces scope, decides when to re-enter stages. |
| **Recon** | Maps the attack surface: subdomains, hosts, live services, tech, JS, endpoints, secrets. |
| **Map** | Models auth mechanisms, roles, tenants, permissions, object relationships, trust boundaries. |
| **Think** | Deep logic analysis: endpoint→function mapping, workflows, feature interactions → ranked, testable attack-path hypotheses. |
| **Exploit** | Hypothesis-driven testing: IDOR/BOLA, SSRF, authz, auth flaws, injection. No blind brute force. |
| **Prove** | Reproducible PoCs, impact confirmation, false-positive elimination, redacted evidence, the 7-Question Gate. |
| **Report** | Professional HackerOne disclosure report: repro steps, impact, evidence, remediation. |
| **JSintel** *(support)* | JS intelligence: endpoints, secrets, postMessage handlers, DOM XSS sinks, source maps. |
| **Apianalyst** *(support)* | API contracts: GraphQL introspection, OpenAPI, gRPC, shadow APIs. |
| **Duplicatecheck** *(support)* | Duplicate detection vs the public space and within the engagement. |

## Architecture in one picture

```
recon ──► jsintel ─┐
   │               ▼
   └──► apianalyst► map ──► think ──► exploit ──► prove ──► duplicatecheck ──► report
                 ▲                              │
                 └────── new surface / paths ◄──┘
```

- **Agents** are [opencode subagents](https://opencode.ai) (`agents/*.md`) — each
  with a clear standing prompt, its stage's knowledge layer, and the shared
  **handoff contract**.
- **Blackboard** — every engagement lives in `~/Targets/<target>/` with a
  machine-readable `engagement.json` plus per-stage artifact JSON. Agents read
  prior stages' output and write their own.
- **Orchestrator** — the `mh` Python CLI is the deterministic backbone: scaffold,
  ingest, findings, dedup, the 7-Question Gate, report assembly, export.
- **Knowledge layer** — the vendored Claude-BugHunter bundle (83 skills + 37
  disclosed-report pattern libraries) is the per-class encyclopedia the agents
  load (`hunt-idor`, `hunt-ssrf`, `triage-validation`, `evidence-hygiene`,
  `report-writing`, ...).

See [`docs/architecture.md`](docs/architecture.md) and
[`docs/workflow.md`](docs/workflow.md).

## Install

Prerequisites: Python 3.9+, opencode, and a clone of Claude-BugHunter for the
knowledge layer.

```powershell
# 1. vendor the Claude-BugHunter knowledge layer
git clone https://github.com/elementalsouls/Claude-BugHunter.git
./scripts/vendor-skills.ps1 -Source <path-to-Claude-BugHunter-clone>

# 2. install agents, commands, skill, and the mh CLI
./scripts/install.ps1
```

(macOS/Linux: `./scripts/vendor-skills.sh <clone>` then `./scripts/install.sh`)

This copies the agents into `~/.config/opencode/agent/`, the slash commands into
`~/.config/opencode/command/`, the coordinating skill into
`~/.config/opencode/skills/`, the 83 Claude-BugHunter skills into
`~/.agents/skills/` (auto-scanned by opencode), and an `mh` CLI shim into
`~/.local/bin`.

**Restart opencode** after installing — config loads once at startup.

## Quickstart

```text
/pipeline acme.com --program hackerone
```

The Director scaffolds the engagement, then dispatches the specialists in
dependency order, reviewing each handoff and re-entering stages when exploit
discovers new surface. Or drive it manually:

```text
/mh-scope acme.com          # author the in-scope/out-of-scope/impact/rules
/mh-status acme.com         # phase, stage status, counts
```

Everything the agents write lands in `~/Targets/<target>/`, and the final report
is `~/Targets/<target>/reports/<target>-report.md`.

## The mh CLI

```text
mh new <target>                 scaffold an engagement
mh status <target>              phase, stage status, counts
mh run <target> <stage>         render the full agent task for a stage
mh handoff <target> <stage>     record a completed stage, advance the phase cursor
mh ingest <target> <kind> --file x.json    merge artifacts (assets/endpoints/js/secrets/attack-paths/hypotheses)
mh add-finding <target> --file finding.json|finding.md
mh dedup <target>               mark duplicates (deterministic pass)
mh triage <target>              run the 7-Question Gate on findings
mh report <target> --platform h1   assemble the HackerOne report
mh export <target>              bundle report + findings
mh log <target>                 tail the event log
```

`MH_TARGETS` overrides the engagement base directory (default `~/Targets`).

## Testing

```text
python -m unittest discover -s tests -v
```

No external dependencies — the orchestrator and tests are stdlib-only, matching
the Claude-BugHunter engine's philosophy.

## How the stages cooperate

1. **Recon** discovers the surface and ranks it (P1/P2/KILL), scope-checking
   every asset. **JSintel** and **Apianalyst** deepen it.
2. **Map** turns the surface into a model: who can do what, which objects are
   owned by whom, where trust crosses boundaries.
3. **Think** reasons about the model and produces ranked, *testable* attack-path
   hypotheses (never claims — hypotheses).
4. **Exploit** executes hypotheses with minimal, precise requests; confirmed
   signals become candidates; new surface loops back to Think.
5. **Prove** independently reproduces each candidate, confirms impact, kills
   false positives, gathers redacted evidence, and runs the 7-Question Gate.
6. **Duplicatecheck** clears findings against the public space and the
   engagement.
7. **Report** writes the final disclosure report from validated findings only.

Every stage ends with a machine-readable **handoff** (`artifacts_written`,
`highlights`, `recommended_next`, `blockers`) that the Director consumes to
choose the next dispatch.

## License

MIT for code; the vendored Claude-BugHunter content keeps its own license
(MIT for code, CC BY 4.0 for methodology/content). See
[`LICENSE`](LICENSE) and the Claude-BugHunter `NOTICE`/`LICENSE-CONTENT` for the
vendored bundle.