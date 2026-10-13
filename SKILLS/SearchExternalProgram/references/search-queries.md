# Query Bank — paid, fresh, low-competition

Run these across the search tools. Replace `{YEAR}` with the current year,
`{MONTH}` with the current month name, and use `after:{DATE}` (**≈60 days ago** for
this tighter, unfarmed focus) where supported. The goal is **newly announced,
CASH-PAYING, external/self-hosted** programs that **few researchers have reached
yet**.

Three biases layered into every query:
- **Paid** — pair reward wording with currency/amount (`"we pay" $`, `bounty reward`).
- **Fresh** — date restriction + launch wording (`after:{DATE}`, "just launched").
- **Unfarmed** — prefer the company's OWN page/security.txt; treat aggregator hits
  as a *signal to pivot* to the source, and down-rank anything already crowded.

Rotate phrasing between runs — repeating identical queries returns identical pages.
Each run, vary at least a third of the queries (synonyms, different month, different
site filter) so the sweep keeps surfacing new results instead of the same cache.

**Reject on sight** (don't record): "no monetary reward", "swag only", "hall of
fame", "points only", "recognition only", platform-only programs.

---

## 1. Google — direct, PAID company programs

```
"report a vulnerability" "we pay" ("$" OR bounty) security.txt after:{DATE}
"bug bounty" "launched" "$" {MONTH} {YEAR} -hackerone -bugcrowd -intigriti -yeswehack
"we pay security researchers" "$" site:*.com after:{DATE}
"cash reward" "report a security issue" {YEAR} -platform
"vulnerability reward program" "up to $" -google -microsoft -apple after:{DATE}
inurl:security.txt "Contact:" ("bounty" OR "reward") -hackerone -bugcrowd
"security@" "we offer" ("$" OR "cash") "vulnerability" {YEAR}
"self-hosted" OR "in-house" bug bounty "pays" {YEAR}
"now offering" "monetary reward" vulnerability {MONTH} {YEAR}
("launched" OR "introducing") "bug bounty" "$" site:*.io after:{DATE}
```

## 2. security.txt / SECURITY.md discovery

```
inurl:/.well-known/security.txt Contact
site:github.com SECURITY.md "bounty" "security@"
"security.txt" new program {MONTH} {YEAR}
inurl:security.txt "Preferred-Languages" "Policy"
```
After a hit: fetch `https://<domain>/.well-known/security.txt` directly to pull the
`Contact:` email and `Policy:` page.

## 3. LinkedIn — announcements

```
site:linkedin.com/posts "bug bounty" "launch" {YEAR}
site:linkedin.com/posts "vulnerability disclosure program" {MONTH} {YEAR}
site:linkedin.com "we're excited to announce" "security researchers" reward
site:linkedin.com/pulse "responsible disclosure" "reward" {YEAR}
```

## 4. X / Twitter — launches

```
site:twitter.com "bug bounty" launch {YEAR}
site:x.com "VDP" OR "vulnerability disclosure" announced
site:twitter.com "now accepting" "security reports" reward
("just launched" OR "excited to launch") "bug bounty" -platform {MONTH} {YEAR}
```

## 5. Reddit / community

```
site:reddit.com/r/bugbounty new program {YEAR}
site:reddit.com "self hosted" bug bounty email reports
site:reddit.com/r/netsec VDP launch {MONTH} {YEAR}
```

## 6. Aggregators & indexes (use to find the company's OWN page)

```
site:disclose.io program {YEAR}
"program.json" disclose.io site:github.com
site:bugcrowd.com/programs   # only to note companies, then find their direct page
"vdp" "launched" directory {YEAR}
```

## 7. Fresh + paid signal boosters (append to any query)

```
after:{DATE}
"announced" {MONTH} {YEAR}
"just launched"  /  "now live"  /  "introducing"
"we pay"  /  "cash reward"  /  "up to $"
"$" (force a monetary token into the result)
```

## 8. Low-competition / unfarmed boosters
Used to FIND the quiet ones and to JUDGE crowding (see SKILL.md scoring).

```
# find small/niche/regional launches that the crowd hasn't hit
"bug bounty" "$" ("startup" OR "fintech" OR "saas") launch {MONTH} {YEAR}
"security.txt" new "$" site:*.io after:{DATE}
"first bug bounty" OR "our new bug bounty" "$" {YEAR}

# crowding checks — if these return a lot, mark competition=high
site:reddit.com/r/bugbounty "<company>"
site:twitter.com OR site:x.com "<company>" bug bounty
"<company>" writeup bug bounty
site:disclose.io "<company>"          # present => already farmed
```

---

## Date math
- `{DATE}` = today minus ~60 days, formatted `YYYY-MM-DD` (tighter window for
  unfarmed focus; widen to ~90 only if a run returns too little).
- Page publish date older than ~90 days → `freshness: older`; keep only if clearly
  still open, paid, AND not already crowded/in the file.

## Per-hit confirmation checklist
1. **Fetch the page.** Live (not closed/paused/archived)?
2. **Direct channel?** email / own form / security.txt — not platform-only.
3. **PAID?** Confirm a cash reward (amount, range, "up to $", or explicit "we pay").
   Swag / HoF / points / "no monetary reward" → **drop**.
4. **Crowding?** Run the section-8 checks → set `competition` low/medium/high.
5. Pull: company, email, bounty_range, program_page, announce date, competition,
   source.
6. Drop anything failing 1–3; down-rank `high` competition unless user wants all.
