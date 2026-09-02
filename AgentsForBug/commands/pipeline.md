---
description: Run the MultiHunter pipeline. Starts or resumes the multi-agent security-testing workflow for a target: /pipeline acme.com [--program hackerone]. Scaffolds the engagement if needed, then hands off to the Director.
agent: director
---

Run the MultiHunter multi-agent security-testing pipeline for the target in
$ARGUMENTS.

First, load the `multi-hunter` skill for the canonical workflow.

If the engagement does not exist yet, scaffold it:
`mh new <target> --program hackerone` (parse any target details from
$ARGUMENTS). If it exists, resume from its current phase.

Then execute the pipeline as Director:

1. Read `engagement.json` and `scope.md` in the engagement folder.
2. Dispatch each stage in dependency order using the Task tool with the stage
   agent as `subagent_type` (recon → jsintel/apianalyst → map → think →
   exploit → prove → duplicatecheck → report). Pass each agent the blackboard
   context (its stage reads the engagement folder directly).
3. Review each handoff; when exploit discovers new surface or attack paths,
   re-enter think (and recon if genuinely new surface) before moving on.
4. Enforce scope: never test an out-of-scope asset, never exceed program rate
   limits, stop on production data.
5. When report completes, show the operator the report path and a 5-line
   summary of the findings.

Stop and ask the operator if: the scope file is empty/unclear, test accounts
are missing, or a stage reports a blocker you cannot resolve.

Report progress as each stage completes; keep the operator informed but terse.