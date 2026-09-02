#!/usr/bin/env python3
"""
dedup.py — duplicate-finding detection for the Prove stage.

Before a finding reaches the Report stage it must be checked against (a) the
program's previously disclosed reports / hacktivity and (b) the other findings
already in this engagement. This module provides deterministic similarity
helpers the duplicatecheck agent can lean on, plus a registry that marks
findings as duplicates of one another.

Signals used for dedup:
  - exact (endpoint normalized, vuln class, HTTP method, parameter) match
  - normalized-title similarity (token overlap)
  - URL/param overlap
"""
import re
from difflib import SequenceMatcher

STOPWORDS = {"the", "a", "an", "on", "in", "of", "to", "for", "and", "or",
             "with", "via", "in", "at", "by", "is", "are", "vulnerability",
             "vulnerabilities", "issue", "finding", "endpoint", "application"}


def normalize_url(url: str) -> str:
    """Strip scheme, query ordering, trailing slash, and common dynamic segments."""
    if not url:
        return ""
    url = url.strip()
    url = re.sub(r"^https?://", "", url, flags=re.I)
    url = url.split("?")[0]
    url = url.rstrip("/")
    url = re.sub(r"/\d+", "/{id}", url)          # numeric ids -> {id}
    url = re.sub(r"\b[0-9a-f]{8,32}\b", "{uuid}", url, flags=re.I)  # uuids
    return url.lower()


def tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (title or "").lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def title_similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return inter / max(len(ta), len(tb))


def finding_key(f: dict) -> tuple:
    return (normalize_url(f.get("endpoint", "")),
            (f.get("vuln_class") or "").lower(),
            (f.get("method") or "").upper(),
            normalize_url(f.get("param") or ""))


def find_duplicates(findings: list[dict], title_threshold: float = 0.6) -> list[dict]:
    """Return a list of {source, duplicate_of, score, signals} for findings
    that collide on the same (endpoint, class, method, param) key or whose
    titles are very similar."""
    out = []
    by_key: dict[tuple, list[dict]] = {}
    for f in findings:
        by_key.setdefault(finding_key(f), []).append(f)
    for key, group in by_key.items():
        for i in range(1, len(group)):
            out.append({"source": group[i].get("id"), "duplicate_of": group[0].get("id"),
                        "score": 1.0, "signals": ["same endpoint/class/method/param"]})
    # title-similarity pass (keeps the first as canonical)
    seen_canonical = set()
    for i, f in enumerate(findings):
        if f.get("id") in {d["source"] for d in out}:
            continue
        for j in range(i + 1, len(findings)):
            g = findings[j]
            if g.get("id") in {d["source"] for d in out}:
                continue
            score = title_similarity(f.get("title", ""), g.get("title", ""))
            if score >= title_threshold:
                out.append({"source": g.get("id"), "duplicate_of": f.get("id"),
                            "score": round(score, 2), "signals": ["similar title"]})
                break
    return out


def apply_duplicates(findings: list[dict], dups: list[dict]) -> int:
    """Mark findings as status=duplicate based on dedup results. Returns count."""
    n = 0
    by_id = {f.get("id"): f for f in findings}
    for d in dups:
        f = by_id.get(d["source"])
        if f and f.get("status") != "duplicate":
            f["status"] = "duplicate"
            f["duplicate_of"] = d["duplicate_of"]
            f["dup_score"] = d["score"]
            n += 1
    return n


def _selftest():
    findings = [
        {"id": "F-001", "endpoint": "https://a.com/api/user/42", "method": "GET",
         "vuln_class": "IDOR", "param": "id", "title": "IDOR on user endpoint"},
        {"id": "F-002", "endpoint": "https://a.com/api/user/43", "method": "GET",
         "vuln_class": "IDOR", "param": "id", "title": "IDOR on user endpoint"},
        {"id": "F-003", "endpoint": "https://a.com/api/order", "method": "POST",
         "vuln_class": "SSRF", "param": "url", "title": "SSRF via order url"},
    ]
    dups = find_duplicates(findings)
    assert any(d["source"] == "F-002" and d["duplicate_of"] == "F-001" for d in dups)
    assert not any(d["source"] == "F-003" for d in dups)
    n = apply_duplicates(findings, dups)
    assert n == 1 and findings[1]["status"] == "duplicate"
    assert normalize_url("HTTPS://A.com/API/user/42?x=1") == "a.com/api/user/{id}"
    assert normalize_url("https://a.com/x/abc12345") == "a.com/x/{uuid}"
    print("dedup.py self-test: PASS")


if __name__ == "__main__":
    _selftest()