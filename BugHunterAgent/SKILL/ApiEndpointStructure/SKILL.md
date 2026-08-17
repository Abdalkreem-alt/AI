---
name: find-api-endpoints
description: Discover and expand REST API endpoints for a target during authorized bug bounty / security testing. Takes a starting endpoint.json (e.g. produced by JS-mining/recon) and recursively builds out the full endpoint tree — resource collections, their unique-identifier child routes (id/uid/slug), nested sub-resources, and hidden path parameters — while also fuzzing API version (v1/v2/v3...) and HTTP method (GET/POST/PUT/PATCH) combinations. Use this skill whenever the user wants to map out an API's structure, expand a list of known endpoints into deeper/nested endpoints, find IDOR-relevant object identifiers, or enumerate versioned/method variants of an endpoint. Always use this skill before doing IDOR or access-control testing, since hunt-idor depends on having a complete endpoint map first.
---

# Find API Endpoints

A skill for mapping the full structure of a target's REST API during **authorized** bug bounty engagements. It starts from a seed list of known endpoints (usually produced by a JS-mining/recon step) and systematically expands that list into the complete endpoint tree: collection routes, item routes (with their unique identifiers), nested sub-resources, and version/method variants.

This is a reconnaissance/mapping skill — it does not exploit anything. It only sends requests needed to understand API shape and records observed status codes. Only ever run this against targets the user is explicitly authorized to test (e.g. a bug bounty program's in-scope assets).

## When to use this

- The user has a JS-mining or recon output (an `endpoint.json` or similar list of raw endpoints) and wants it expanded into real, testable routes.
- The user wants to understand an API's resource hierarchy before running IDOR, BOLA, or access-control checks (this feeds directly into `hunt-idor`).
- The user asks to "explore", "expand", "map", or "enumerate" an API's endpoints.

## Input

A JSON file (commonly `endpoint.json`) containing a flat list of endpoint strings discovered from JS bundles, e.g.:

```json
[
  "/api/v1/teams",
  "/api/v1/user",
  "/api/v1/projects"
]
```

## Core workflow

### 1. Start from each seed (collection) endpoint

For an endpoint like `/api/v1/teams`, send a `GET` request (using whatever session/auth context the user has provided for the target account).

- If the response is a **JSON array of objects**, this is a collection endpoint. Inspect the objects for a field that is unique per item — commonly `id`, `uid`, `slug`, `_id`, `uuid`, `key`, or similar. Prefer the field the API itself seems to key on (test by substitution — see step 3).
- If the response is a **single JSON object**, this is already an item/detail endpoint.

### 2. Build the item (detail) endpoint

Append the unique identifier value to the collection path:

```
/api/v1/teams              (collection)
/api/v1/teams/{team_id}    (item — use a real id observed in the response)
```

Record this new endpoint.

### 3. Recurse into nested resources

Fetch the item endpoint and inspect its response body for nested resources — either sub-arrays/sub-objects embedded in the payload, or fields that hint at related routes (`membersUrl`, `programId`, etc.), or just try common sub-resource names relevant to the object's domain (`members`, `program`, `settings`, `invites`, `billing`, etc.).

For each plausible sub-resource:

```
/api/v1/teams/{team_id}/members
```

Apply the same logic recursively:
- Array response → find the unique key per item → build the item route: `/api/v1/teams/{team_id}/members/{member_id}`
- Object response → treat as a leaf and go to step 4.

Keep recursing until no further nested resources are found.

### 4. Probe leaf/detail responses for hidden unique parameters

For a leaf item endpoint (e.g. a single member's detail response), don't assume the response is complete. Take **every field in the response body** and try substituting its value into the URL in place of the known identifier, one at a time:

```
/api/v1/teams/{team_id}/members/{username}
/api/v1/teams/{team_id}/members/{email}
/api/v1/teams/{team_id}/members/{uid}
```

If substituting a different field's value returns a **different but valid** response (not a 404/error), that field is also a valid identifier/routing key for this resource — record it as an alternate access path. This matters a lot for IDOR testing later, since an app may authorize on one identifier type but not another.

### 5. Fuzz API version and HTTP method for every discovered endpoint

For every endpoint discovered above, systematically vary:

- **API version**: v1, v2, v3 (and any other version pattern observed elsewhere on the target, e.g. `v1beta`, `2023-01-01`)
- **HTTP method**: GET, POST, PUT, PATCH (and DELETE only if explicitly authorized/in scope — flag this to the user before trying destructive methods)

Example expansion order for a single endpoint:

```
GET    /api/v1/teams
GET    /api/v2/teams
GET    /api/v3/teams
PATCH  /api/v1/teams
PATCH  /api/v2/teams
PATCH  /api/v3/teams
POST   /api/v1/teams
...
PUT    /api/v1/teams
...
```

Do this for every endpoint in the growing tree, not just the seeds — nested/leaf endpoints get the same version × method treatment.

## What to record

Only record endpoint attempts whose response status is one of: **200, 400, 401, 403**. These indicate the route exists and is meaningfully handled (success, bad input, auth required, or forbidden) as opposed to routes that don't exist (404) or are otherwise irrelevant.

For each recorded entry capture at minimum:
- `method`
- `url` (full path with the version and any resolved identifiers)
- `status`
- `contentType` / short note on response shape (array vs object, key fields) — useful context for later steps
- `parentEndpoint` — the endpoint it was derived from, so the tree structure is traceable

## Output location and format

Write results to:

```
bug-hunter/
└── {main-domain}/
    └── {subdomain-name}/
        └── AnalyzingJavaScriptFiles/
              └── FindApiEndpoint.json
```

- `{main-domain}` — the target's registrable domain (e.g. `example.com`)
- `{subdomain-name}` — the specific host being tested (e.g. `api.example.com`, or `www` if it's the apex/main host)

`FindApiEndpoint.json` structure:

```json
{
  "target": "api.example.com",
  "generatedAt": "<ISO timestamp>",
  "endpoints": [
    {
      "method": "GET",
      "url": "/api/v1/teams/team_11111111111/members/user_11111111",
      "status": 200,
      "responseShape": "object",
      "uniqueFieldsObserved": ["uid", "username", "email"],
      "parentEndpoint": "/api/v1/teams/team_11111111111/members"
    }
  ]
}
```

If `FindApiEndpoint.json` already exists for this target, merge new findings into it (dedupe on method+url) rather than overwriting.

## Notes and guardrails

- Always confirm the target is in-scope for the authorized engagement before starting.
- Rate-limit requests to avoid tripping WAF/anti-abuse protections or degrading the target's service — this is recon, not a stress test.
- Never attempt to exploit a discovered endpoint as part of this skill; that belongs to a dedicated testing skill (e.g. `hunt-idor`) run afterward, using this skill's output as its endpoint map.
- If an endpoint requires parameters this skill can't infer (e.g. a required body schema for POST/PUT/PATCH), record the attempt and status code, but don't guess at sensitive field values (e.g. payment data) — leave a note instead.

