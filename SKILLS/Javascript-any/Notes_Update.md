
## 1- Update One (Pending):

Please modify Phase 6 to make it more thorough and recursive. Train it so that when it analyzes a URL, it extracts all discovered links from that page, then analyzes each of those links using the methodology defined in the skills. If any of those links reveal additional links, it should continue recursively, repeating the same process until no new links are found.


<img width="2800" height="4089" alt="mermaid-diagram" src="https://github.com/user-attachments/assets/48ab63ca-4629-4ba0-b6ab-9717ddb80f85" />



Recursive JavaScript Processing Workflow

Receive the original authorized JavaScript file
    ↓
Phase 2 — Retrieve the JavaScript response into memory
    ↓
Phase 3 — Read the complete JavaScript response
    ↓
Phase 4 — Build a mental model of the file
    ↓
Phase 5 — Apply all eight security analysis categories
    ↓
Phase 6 — Normalize and correlate endpoints, parameters, and findings
    ↓
Phase 7 — Search the analyzed JavaScript for referenced JavaScript files
    ↓
Were new JavaScript files discovered?
    ├── No
    │     ↓
    │   Mark the current file as fully analyzed
    │     ↓
    │   Check the pending JavaScript queue
    │
    └── Yes
          ↓
        Resolve every discovered JavaScript reference into an absolute URL
          ↓
        Validate that each URL is authorized and actually points to JavaScript
          ↓
        Remove files that were already analyzed or already added to the queue
          ↓
        Add every new unique JavaScript file to the pending JavaScript queue
          ↓
        Mark the current file as fully analyzed
          ↓
        Select the next JavaScript file from the queue
          ↓
        Return to Phase 2

Continue this loop:

Phase 2
   ↓
Phase 3
   ↓
Phase 4
   ↓
Phase 5
   ↓
Phase 6
   ↓
Phase 7
   ↓
Discover new JavaScript files
   ↓
Add unique files to the queue
   ↓
Return to Phase 2 for the next file

The process ends only when:

No JavaScript file remains in the pending queue
AND
Every discovered unique authorized JavaScript file has been fully processed
through Phases 2, 3, 4, 5, 6, and 7

Mandatory Rule

Whenever Phase 7 discovers a new authorized JavaScript file, do not analyze it
partially inside Phase 7.

Add it to the pending queue and process it from Phase 2 through Phase 7 using
the same complete workflow as the original file.

Maintain these states:

Pending:
Discovered JavaScript files waiting to start Phase 2

Processing:
The JavaScript file currently passing through Phases 2–7

Completed:
JavaScript files that fully passed through Phases 2–7

Skipped:
Duplicate, out-of-scope, unreachable, or non-JavaScript resources

Before adding a discovered file to the queue, confirm that it is not already in:

Pending
Processing
Completed
Skipped

Do not stop after finishing the original JavaScript file. Continue processing
newly discovered files until the pending queue is empty.


## 2- Saving results in correct, organized paths.(confirm)
```
js-intelligence/
└── {main-domain}/
    └── {subdomain-name}/
        ├── input/
        │   ├── urls.txt
        │   └── js-urls.txt
        ├── runtime/
        │   ├── url-index.json
        │   └── source-map-notes/
        ├── analysis/
        │   ├── file-notes/
        │   ├── endpoints.json
        │   ├── parameters.json
        │   ├── secrets-redacted.json
        │   ├── postmessage.json
        │   ├── dom-xss.json
        │   ├── storage.json
        │   └── access-control.json
        ├── requests/
        │   ├── request-log.jsonl
        │   └── response-bodies/
        └── reports/
            ├── summary.md
            └── full-report.md
```
## 3- add (Confirm)

Add a feature to the skills that searches for all domains present in the file, regardless of whether they are subdomains or domains.
