#!/usr/bin/env python3
"""
blackboard.py — the shared state layer of the MultiHunter pipeline.

Every agent works on the same on-disk "blackboard": an engagement folder that is
both human-readable (markdown) and machine-readable (JSON). Agents read the
artifacts produced by the stages before them, do their work, and write their
output back. This module is the deterministic API over that folder so agents
and the CLI never hand-roll JSON.

Engagement layout (created by `mh new`):

  <base>/<target>/
    engagement.json        # master index: cursor, stage status, handoffs, counts
    scope.md               # program scope + rules (operator/director authored)
    scope.json             # machine-readable scope (parsed from scope.md)
    surface/               # Recon  -> assets.json, endpoints.json, js.json, secrets.json
    model/                 # Map    -> app.json, auth.json
    analysis/              # Think  -> attack-paths.json
    testing/               # Exploit-> hypotheses.json, results.json
    findings/              # Prove  -> <id>.json + <id>.md
    evidence/              # Prove  -> <id>/ (screenshots, hars, replays)
    reports/               # Report -> <target>-report.md
    log.json               # append-only event log (also mirrored in engagement.json)
"""
import json
import os
import re
import time
from datetime import datetime, timezone

DEFAULT_BASE = os.path.expanduser("~/Targets")

STAGES = ["recon", "map", "think", "exploit", "prove", "report"]
# Extra agents that slot into the workflow but are not hard gates.
SIDE_AGENTS = ["jsintel", "apianalyst", "duplicatecheck"]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fmt_ts():
    return time.strftime("%Y%m%d-%H%M%S")


def safe_name(target: str) -> str:
    """Sanitize a target string into a safe folder name."""
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", target.strip().lower()).strip("-") or "target"


class BlackboardError(Exception):
    pass


# ---------------------------------------------------------------------------
# Engagement
# ---------------------------------------------------------------------------
class Engagement:
    def __init__(self, base: str | None = None, target: str | None = None, dir_path: str | None = None):
        self.base = os.path.expanduser(base or DEFAULT_BASE)
        if dir_path:
            self.dir = os.path.abspath(dir_path)
            self.target = safe_name(os.path.basename(self.dir))
        else:
            if not target:
                raise BlackboardError("must provide a target name or an existing engagement dir")
            self.target = safe_name(target)
            self.dir = os.path.join(self.base, self.target)
        self.engage_path = os.path.join(self.dir, "engagement.json")
        self.scope_md_path = os.path.join(self.dir, "scope.md")
        self.scope_json_path = os.path.join(self.dir, "scope.json")

    # ----- lifecycle ------------------------------------------------------
    def exists(self) -> bool:
        return os.path.isfile(self.engage_path)

    def create(self, target: str, program: str = "hackerone",
               scope_text: str = "", root_domains: list[str] | None = None) -> "Engagement":
        os.makedirs(os.path.join(self.dir, "surface"), exist_ok=True)
        os.makedirs(os.path.join(self.dir, "model"), exist_ok=True)
        os.makedirs(os.path.join(self.dir, "analysis"), exist_ok=True)
        os.makedirs(os.path.join(self.dir, "testing"), exist_ok=True)
        os.makedirs(os.path.join(self.dir, "findings"), exist_ok=True)
        os.makedirs(os.path.join(self.dir, "evidence"), exist_ok=True)
        os.makedirs(os.path.join(self.dir, "reports"), exist_ok=True)
        self._write_engagement({
            "$schema": "multihunter/engagement-v1",
            "target": target,
            "program": program,
            "created": _now(),
            "updated": _now(),
            "phase": "init",
            "stage_status": {s: "pending" for s in STAGES},
            "scope": {
                "root_domains": root_domains or [target],
                "in_scope": [],
                "out_of_scope": [],
                "accepted_impact": [],
                "rules": [],
                "test_accounts": [],
                "notes": "",
            },
            "counts": {"assets": 0, "endpoints": 0, "js": 0, "secrets": 0,
                       "attack_paths": 0, "hypotheses": 0, "findings": 0},
            "handoffs": [],
        })
        with open(self.scope_md_path, "w", encoding="utf-8") as f:
            f.write(scope_text or _default_scope_md(target, program))
        self.log(f"engagement created: target={target} program={program}")
        return self

    # ----- io -------------------------------------------------------------
    def _write_engagement(self, state: dict):
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.engage_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.engage_path)

    def _load_engagement(self) -> dict:
        if not os.path.isfile(self.engage_path):
            raise BlackboardError(f"no engagement at {self.engage_path} — run `mh new` first")
        with open(self.engage_path, encoding="utf-8") as f:
            return json.load(f)

    def _save_engagement(self, state: dict):
        state["updated"] = _now()
        self._write_engagement(state)

    def state(self) -> dict:
        return self._load_engagement()

    def log(self, event: str, detail: str = ""):
        state = self._load_engagement()
        state.setdefault("log", [])
        state["log"].append({"at": _now(), "event": event, "detail": detail})
        self._save_engagement(state)
        # also mirror to log.json for tailing
        with open(os.path.join(self.dir, "log.json"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": _now(), "event": event, "detail": detail}) + "\n")

    def _read_artifact(self, *parts, default):
        p = os.path.join(self.dir, *parts)
        if not os.path.isfile(p):
            return default
        try:
            with open(p, encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            raise BlackboardError(f"corrupt artifact {p}: {e}")

    def _write_artifact(self, data, *parts):
        p = os.path.join(self.dir, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)

    # ----- workflow cursor -------------------------------------------------
    def set_phase(self, phase: str):
        state = self._load_engagement()
        state["phase"] = phase
        state["stage_status"][phase] = "in_progress"
        self._save_engagement(state)

    def complete_phase(self, phase: str, summary: str = "", artifacts: list[str] | None = None):
        state = self._load_engagement()
        state["phase"] = _next_phase(phase)
        state["stage_status"][phase] = "complete"
        state.setdefault("handoffs", []).append({
            "agent": phase, "at": _now(), "status": "complete",
            "summary": summary, "artifacts": artifacts or [],
        })
        self._save_engagement(state)
        self.log(f"handoff: {phase} -> {state['phase']}", summary)

    def set_stage(self, stage: str, status: str):
        state = self._load_engagement()
        state["stage_status"][stage] = status
        self._save_engagement(state)

    def summary(self) -> dict:
        state = self._load_engagement()
        c = state.get("counts", {})
        return {
            "target": state.get("target"),
            "program": state.get("program"),
            "phase": state.get("phase"),
            "stage_status": state.get("stage_status", {}),
            "counts": c,
            "handoffs": len(state.get("handoffs", [])),
        }

    # ----- scope ------------------------------------------------------------
    def scope(self) -> dict:
        if os.path.isfile(self.scope_json_path):
            return self._read_artifact("scope.json", default={})
        return {}

    def set_scope(self, scope: dict):
        self._write_artifact(scope, "scope.json")

    # ----- surface (Recon) ---------------------------------------------------
    def add_assets(self, assets: list[dict]) -> int:
        return self._upsert("surface", "assets.json", assets, "host")

    def add_endpoints(self, endpoints: list[dict]) -> int:
        return self._upsert("surface", "endpoints.json", endpoints, "url")

    def add_js(self, js: list[dict]) -> int:
        return self._upsert("surface", "js.json", js, "url")

    def add_secrets(self, secrets: list[dict]) -> int:
        return self._upsert("surface", "secrets.json", secrets, "value")

    def _upsert(self, subdir: str, fname: str, items: list[dict], key: str) -> int:
        path = [subdir, fname]
        existing = self._read_artifact(*path, default=[])
        seen = {it.get(key) for it in existing}
        added = 0
        for it in items:
            if it.get(key) in seen:
                continue
            existing.append(it)
            seen.add(it.get(key))
            added += 1
        if added:
            self._write_artifact(existing, *path)
            self._bump(subdir_map(subdir, fname), added)
        return added

    def _bump(self, counter: str, n: int):
        state = self._load_engagement()
        state.setdefault("counts", {})[counter] = state.get("counts", {}).get(counter, 0) + n
        self._save_engagement(state)

    def artifacts(self, subdir: str, fname: str):
        return self._read_artifact(subdir, fname, default=[])

    # ----- model (Map) ---------------------------------------------------------
    def write_model(self, app: dict, auth: dict):
        self._write_artifact(app, "model", "app.json")
        self._write_artifact(auth, "model", "auth.json")

    def model(self) -> tuple[dict, dict]:
        return (self._read_artifact("model", "app.json", default={}),
                self._read_artifact("model", "auth.json", default={}))

    # ----- analysis (Think) -----------------------------------------------------
    def add_attack_paths(self, paths: list[dict]) -> int:
        n = self._upsert("analysis", "attack-paths.json", paths, "id")
        state = self._load_engagement()
        state.setdefault("counts", {})["attack_paths"] = len(
            self._read_artifact("analysis", "attack-paths.json", default=[]))
        self._save_engagement(state)
        return n

    def attack_paths(self) -> list[dict]:
        return self._read_artifact("analysis", "attack-paths.json", default=[])

    # ----- testing (Exploit) -----------------------------------------------------
    def add_hypotheses(self, hypos: list[dict]) -> int:
        n = self._upsert("testing", "hypotheses.json", hypos, "id")
        state = self._load_engagement()
        state.setdefault("counts", {})["hypotheses"] = len(
            self._read_artifact("testing", "hypotheses.json", default=[]))
        self._save_engagement(state)
        return n

    def hypotheses(self) -> list[dict]:
        return self._read_artifact("testing", "hypotheses.json", default=[])

    def update_hypothesis(self, hid: str, patch: dict):
        hypos = self._read_artifact("testing", "hypotheses.json", default=[])
        for h in hypos:
            if h.get("id") == hid:
                h.update(patch)
                break
        self._write_artifact(hypos, "testing", "hypotheses.json")

    def record_result(self, result: dict):
        results = self._read_artifact("testing", "results.json", default=[])
        results.append(result)
        self._write_artifact(results, "testing", "results.json")

    # ----- findings (Prove) -------------------------------------------------------
    def add_finding(self, finding: dict) -> str:
        fid = finding.get("id") or f"F-{len(self._read_artifact('findings', 'index.json', default=[])) + 1:03d}"
        finding["id"] = fid
        finding.setdefault("status", "candidate")
        self._write_artifact(finding, "findings", f"{fid}.json")
        index = self._read_artifact("findings", "index.json", default=[])
        if fid not in index:
            index.append(fid)
            self._write_artifact(index, "findings", "index.json")
        state = self._load_engagement()
        state.setdefault("counts", {})["findings"] = len(index)
        self._save_engagement(state)
        return fid

    def findings(self) -> list[dict]:
        index = self._read_artifact("findings", "index.json", default=[])
        out = []
        for fid in index:
            f = self._read_artifact("findings", f"{fid}.json", default=None)
            if f:
                out.append(f)
        return out

    def get_finding(self, fid: str) -> dict | None:
        return self._read_artifact("findings", f"{fid}.json", default=None)

    def update_finding(self, fid: str, patch: dict):
        f = self.get_finding(fid)
        if not f:
            raise BlackboardError(f"unknown finding {fid}")
        f.update(patch)
        self._write_artifact(f, "findings", f"{fid}.json")

    def evidence_dir(self, fid: str) -> str:
        d = os.path.join(self.dir, "evidence", fid)
        os.makedirs(d, exist_ok=True)
        return d

    # ----- snapshot for prompts ---------------------------------------------------
    def snapshot(self, max_items: int = 200) -> dict:
        """Compact, prompt-sized view of the blackboard. Agents receive this as context."""
        s = self.summary()
        snap = {
            "target": s["target"],
            "program": s["program"],
            "phase": s["phase"],
            "stage_status": s["stage_status"],
            "counts": s["counts"],
            "scope": self.scope(),
            "assets": self.artifacts("surface", "assets.json")[:max_items],
            "endpoints": self.artifacts("surface", "endpoints.json")[:max_items],
            "js": self.artifacts("surface", "js.json")[:max_items],
            "secrets": self.artifacts("surface", "secrets.json")[:max_items],
            "attack_paths": self.attack_paths()[:max_items],
            "hypotheses": self.hypotheses()[:max_items],
            "findings": self.findings()[:max_items],
            "model": self.model()[0],
            "auth": self.model()[1],
        }
        return snap


def _next_phase(phase: str) -> str:
    idx = STAGES.index(phase)
    return STAGES[idx + 1] if idx + 1 < len(STAGES) else "report"


def subdir_map(subdir: str, fname: str) -> str:
    m = {"assets.json": "assets", "endpoints.json": "endpoints", "js.json": "js",
         "secrets.json": "secrets", "attack-paths.json": "attack_paths",
         "hypotheses.json": "hypotheses"}
    return m.get(fname, fname.split(".")[0])


def _default_scope_md(target: str, program: str) -> str:
    return f"""# Scope — {target}

_Program: {program}_

## In scope
- `*.{target}`

## Out of scope
- _(list explicitly out-of-scope assets here)_

## Accepted impact
- _(list the program's accepted impact classes, e.g. RCE, SQLi, IDOR, SSRF, stored XSS)_

## Rules
- No automated scanning above program rate limits
- Use dedicated test accounts only
- Stop immediately on anything resembling production data
- Do not test third-party / acquired assets not listed above

## Test accounts
- _(email / role / privileges per account)_
"""


def _selftest():
    import shutil
    import tempfile
    d = tempfile.mkdtemp()
    try:
        e = Engagement(base=d, target="acme.com").create("acme.com", "hackerone")
        assert e.exists()
        assert e.add_assets([{"host": "a.acme.com", "url": "https://a.acme.com/"},
                             {"host": "a.acme.com", "url": "https://a.acme.com/"}]) == 1  # dedup
        assert e.add_endpoints([{"url": "https://a.acme.com/api/user/1", "method": "GET", "auth": "user"}]) == 1
        assert e.add_attack_paths([{"id": "AP-001", "title": "IDOR on /api/user/{id}"}]) == 1
        assert e.add_hypotheses([{"id": "H-001", "attack_path_id": "AP-001", "title": "swap id"}]) == 1
        fid = e.add_finding({"title": "IDOR", "vuln_class": "idor"})
        assert fid == "F-001"
        e.set_phase("recon")
        e.complete_phase("recon", "5 assets")
        s = e.summary()
        assert s["phase"] == "map" and s["counts"]["assets"] == 1 and s["counts"]["findings"] == 1
        snap = e.snapshot()
        assert snap["assets"][0]["host"] == "a.acme.com"
        # resume across instances
        e2 = Engagement(base=d, target="acme.com")
        assert e2.exists() and e2.summary()["phase"] == "map"
        print("blackboard.py self-test: PASS")
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    _selftest()