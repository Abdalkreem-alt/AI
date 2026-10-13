# Continuous / recurring hunting

A single chat turn ends; it cannot "run forever". To make the hunt **continuous**,
schedule recurring runs. Each run is a fresh session that invokes this skill, does
one sweep, and appends only newly discovered programs to `~/ClientExternal.md`.

## Recommended cadence
- Active hunting: every **6–12 hours**.
- Light monitoring: **once daily** (early morning).

Daily is usually enough — new external programs don't appear by the minute, and a
tighter cadence mostly re-scans the same pages. Confirm the cadence with the user
before creating the schedule.

## Setting it up (inside Claude Code / this environment)
Use the environment's scheduled-task tool (the `create_trigger` family). The task
prompt should be self-contained, e.g.:

> Run the `external-program-hunter` skill: do one full freshness-biased search
> sweep for newly announced external/self-hosted bug-bounty and VDP programs that
> accept researcher reports directly and reward them, then append any new ones to
> ~/ClientExternal.md using scripts/merge_programs.py. Report how many new programs
> were added.

- Make it recurring (daily or every N hours), in the user's timezone.
- One-shot "remind me / run once later" → a single scheduled run instead.

## If scheduling tools are not available in the session
Fall back to an OS cron entry that launches the agent headless, or tell the user to
re-run `/external-program-hunter` manually. Do not claim continuous operation that
the environment can't actually provide.

## Keeping results fresh each run
- Rotate ~1/3 of the queries each run (see search-queries.md) so the sweep doesn't
  keep hitting the same cached pages.
- The merge script dedupes, so re-runs never create duplicate rows — only genuinely
  new programs get appended.
