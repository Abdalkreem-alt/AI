---
name: external-program-hunter
description: >
  Professionally and continuously hunts the web — Google, LinkedIn, X/Twitter,
  Reddit, GitHub, Mastodon and company/security pages — for companies running their
  OWN external / self-hosted security program reachable DIRECTLY (email /
  security.txt / own form), never routed through a managed platform. GOAL: surface
  brand-new, just-launched external programs that NO researcher has reached yet.
  HARD EXCLUSIONS: any program listed on HackerOne, Bugcrowd, Intigriti or
  YesWeHack (or any managed platform) is dropped entirely and never appears; any
  Web3 / crypto / blockchain program is ignored; any program whose policy says it
  does NOT pay is dropped. It ACCEPTS three kinds: (1) pays and states the amount,
  (2) says it rewards but without an amount, (3) only gives an email/channel to
  report to without mentioning reward (tagged to ask them). Results always go to the
  single fixed file ~/ClientExternal.md — every run updates it in place, appending
  new finds above the existing ones. Columns: Company, Contact email, Bounty range,
  Program/announcement page, Date found, Freshness, Competition, Source. Trigger
  phrases: "external program", "self-hosted bounty", "ClientExternal", "programs by
  email", "security.txt hunt", "new/unfarmed external programs".
---

# External Program Hunter

## Purpose (read first)
**The whole point of this skill is to surface brand-new, just-launched EXTERNAL
security programs that no researcher has reached yet** — reachable directly at the
company (email, their own `/security` page or form, or a `security.txt` `Contact:`),
never through a managed platform. Freshness and zero-competition are the goal;
anything already crowded or already on a platform is worthless here.

Results **always** go to the single fixed file `~/ClientExternal.md`. Every run
**updates that same file in place** — new finds are appended **above** the existing
rows (newest on top); existing rows are preserved and de-duplicated. The file is
never replaced or moved.

---

## HARD EXCLUSIONS — drop entirely, never output

These are absolute. A target matching **any** of these is discarded and must never
appear in the file, even if everything else about it is perfect:

1. **Listed on a managed platform.** If the program is hosted on / routed through
   **HackerOne, Bugcrowd, Intigriti, YesWeHack** — or any other managed marketplace
   (Immunefi, HackenProof, etc.) — **drop it completely.** This applies even if the
   company also has its own page: if the reporting path the world sees is the
   platform, it is not a fresh external find. (Signals: a `hackerone.com/…`,
   `bugcrowd.com/…`, `intigriti.com/…`, `yeswehack.com/…` program URL; "submit via
   HackerOne"; a platform "Submit report" button as the primary channel.)
2. **Web3 / crypto / blockchain.** Ignore any program for a crypto, DeFi, smart
   contract, token, wallet, chain, NFT, or blockchain product. Drop it.
3. **Explicitly non-paying.** If the policy/page states it does **not** pay — "no
   monetary reward", "no bounty", "recognition only", "we are unable to offer
   rewards" — **drop it.** (Note: a program that is simply *silent* about reward is
   NOT this case — see ACCEPT #3 below.)

---

## ACCEPT — three valid kinds (all go in the file)

A target is valid when it has a **direct external reporting channel** (own email /
security.txt / own form), is open to external researchers, is **live**, and is NOT
hit by any hard exclusion above. Within that, accept all three of these and **tag
the reward type clearly** in the Bounty Range column:

1. **Pays, amount stated** → `bounty_range` = the figure/range, e.g. `$500–$5,000`,
   `up to $10k`, `€250+`.
2. **Rewards, no amount** → the page says it rewards/pays but hides the number →
   `bounty_range` = `will reward (amount undisclosed)`.
3. **Email/channel only, reward not mentioned** → the page only says something like
   "report vulnerabilities to security@…" and says nothing about reward (neither
   yes nor no) → `bounty_range` = `email only — reward unstated (ask them)`. This is
   still worth recording: contacting them to ask if they reward is part of the play.

> Only kind #3's silence is accepted. An explicit "we don't pay" is a HARD
> EXCLUSION (#3 above), not kind #3 here.

**Evidence required:** you must have fetched the actual page and confirmed it is
live and external before writing the row.

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

- **One-shot hunt** (default): one full sweep, dedupe against the existing file,
  append new rows **above** the old ones, report.
- **Continuous / autonomous** (when the user says دائم / مستمر / always): do one
  hunt now, then set up a **scheduled task** (see `references/scheduling.md`) that
  re-invokes this skill on a cadence. **Every run writes to the same fixed
  `~/ClientExternal.md`**, updating it in place and appending only newly discovered
  programs. Confirm the cadence before scheduling.

---

## Procedure

### 0. Prep
- The merge script creates `~/ClientExternal.md` with the canonical header if
  absent, and updates it **in place** on every later run. Never write results
  anywhere else, and never replace the file — only append + dedupe.
- Load the query bank from `references/search-queries.md`.

### 1. Professional search sweep (fresh + unfarmed + direct-channel biased)
Run queries across every channel, strongly preferring the **last 14–60 days**. Use
date restriction where supported (`after:YYYY-MM-DD`). Channels (full list in the
query bank): Google web, LinkedIn posts, X/Twitter, Reddit, GitHub (`security.txt`
/ `SECURITY.md`), Mastodon/infosec, and company security pages.

Method, in order:
1. **Cast wide** with freshness + direct-channel keywords.
2. **Pivot to the source of truth.** For any hit, go to the company's own
   `https://<domain>/.well-known/security.txt` and `/security` page — that is where
   the real contact and the reward wording live.
3. **Fetch before trusting.** Always WebFetch the actual page; never take the email
   or the reward from a search snippet.
4. **Run the exclusion gate** on every candidate (see HARD EXCLUSIONS):
   platform-hosted? → drop. Web3/crypto? → drop. Says it doesn't pay? → drop.
5. **Competition check.** Quickly gauge how crowded it is (see scoring above).

### 2. Extract per program
- `company`
- `email` — reporting contact (prefer `security.txt` `Contact:` / real mailbox;
  `N/A` if only a form — then put the form URL in `program_page`)
- `bounty_range` — **tag the reward type** (see ACCEPT):
  - amount stated → the figure/range, e.g. `$250–$5,000`, `up to $10k`
  - rewards but no amount → `will reward (amount undisclosed)`
  - email/channel only, reward not mentioned → `email only — reward unstated (ask them)`
- `program_page` — the page you fetched as evidence
- `freshness` — `announced <YYYY-MM-DD>` or `fresh` / `recent`
- `competition` — `low` / `medium` / `high`
- `source` — Google / LinkedIn / X / GitHub / Reddit / security.txt …

### 3. Merge & write (always the same fixed file)
Collect programs as a JSON array and pipe to the merge script. It enforces the
exclusions (platform-hosted, Web3, explicitly-non-paying → dropped), dedupes by
email+domain against existing rows, and appends only new ones **above** the old
ones in `~/ClientExternal.md`:

```bash
python3 scripts/merge_programs.py --input /path/to/found.json --out ~/ClientExternal.md
```

`--out` stays `~/ClientExternal.md` on every run — do not change it, do not create a
second file. The script owns the format, the exclusion filter, and the dedupe — do
not hand-edit the table.

### 4. Report
State how many NEW programs were added, how many were dropped (and why: platform /
Web3 / non-paying / duplicate), and list the freshest low-competition 3–5 by name.
Mention the file path.

---

## Quality gates (before a row is written)

- **Exclusions first.** Platform-hosted (HackerOne/Bugcrowd/Intigriti/YesWeHack/…),
  Web3/crypto, or explicitly-non-paying → **drop** (the script also enforces).
- **Fresh & unfarmed over famous.** Prefer low-competition, just-launched programs.
- **Direct channel required.** Reports must reach the company directly.
- **Evidence or drop it.** No fetched `program_page` → no row.
- **No fabrication.** Never invent an email or a reward. Unknown contact → `N/A`;
  unknown reward → the correct `email only — reward unstated` / `will reward
  (amount undisclosed)` tag, never a made-up figure.

## Ethics / scope note
This skill only *discovers and catalogs publicly announced* external programs and
their public reporting contacts. It does not test, scan, or attack anything. All
testing must stay within each program's published scope and rules.
