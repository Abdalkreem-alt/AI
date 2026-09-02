---
description: Show MultiHunter engagement status for a target: /mh-status acme.com. Prints phase, stage status, counts, and recent handoffs.
agent: build
---

Show the status of the MultiHunter engagement for $ARGUMENTS.

Run `mh status <target>` (target = the argument) and present the output to the
user. If the engagement does not exist, say so and suggest `mh new <target>`.

Also append the last few entries of `mh log <target> --tail 10` so the user
sees the recent activity, then stop. Do not start or continue the pipeline.