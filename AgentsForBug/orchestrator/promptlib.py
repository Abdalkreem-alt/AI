#!/usr/bin/env python3
"""
promptlib.py — render a self-contained agent task from an agent definition
plus the current blackboard snapshot.

Each agent ships as a markdown file in `agents/<name>.md` (opencode subagent
definition). The body of that file is the standing system prompt. For headless
runs (`mh run <target> <stage>`), promptlib appends a compact snapshot of the
blackboard so a single prompt string carries everything the agent needs.
"""
import json
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(REPO_ROOT, "agents")

HANDOFF_CONTRACT = """\
## Handoff contract
When your work is done:
1. Write your artifacts into the engagement blackboard (see paths below).
2. Record outcomes with the `mh` CLI if available (e.g. `mh add-endpoints <target> --file ...`).
3. End your reply with a single fenced ```json``` block containing:

```json
{
  "agent": "<your name>",
  "status": "complete",
  "counts": {"<artifact type>": <n>},
  "artifacts_written": ["<relative paths>"],
  "highlights": ["<one-line findings / discoveries>"],
  "recommended_next": ["<stage name>"],
  "blockers": ["<anything that stopped you>"]
}
```

Do not invent evidence. If a test did not run, say so in `blockers`.
"""


def agent_def(name: str) -> dict:
    path = os.path.join(AGENTS_DIR, f"{name}.md")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"no agent definition {name} at {path}")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S).strip()
    m = re.search(r"^---\n(.*?)\n---\n", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
    return {"name": name, "meta": meta, "body": body}


def compact_snapshot(snapshot: dict, max_items: int = 30) -> str:
    """Render the blackboard snapshot as compact markdown, trimmed for context."""
    lines = []
    lines.append(f"### Target: {snapshot.get('target')} · Program: {snapshot.get('program')} · Phase: {snapshot.get('phase')}")
    lines.append(f"Stage status: {json.dumps(snapshot.get('stage_status', {}))}")
    lines.append(f"Counts: {json.dumps(snapshot.get('counts', {}))}")
    scope = snapshot.get("scope") or {}
    if scope:
        lines.append(f"Scope: in={scope.get('in_scope')} out={scope.get('out_of_scope')} "
                     f"impact={scope.get('accepted_impact')}")
    for label, key in (("ASSETS", "assets"), ("ENDPOINTS", "endpoints"), ("JS FILES", "js"),
                       ("SECRETS", "secrets"), ("ATTACK PATHS", "attack_paths"),
                       ("HYPOTHESES", "hypotheses"), ("FINDINGS", "findings")):
        items = snapshot.get(key) or []
        if not items:
            continue
        lines.append("")
        lines.append(f"#### {label} ({len(items)} shown first)")
        for it in items[:max_items]:
            lines.append(json.dumps(it, ensure_ascii=False)[:500])
    app = snapshot.get("model") or {}
    auth = snapshot.get("auth") or {}
    if app:
        lines.append("")
        lines.append("#### Application model")
        lines.append(json.dumps(app, ensure_ascii=False)[:1200])
    if auth:
        lines.append("")
        lines.append("#### Auth model")
        lines.append(json.dumps(auth, ensure_ascii=False)[:1200])
    return "\n".join(lines)


def render_agent_prompt(name: str, engagement, extra: str = "") -> str:
    """Full task prompt for a headless run of one stage agent."""
    body = agent_def(name)["body"]
    snap = engagement.snapshot()
    parts = [
        body,
        "",
        "## Current blackboard context",
        compact_snapshot(snap),
        "",
        HANDOFF_CONTRACT,
    ]
    if extra:
        parts.append("")
        parts.append("## Operator instructions")
        parts.append(extra)
    return "\n".join(parts)


def _selftest():
    import tempfile
    from blackboard import Engagement
    d = tempfile.mkdtemp()
    try:
        e = Engagement(base=d, target="acme.com").create("acme.com")
        e.add_assets([{"host": "a.acme.com", "url": "https://a.acme.com/"}])
        p = render_agent_prompt("recon", e)
        assert "recon" in p and "Current blackboard context" in p and "Handoff contract" in p
        assert "a.acme.com" in p
        assert "```json" in p
        print("promptlib.py self-test: PASS")
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    _selftest()