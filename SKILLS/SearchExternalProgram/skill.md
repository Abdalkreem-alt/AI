---
name: external-program-hunter
description: >
  Professionally and continuously hunts the web — Google, LinkedIn, X/Twitter,
  Reddit, GitHub, Mastodon and company/security pages — for companies running their
  OWN external / self-hosted bug-bounty program that PAYS CASH and accepts reports
  directly (email / security.txt / own form), NOT the big managed platforms. It
  REJECTS unpaid VDPs, swag-only, and "thanks/hall-of-fame only" programs. Tuned to
  surface FRESH, newly announced programs that few or no researchers have reached
  yet (low competition / unfarmed). Appends scored rows to ~/ClientExternal.md:
  Company, Contact email, Bounty range, Program/announcement page, Date found,
  Freshness, Competition, Source. Use when the user asks to find, hunt, discover,
  or monitor PAID external/self-hosted bug-bounty programs, private security.txt
  contacts, "send reports to" security contacts, or companies paying researchers
  directly. Trigger phrases: "external program", "self-hosted bounty", "find paid
  programs", "ClientExternal", "programs by email", "security.txt hunt",
  "unfarmed / low-competition programs".
---

# External Program Hunter (paid, fresh, low-competition)

Find companies that run their **own, cash-paying** bug-bounty program — reports go
to the company **directly** (email, their own `/security` page, their own form, or
a `security.txt` `Contact:`) — and that **almost no researcher has reached yet.**
Write scored results to `~/ClientExternal.md`, newest first.

Two edges define this skill:

1. **Paid only.** A real cash bounty is mandatory. Unpaid VDPs, swag-only, and
   hall-of-fame/thanks-only programs are **rejected**.
2. **Unfarmed freshness.** It targets *recently announced* programs that have **not
   yet reached the researcher crowd** — low competition, not the lists everyone
   already mines.

---

## What counts as a valid target

INCLUDE a company only if **ALL** hold:

1. **Own external channel.** Reports go directly to the company — email, their own
   security page/form, or a `security.txt` `Contact:` line they publish.
2. **Open to external researchers** (not invite-only internal red teams).
3. **CASH reward.** There is a monetary bounty: a stated amount, a range, "up to
   $X", or an explicit "we pay / cash rewards" statement. **This is required.**
4. **Evidence.** You fetched the announcing/program page yourself and confirmed it
   is live.

REJECT (do not write a row):

- **Unpaid VDP** / responsible-disclosure-only / "we do not offer monetary rewards".
- **Swag-only**, points-only, or **hall-of-fame / thanks-only** recognition.
- Programs that exist **only** on a managed marketplace (HackerOne, Bugcrowd,
  Intigriti, YesWeHack, Immunefi, HackenProof, etc.) with **no** direct/off-platform
  channel. (If a company publishes its OWN paid page/email AND also lists on a
  platform, include it and note both in `source`.)
- Dead / archived / closed / paused programs.
- Anything where you could not confirm a cash reward — "undisclosed but paid" is
  allowed only when the page explicitly says it pays; otherwise reject.

> If the user later says "include VDPs / unpaid too", relax rule 3 for that run only.

---

## Competition scoring — surfacing the unfarmed

The user's priority: **results no researcher has reached yet.** For each candidate,
estimate how crowded it already is and record a `competition` label. Prefer LOW.

Signals that a program is **LOW competition (GOOD — prioritize):**
- Announced very recently (days–few weeks) and not yet reshared widely.
- Found on the **company's own page / security.txt**, not on an aggregator.
- Little or no chatter on X/Reddit/bug-bounty writeups; not in public program lists.
- Niche/regional/mid-size company, newly launched page.

Signals that a program is **HIGH competition (deprioritize / usually skip):**
- Already indexed by disclose.io or big aggregator "live program" lists.
- Many recent writeups, tweets, or a crowded platform leaderboard.
- Large well-known brand with a long-running program.

Set `competition` to `low`, `medium`, or `high`. **Default the sweep to writing
only `low` and `medium`;** include `high` only if the user asked for completeness.
Aggregators (disclose.io etc.) are used as *negative* signals here — a program
sitting in them is, by definition, already farmed — but still useful to **pivot
from** toward the company's own freshly announced page.

---

## Operating modes

- **One-shot hunt** (default): one full sweep, dedupe, append new paid rows, report.
- **Continuous / autonomous** (when the user says دائم / مستمر / always): do one
  hunt now, then set up a **scheduled task** (see `references/scheduling.md`) that
  re-invokes this skill on a cadence. Each run appends only newly discovered paid
  programs. Confirm the cadence before scheduling.

---

## Procedure

### 0. Prep
- The merge script creates `~/ClientExternal.md` with the canonical header if absent.
- Load the query bank from `references/search-queries.md`.

### 1. Professional search sweep (freshness + paid + low-competition biased)
Run queries across every channel, strongly preferring the **last 14–60 days**. Use
date restriction where supported (`after:YYYY-MM-DD`). Channels (full list in the
query bank): Google web, LinkedIn posts, X/Twitter, Reddit, GitHub (`security.txt`
/ `SECURITY.md`), Mastodon/infosec, and company security pages.

Method, in order:
1. **Cast wide** with freshness + paid keywords.
2. **Pivot to the source of truth.** For any hit, go to the company's own
   `https://<domain>/.well-known/security.txt` and `/security` page — that is where
   the real contact and the "we pay" wording live.
3. **Fetch before trusting.** Always WebFetch the actual page; never take the email
   or the bounty figure from a search snippet.
4. **Competition check.** Quickly gauge how crowded it is (see scoring above).

### 2. Extract per program
- `company`
- `email` — reporting contact (prefer `security.txt` `Contact:` / real mailbox;
  `N/A` if only a form — then put the form URL in `program_page`)
- `bounty_range` — the cash figure/range (e.g. `$250–$5,000`, `up to $10k`). If the
  page says it pays but hides amounts, use `paid (amount undisclosed)`. **Never
  write a row whose reward is swag/unpaid.**
- `program_page` — the page you fetched as evidence
- `freshness` — `announced <YYYY-MM-DD>` or `fresh` / `recent`
- `competition` — `low` / `medium` / `high`
- `source` — Google / LinkedIn / X / GitHub / Reddit / security.txt …

### 3. Merge & write
Collect programs as a JSON array and pipe to the merge script. It enforces the
**paid-only filter** (drops swag/unpaid/hall-of-fame automatically), dedupes by
email+domain against existing rows, and appends only new ones, newest-first:

```bash
python3 scripts/merge_programs.py --input /path/to/found.json --out ~/ClientExternal.md
# add --include-unpaid only if the user explicitly asked to keep VDPs this run
```

The script owns the file format, the paid filter, and the dedupe — do not hand-edit.

### 4. Report
State how many NEW paid programs were added, how many were dropped as
unpaid/swag, how many as duplicates, and list the freshest low-competition 3–5 by
name. Mention the file path.

---

## Quality gates (before a row is written)

- **Paid or drop it.** No confirmed cash reward → no row. (The script also enforces.)
- **Fresh & unfarmed over famous.** Prefer low-competition, recently announced.
- **Evidence or drop it.** No fetched `program_page` → no row.
- **Own channel.** Platform-only → drop.
- **No fabrication.** Never invent an email or a bounty figure. Unknown contact →
  `N/A`; a wrong `security@` is worse than a blank.

## Ethics / scope note
This skill only *discovers and catalogs publicly announced* paid programs and their
public reporting contacts. It does not test, scan, or attack anything. All testing
must stay within each program's published scope and rules.
