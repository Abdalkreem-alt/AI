#!/usr/bin/env python3
"""
mh — MultiHunter CLI.

The deterministic backbone of the multi-agent pipeline. `mh` manages the shared
engagement blackboard that the agent team (recon, map, think, exploit, prove,
report + jsintel/apianalyst/duplicatecheck) reads and writes.

  mh new <target>                 scaffold an engagement folder
  mh status <target>              phase, stage status, counts, handoffs
  mh run <target> <stage>         render the full agent task for a stage
  mh ingest <target> <kind>       merge JSON artifacts (assets/endpoints/js/...)
  mh add-finding <target>         add a structured finding (JSON or MD)
  mh dedup <target>               mark duplicate findings
  mh triage <target>              run the 7-Question Gate on findings
  mh report <target>              assemble the HackerOne report
  mh export <target>              bundle report + findings + evidence index
  mh log <target>                 tail the engagement event log

Stdlib only. No build step.
"""
import argparse
import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blackboard import (STAGES, SIDE_AGENTS, BlackboardError, Engagement,  # noqa: E402
                        DEFAULT_BASE)
from dedup import apply_duplicates, find_duplicates  # noqa: E402
from reportgen import build_report  # noqa: E402
import promptlib  # noqa: E402

# ---------------------------------------------------------------------------
# 7-Question Gate (from the Claude-BugHunter triage-validation skill)
# ---------------------------------------------------------------------------
TRIAGE_QUESTIONS = [
    ("Q1", "Can an attacker use this RIGHT NOW with a real HTTP request?",
     ["curl ", "POST ", "GET ", "HTTP/1.1", "PUT ", "DELETE ", "PATCH "]),
    ("Q2", "Is the impact on the program's accepted-impact list?",
     ["impact:", "severity:", "critical", "high", "medium", "pii", "rce", "sqli",
      "idor", "ssrf", "xss", "data"]),
    ("Q3", "Is the asset in scope?", ["scope", "in-scope", "in scope", "endpoint", "asset", "in_scope"]),
    ("Q4", "Does it work without privileged access an attacker can't get?",
     ["attacker", "unauthenticated", "low-priv", "any user", "session", "user"]),
    ("Q5", "Is this not already known or documented behavior?",
     ["not duplicate", "novel", "first reported", "previously unknown", "undocumented",
      "duplicate", "hacktivity", "public report", "writeup"]),
    ("Q6", "Can impact be proved beyond 'technically possible'?",
     ["leaked", "exfiltrated", "pii", "credential", "oob callback", "evidence"]),
    ("Q7", "Is this not on the never-submit list?",
     ["self-xss", "rate-limit", "clickjacking", "csrf on logout", "missing security headers"]),
]


def run_triage(finding: dict) -> dict:
    text = json.dumps(finding, ensure_ascii=False).lower()
    answers = []
    for qid, question, signals in TRIAGE_QUESTIONS:
        hit = any(s in text for s in signals)
        ok = not hit if qid == "Q7" else hit
        answers.append({"q": qid, "question": question, "pass": ok,
                        "answer": "YES" if ok else "NO"})
    fails = [a["q"] for a in answers if not a["pass"]]
    if not fails:
        verdict = "PASS"
    elif len(fails) == 1 and fails[0] in ("Q2", "Q5"):
        verdict = "DOWNGRADE"
    else:
        verdict = "KILL"
    return {"answers": answers, "fails": fails, "verdict": verdict}


# ---------------------------------------------------------------------------
# color + output helpers
# ---------------------------------------------------------------------------
def color(s: str, c: str) -> str:
    if not sys.stdout.isatty():
        return s
    codes = {"red": 31, "green": 32, "yellow": 33, "blue": 34, "cyan": 36, "bold": 1, "dim": 2}
    return f"\033[{codes.get(c, 0)}m{s}\033[0m"


def section(title: str):
    print()
    print(color("=" * 70, "blue"))
    print(color(title, "bold"))
    print(color("=" * 70, "blue"))


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_new(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if e.exists():
        print(color(f"[error] engagement already exists: {e.dir}", "red"))
        return 1
    scope_text = args.scope or ""
    if args.program and not scope_text:
        from blackboard import _default_scope_md
        scope_text = _default_scope_md(args.target, args.program)
    e.create(args.target, program=args.program, scope_text=scope_text,
             root_domains=[args.target])
    print(f"engagement created: {e.dir}")
    print(f"  next: {color('mh status ' + args.target, 'bold')} or run the pipeline "
          f"({color('mh run ' + args.target + ' recon', 'bold')})")
    return 0


def cmd_status(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if not e.exists():
        print(color(f"[error] no engagement for {args.target} — run `mh new`", "red"))
        return 1
    s = e.summary()
    section(f"status — {args.target}")
    print(f"  target:   {s['target']}   program: {s['program']}")
    print(f"  phase:    {color(s['phase'], 'bold')}   handoffs: {s['handoffs']}")
    for stage in STAGES + SIDE_AGENTS:
        st = s["stage_status"].get(stage, "-")
        mark = {"complete": "✓", "in_progress": "…", "pending": "·"}.get(st, "·")
        print(f"  {mark} {color(stage.ljust(14), 'dim')} {st}")
    c = s["counts"]
    print(f"  counts:   assets={c.get('assets')} endpoints={c.get('endpoints')} "
          f"js={c.get('js')} secrets={c.get('secrets')} attack_paths={c.get('attack_paths')} "
          f"hypotheses={c.get('hypotheses')} findings={c.get('findings')}")
    return 0


def cmd_run(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if not e.exists():
        print(color(f"[error] no engagement for {args.target} — run `mh new`", "red"))
        return 1
    if args.stage not in STAGES and args.stage not in SIDE_AGENTS:
        print(color(f"[error] unknown stage {args.stage} (known: {', '.join(STAGES + SIDE_AGENTS)})", "red"))
        return 1
    e.set_stage(args.stage, "in_progress")
    prompt = promptlib.render_agent_prompt(args.stage, e, extra=args.extra)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"agent task for `{args.stage}` written to {args.out} "
              f"({len(prompt.split())} words)")
    else:
        print(prompt)
    return 0


def cmd_prompt(args) -> int:
    return cmd_run(args)


KINDS = {
    "assets": "add_assets", "endpoints": "add_endpoints", "js": "add_js",
    "secrets": "add_secrets", "attack-paths": "add_attack_paths", "hypotheses": "add_hypotheses",
}
ARTIFACT_PATHS = {
    "assets": ("surface", "assets.json"), "endpoints": ("surface", "endpoints.json"),
    "js": ("surface", "js.json"), "secrets": ("surface", "secrets.json"),
    "attack-paths": ("analysis", "attack-paths.json"), "hypotheses": ("testing", "hypotheses.json"),
}


def cmd_ingest(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if not e.exists():
        print(color(f"[error] no engagement for {args.target}", "red"))
        return 1
    if args.kind not in KINDS:
        print(color(f"[error] kind must be one of {', '.join(KINDS)}", "red"))
        return 1
    if not args.file:
        print(color("[error] --file required", "red"))
        return 1
    with open(args.file, encoding="utf-8-sig") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else [data]
    method = getattr(e, KINDS[args.kind])
    n = method(items)
    total = len(e.artifacts(*ARTIFACT_PATHS[args.kind]))
    print(f"ingested {n} new {args.kind} (total {total})")
    return 0


def cmd_add_finding(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if not e.exists():
        print(color(f"[error] no engagement for {args.target}", "red"))
        return 1
    if args.file and args.file.endswith(".md"):
        fid = _ingest_finding_md(e, args.file)
    else:
        with open(args.file, encoding="utf-8-sig") as f:
            finding = json.load(f)
        fid = e.add_finding(finding)
    print(f"finding added: {fid}")
    print(f"  next: {color('mh triage ' + args.target + ' --finding ' + fid, 'bold')}")
    return 0


def _ingest_finding_md(e: Engagement, path: str) -> str:
    import re
    text = open(path, encoding="utf-8").read()
    finding = {"title": "", "summary": "", "reproduction_steps": [], "impact": ""}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    body = text
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                finding[k.strip().lower()] = v.strip().strip('"').strip("'")
        body = m.group(2)
    for key, pat in [("summary", r"##\s*(?:summary|description)\s*\n(.+?)(?=\n##|\Z)"),
                     ("impact", r"##\s*impact\s*\n(.+?)(?=\n##|\Z)"),
                     ("remediation", r"##\s*(?:remediation|fix)\s*\n(.+?)(?=\n##|\Z)")]:
        mm = re.search(pat, body, re.I | re.S)
        if mm and not finding.get(key):
            finding[key] = mm.group(1).strip()
    steps = re.search(r"##\s*(?:steps|reproduction|reproduce|poc)\s*\n(.+?)(?=\n##|\Z)", body, re.I | re.S)
    if steps:
        finding["reproduction_steps"] = [s for s in steps.group(1).splitlines() if s.strip()]
    if not finding["title"]:
        for line in body.splitlines():
            if line.startswith("# "):
                finding["title"] = line[2:].strip()
                break
    for k in ("endpoint", "vuln_class", "severity", "method"):
        if not finding.get(k):
            finding[k] = ""
    return e.add_finding(finding)


def cmd_dedup(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if not e.exists():
        print(color(f"[error] no engagement for {args.target}", "red"))
        return 1
    findings = e.findings()
    dups = find_duplicates(findings, title_threshold=args.threshold)
    n = apply_duplicates(findings, dups)
    for f in e.findings():
        if f.get("status") == "duplicate":
            e.update_finding(f["id"], {"status": "duplicate",
                                       "duplicate_of": f.get("duplicate_of"),
                                       "dup_score": f.get("dup_score")})
    print(f"dedup: {len(dups)} collision(s), {n} finding(s) marked duplicate")
    for d in dups:
        print(f"  {color(d['source'], 'yellow')} -> duplicate of {d['duplicate_of']} "
              f"(score {d['score']}, {', '.join(d['signals'])})")
    return 0


def cmd_triage(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if not e.exists():
        print(color(f"[error] no engagement for {args.target}", "red"))
        return 1
    findings = [f for f in e.findings() if f.get("status") != "duplicate"]
    if args.finding:
        findings = [f for f in findings if f.get("id") == args.finding]
    if not findings:
        print(color("[error] no findings to triage", "red"))
        return 1
    verdicts = {}
    for f in findings:
        t = run_triage(f)
        verdicts[f["id"]] = t["verdict"]
        e.update_finding(f["id"], {"triage": {"verdict": t["verdict"], "fails": t["fails"],
                                              "answers": t["answers"]}})
        mark = {"PASS": "green", "DOWNGRADE": "yellow", "KILL": "red"}[t["verdict"]]
        print(f"  {color(t['verdict'].ljust(10), mark)} {f['id']}  {f.get('title','')}")
        if t["fails"]:
            print(f"      failed: {', '.join(t['fails'])}")
    return 0


def cmd_report(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if not e.exists():
        print(color(f"[error] no engagement for {args.target}", "red"))
        return 1
    report = build_report(e, platform=args.platform, evidence_root=e.dir)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"report written: {args.out}")
    else:
        print(report)
    return 0


def cmd_export(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if not e.exists():
        print(color(f"[error] no engagement for {args.target}", "red"))
        return 1
    bundle = {
        "target": e.summary().get("target"),
        "program": e.summary().get("program"),
        "scope": e.scope(),
        "findings": [f for f in e.findings() if f.get("status") != "duplicate"],
        "report": build_report(e, platform=args.platform, evidence_root=e.dir),
    }
    out = args.out or os.path.join(e.dir, "reports", f"{e.summary().get('target')}-bundle.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
    print(f"bundle exported: {out}")
    return 0


def cmd_log(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if not e.exists():
        print(color(f"[error] no engagement for {args.target}", "red"))
        return 1
    lines = []
    logp = os.path.join(e.dir, "log.json")
    if os.path.isfile(logp):
        with open(logp, encoding="utf-8") as f:
            lines = [json.loads(l) for l in f if l.strip()]
    for l in lines[-args.tail:]:
        print(f"{color(l['at'], 'dim')}  {color(l['event'], 'cyan')}  {l.get('detail','')}")
    return 0


def cmd_scope(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if not e.exists():
        print(color(f"[error] no engagement for {args.target}", "red"))
        return 1
    if args.set:
        with open(args.set, encoding="utf-8") as f:
            scope = json.load(f)
        e.set_scope(scope)
        print(f"scope written: {args.set}")
    else:
        print(json.dumps(e.scope(), indent=2))
    return 0


def cmd_handoff(args) -> int:
    e = Engagement(base=args.base, target=args.target)
    if not e.exists():
        print(color(f"[error] no engagement for {args.target}", "red"))
        return 1
    if args.stage not in STAGES and args.stage not in SIDE_AGENTS:
        print(color(f"[error] unknown stage {args.stage}", "red"))
        return 1
    e.complete_phase(args.stage, summary=args.summary, artifacts=args.artifacts)
    s = e.summary()
    print(f"handoff recorded: {args.stage} complete -> next phase {s['phase']}")
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mh",
        description="MultiHunter — deterministic backbone of the multi-agent "
                    "security testing pipeline (recon -> map -> think -> exploit -> prove -> report).",
        epilog=textwrap.dedent("""\
            Examples:
              mh new acme.com --program hackerone
              mh run acme.com recon --out task-recon.md
              mh ingest acme.com endpoints --file endpoints.json
              mh add-finding acme.com --file finding.json
              mh dedup acme.com
              mh triage acme.com
              mh report acme.com --platform h1 --out reports/report.md
            """),
    )
    parser.add_argument("--base", default=os.environ.get("MH_TARGETS", DEFAULT_BASE),
                        help=f"engagement base dir (default {DEFAULT_BASE})")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="scaffold an engagement")
    p.add_argument("target")
    p.add_argument("--program", default="hackerone")
    p.add_argument("--scope", default="")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("status", help="show phase/stage/counts")
    p.add_argument("target")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("run", help="render the agent task for a stage")
    p.add_argument("target")
    p.add_argument("stage")
    p.add_argument("--extra", default="")
    p.add_argument("--out")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("prompt", help="alias for `run` (render agent task)")
    p.add_argument("target")
    p.add_argument("stage")
    p.add_argument("--extra", default="")
    p.add_argument("--out")
    p.set_defaults(func=cmd_prompt)

    p = sub.add_parser("ingest", help="merge JSON artifacts into the blackboard")
    p.add_argument("target")
    p.add_argument("kind", choices=sorted(KINDS))
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("add-finding", help="add a structured finding (JSON or MD)")
    p.add_argument("target")
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_add_finding)

    p = sub.add_parser("dedup", help="mark duplicate findings")
    p.add_argument("target")
    p.add_argument("--threshold", type=float, default=0.6)
    p.set_defaults(func=cmd_dedup)

    p = sub.add_parser("triage", help="run the 7-Question Gate on findings")
    p.add_argument("target")
    p.add_argument("--finding")
    p.set_defaults(func=cmd_triage)

    p = sub.add_parser("report", help="assemble the HackerOne report")
    p.add_argument("target")
    p.add_argument("--platform", default="h1", choices=["h1", "bugcrowd", "intigriti", "immunefi"])
    p.add_argument("--out")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("export", help="export report + findings bundle")
    p.add_argument("target")
    p.add_argument("--platform", default="h1")
    p.add_argument("--out")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("log", help="tail the event log")
    p.add_argument("target")
    p.add_argument("--tail", type=int, default=20)
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("scope", help="read or set engagement scope")
    p.add_argument("target")
    p.add_argument("--set")
    p.set_defaults(func=cmd_scope)

    p = sub.add_parser("handoff", help="record a completed stage and advance the phase cursor")
    p.add_argument("target")
    p.add_argument("stage")
    p.add_argument("--summary", default="")
    p.add_argument("--artifacts", nargs="*", default=[])
    p.set_defaults(func=cmd_handoff)

    args = parser.parse_args()
    try:
        return args.func(args)
    except BlackboardError as e:
        print(color(f"[error] {e}", "red"))
        return 2


if __name__ == "__main__":
    sys.exit(main())