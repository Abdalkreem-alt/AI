#!/usr/bin/env python3
"""
merge_programs.py — merge newly found PAID external bug-bounty programs into
~/ClientExternal.md as a Markdown table, newest-first, with dedupe.

Enforces a PAID-ONLY policy: rows whose reward is swag-only, points-only,
hall-of-fame/thanks-only, or an explicit "no monetary reward" VDP are dropped,
unless --include-unpaid is passed.

Input: a JSON array of program objects. Each object may contain:
  {
    "company":      "Acme Corp",
    "email":        "security@acme.com",      # or "N/A"
    "bounty_range": "$250-$5,000",            # cash; "paid (amount undisclosed)" ok
    "program_page": "https://acme.com/security",
    "freshness":    "announced 2026-09-30",   # or "fresh" / "recent" / "unknown"
    "competition":  "low",                    # low / medium / high
    "source":       "security.txt",           # Google / LinkedIn / X / GitHub ...
    "date_found":   "2026-10-13"              # optional; defaults to today
  }

Dedupe: by strong signals (reporting email, program-page domain); company name is
only a weak fallback. New rows are inserted at the TOP (newest-first).

Usage:
  python3 merge_programs.py --input found.json --out ~/ClientExternal.md
  cat found.json | python3 merge_programs.py --out ~/ClientExternal.md   # stdin
  python3 merge_programs.py --input found.json --include-unpaid   # keep VDPs too
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from urllib.parse import urlparse

HEADER_TITLE = "# External PAID Bug-Bounty Programs — Direct Report Channels"
HEADER_NOTE = (
    "_Companies running their own external program that pay CASH and accept "
    "researcher reports directly (email / security.txt / own form). Fresh & "
    "low-competition first. Newest on top._"
)
TABLE_HEADER = (
    "| # | Company | Email | Bounty Range | Program / Announcement Page | "
    "Date Found | Freshness | Competition | Source |"
)
TABLE_SEP = (
    "|---|---------|-------|--------------|------------------------------|"
    "-----------|-----------|-------------|--------|"
)

CELL_FIELDS = [
    "company", "email", "bounty_range", "program_page",
    "date_found", "freshness", "competition", "source",
]

# Reward-signal detection for the paid-only policy.
UNPAID_RE = re.compile(
    r"\b(swag[\s-]?only|swag|sticker|t[\s-]?shirt|hall[\s-]?of[\s-]?fame|"
    r"thanks?[\s-]?only|recognition|points?[\s-]?only|kudos|no\s+(monetary|cash|"
    r"financial)\s+reward|non[\s-]?paying|unpaid|no\s+bounty)\b",
    re.I,
)
PAID_RE = re.compile(
    r"(\$|€|£|usd|eur|gbp|\bpaid\b|\bcash\b|\bbounty\b|\breward(s)?\b|\bpay(s|ing)?\b|"
    r"up\s*to|\bk\b|\d)",
    re.I,
)


def is_paid(bounty_range: str) -> bool:
    """True when the reward reads as monetary and NOT swag/unpaid/HoF."""
    s = (bounty_range or "").strip()
    if not s:
        return False
    if UNPAID_RE.search(s) and not re.search(r"[$€£]|\bup\s*to\b|\d", s):
        # swag/HoF/points/unpaid wording with no currency or amount → unpaid
        return False
    # "paid (amount undisclosed)" and any currency/amount count as paid
    if re.search(r"[$€£]|\bpaid\b|\bcash\b|up\s*to|\d", s, re.I):
        return True
    # bare "bounty"/"reward" with no unpaid wording → treat as paid
    return bool(PAID_RE.search(s)) and not UNPAID_RE.search(s)


def today() -> str:
    return dt.date.today().isoformat()


def norm_company(name: str) -> str:
    n = (name or "").strip().lower()
    n = re.sub(r"\b(inc|llc|ltd|gmbh|corp|co|plc|sa|ag|bv|oy|ab)\b\.?", "", n)
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n


def domain_of(url: str) -> str:
    if not url or url == "N/A":
        return ""
    u = url.strip()
    if not re.match(r"^https?://", u):
        u = "https://" + u
    host = (urlparse(u).netloc or "").lower()
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 2:
        host = ".".join(parts[-2:])
    return host


def signals(company: str, email: str, page: str) -> dict:
    """Strong signals (email, domain) identify a program across name variants;
    the company signal is a weak fallback used only when no strong one exists."""
    email = (email or "").strip().lower()
    dom = domain_of(page)
    strong = set()
    if email and email != "n/a":
        strong.add("email:" + email)
    if dom:
        strong.add("dom:" + dom)
    weak = {"co:" + norm_company(company)} if norm_company(company) else set()
    return {"strong": strong, "weak": weak}


def is_duplicate(sig: dict, seen_strong: set, seen_weak: set) -> bool:
    if sig["strong"] & seen_strong:
        return True
    # only fall back to the company name when there is no strong signal at all
    if not sig["strong"] and (sig["weak"] & seen_weak):
        return True
    return False


def md_escape(s: str) -> str:
    s = str(s if s is not None else "").replace("\n", " ").strip()
    return s.replace("|", "\\|")


def link_cell(url: str) -> str:
    url = (url or "").strip()
    if not url or url == "N/A":
        return "N/A"
    show = re.sub(r"^https?://", "", url)
    show = show[:48] + "…" if len(show) > 49 else show
    return f"[{md_escape(show)}]({md_escape(url)})"


def ensure_file(path: str) -> None:
    if os.path.exists(path):
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            f"{HEADER_TITLE}\n\n{HEADER_NOTE}\n\n"
            f"_Last updated: {today()}_\n\n"
            f"{TABLE_HEADER}\n{TABLE_SEP}\n"
        )


ROW_RE = re.compile(r"^\|\s*\d+\s*\|(.+)\|\s*$")


def parse_existing(path: str):
    """Return (pre_lines, existing_rows_cells, post_lines, keyset)."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    sep_idx = None
    for i, ln in enumerate(lines):
        if set(ln.strip()) <= set("|-: ") and ln.count("|") >= 7 and "-" in ln:
            # separator row of the table
            if i > 0 and lines[i - 1].lstrip().startswith("|"):
                sep_idx = i
                break
    if sep_idx is None:
        # malformed / no table — rebuild from scratch, keep nothing
        return (
            [HEADER_TITLE, "", HEADER_NOTE, "", f"_Last updated: {today()}_", "",
             TABLE_HEADER, TABLE_SEP],
            [], [], set(), set(),
        )

    # Rebuild the pre-table block with the CANONICAL header, preserving the
    # title/note/updated lines that came before the table header row. This
    # upgrades any older-format file (e.g. one missing the Competition column).
    header_row_idx = sep_idx - 1
    preface = lines[:header_row_idx]
    pre = preface + [TABLE_HEADER, TABLE_SEP]

    rows = []
    post = []
    body_ended = False
    for ln in lines[sep_idx + 1:]:
        if not body_ended and ln.strip().startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            # drop the leading "#" index column; keep only the data cells
            if cells and re.fullmatch(r"\d+", cells[0]):
                cells = cells[1:]
            cells = migrate_row(cells)
            rows.append(cells)
        else:
            if ln.strip() == "" and not body_ended:
                body_ended = True
                continue
            body_ended = True
            post.append(ln)

    seen_strong, seen_weak = set(), set()
    for cells in rows:
        # cells: company,email,bounty,page,date,fresh,source
        if len(cells) >= 4:
            sig = signals(cells[0], cells[1], _url_from_cell(cells[3]))
            seen_strong |= sig["strong"]
            seen_weak |= sig["weak"]
    return pre, rows, post, seen_strong, seen_weak


def migrate_row(cells: list) -> list:
    """Normalize a parsed data row to 8 cells:
    company,email,bounty,page,date,fresh,competition,source.
    Old rows (7 cells, no Competition before Source) get 'unknown' inserted."""
    if len(cells) == 7:
        cells = cells[:6] + ["unknown"] + cells[6:]
    return cells


def _url_from_cell(cell: str) -> str:
    m = re.search(r"\]\(([^)]+)\)", cell)
    return m.group(1) if m else cell


def row_cells(p: dict) -> list:
    return [
        md_escape(p.get("company", "")),
        md_escape(p.get("email", "") or "N/A"),
        md_escape(p.get("bounty_range", "") or "undisclosed"),
        link_cell(p.get("program_page", "")),
        md_escape(p.get("date_found") or today()),
        md_escape(p.get("freshness", "") or "unknown"),
        md_escape(p.get("competition", "") or "unknown"),
        md_escape(p.get("source", "") or ""),
    ]


def render(pre, rows, post) -> str:
    out = list(pre)
    for idx, cells in enumerate(rows, start=1):
        out.append("| " + " | ".join([str(idx)] + cells) + " |")
    out.append("")
    out.extend(post)
    text = "\n".join(out).rstrip() + "\n"
    # refresh "Last updated"
    text = re.sub(r"_Last updated: [0-9-]+_", f"_Last updated: {today()}_", text, count=1)
    return text


def load_input(args) -> list:
    if args.input:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
    else:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else []
    if isinstance(data, dict):
        data = data.get("programs", [data])
    return data or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="JSON file of programs; omit to read stdin")
    ap.add_argument("--out", default=os.path.expanduser("~/ClientExternal.md"))
    ap.add_argument("--include-unpaid", action="store_true",
                    help="keep unpaid/swag/HoF VDPs too (default: drop them)")
    args = ap.parse_args()
    out_path = os.path.expanduser(args.out)

    found = load_input(args)
    ensure_file(out_path)
    pre, existing_rows, post, seen_strong, seen_weak = parse_existing(out_path)

    new_rows = []
    skipped_dupe = skipped_unpaid = skipped_invalid = 0
    for p in found:
        if not p.get("company") and not p.get("program_page"):
            skipped_invalid += 1
            continue
        # paid-only policy
        if not args.include_unpaid and not is_paid(p.get("bounty_range", "")):
            skipped_unpaid += 1
            continue
        sig = signals(p.get("company", ""), p.get("email", ""),
                      p.get("program_page", ""))
        if is_duplicate(sig, seen_strong, seen_weak):
            skipped_dupe += 1
            continue
        seen_strong |= sig["strong"]
        seen_weak |= sig["weak"]
        new_rows.append(row_cells(p))

    # newest-first: new rows go on top of existing body
    merged = new_rows + existing_rows
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render(pre, merged, post))

    print(f"[external-program-hunter] added {len(new_rows)} new | "
          f"dropped {skipped_unpaid} unpaid/swag, {skipped_dupe} dupe, "
          f"{skipped_invalid} invalid | total now {len(merged)}")
    print(f"[external-program-hunter] file: {out_path}")


if __name__ == "__main__":
    main()
