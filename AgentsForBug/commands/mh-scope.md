---
description: Read or update the scope for a MultiHunter engagement: /mh-scope acme.com [--set scope.json | --edit]. Shows current in/out-of-scope, accepted impact, and rules.
agent: build
---

Manage the scope of the MultiHunter engagement for the target in $ARGUMENTS.

- `mh scope <target>` — print the current machine-readable scope (in_scope,
  out_of_scope, accepted_impact, rules, test_accounts).
- If the user wants to set scope from a file: `mh scope <target> --set <file>`.
- If the user wants to author/edit scope interactively, open `scope.md` in the
  engagement folder, help them fill in in-scope assets, out-of-scope assets,
  accepted impact, and rules from the program page text they provide, and then
  update `scope.json` to match (`mh scope <target> --set scope.json`).

Remind the user that the scope file is the enforcement boundary: recon and
exploit will refuse out-of-scope assets. Do not begin testing.