---
name: hunt-idor
description: Hunting skill for IDOR vulnerabilities. Strategy 1 is a lightweight single-endpoint, single-session tampering check; Strategy 2 is the full multi-account hunting methodology built from 26 public bug bounty reports. Use when hunting IDOR on any target.
sources: github, hackerone_public
report_count: 26
---

## Purpose
Test API endpoints for IDOR (Insecure Direct Object Reference)
vulnerabilities — access to another user's data or the ability to
change another user's state without proper ownership/authorization
checks.

⚠️ Use this skill only against systems you are authorized to test
(your own test environment, or a scope you're authorized to test
under a bug bounty program).

---

## Required Inputs
- **Endpoint** (the single endpoint to test)
- **Attacker session** (token/cookie for the attacker's account)
- **Victim session** (token/cookie for the victim's account — used
  only to establish the baseline/expected values that belong to the
  victim, e.g. their real `user`/`TeamId`, so tampered values sent
  under the attacker's session can be checked against what the
  victim's account actually owns)

No other inputs are required for Strategy 1. Strategy 2 additionally
assumes two full accounts (attacker + victim) can be used to browse
the target and capture traffic, as described in that section.

---

## Strategy 1: Response-Reflected Parameter Tampering

### Step 1: Baseline Request
Send the request to the endpoint using the attacker's session,
unmodified. Record:
- `status_code`
- `response_body` (full, as JSON where possible)
- `response_headers` (especially Content-Length, Content-Type)
- `response_time`

### Step 2: Extract Candidate Parameters
Scan the response body for any field that could plausibly be an
identifier or a privilege flag, such as:
- Fields ending in: `id`, `Id`, `_id`, `ID`
- Fields containing: `user`, `account`, `owner`, `team`, `org`, `tenant`
- Sensitive boolean flags: `admin`, `public`, `isOwner`, `verified`, `role`
- Any field that also appears as a query parameter, path parameter,
  or in the request body

Example:
```
GET /api/v1/integration
Response: { "user":"1002", "public":true, "admin":true, "TeamId":"7888" }
```
→ Candidate list: `user`, `public`, `admin`, `TeamId`

### Step 3: Systematic Parameter Fuzzing
For each candidate parameter, send several modified requests,
**changing one parameter at a time** (all others stay at their
original value, to isolate the effect of each parameter).

**For numeric/string ID fields:**
- Adjacent value: `id-1`, `id+1`
- A random value within a plausible range (e.g. `1000`, `9999`)
- `0`, `-1`, `null`, empty string
- The victim's real ID (known from the victim session baseline)

**For sensitive boolean fields (admin, public...):**
- Flip the value (`true` → `false` and vice versa)

**For placement:** try the same parameter in every plausible location:
- Query string: `?user=1003`
- JSON body: `{"user": "1003"}`
- Path parameter: `/api/v1/integration/1003`
- A custom header, if a matching pattern exists (`X-User-Id`)

### Step 4: Diff Analysis
Compare each modified response against the baseline on multiple
levels (not just response length):

1. **Status code** changed? (200→403 suggests it's likely protected;
   200→200 with different data suggests possible IDOR)
2. Did the **sensitive field values themselves** change in a way
   consistent with the value sent? (e.g. you sent `user=1003` and
   got back `"user":"1003"` along with data that matches the
   victim's baseline captured earlier)
3. Did any **new fields appear** or **existing fields disappear**
   compared to the baseline?
4. Did **error messages** leak information? (e.g. "User 1003 not
   found" indicates the backend actually validates the ID's
   existence = real attack surface)
5. Exclude cosmetic differences that don't matter: timestamps,
   request IDs, nonces, ETags

### Step 5: Classification
Classify each finding:
- 🔴 **Confirmed IDOR**: the returned data genuinely belongs to the
  victim, with no authorization check
- 🟠 **Needs manual verification**: the response changed but it's
  unclear whether it's a real leak (e.g. only a number changed with
  no clear context)
- 🟢 **Protected**: the same value was returned despite the change,
  or an appropriate 401/403/404 was returned

### Step 6: Report
For the endpoint, produce a table:

| Parameter | Original Value | Tested Value | Location (query/body/path) | Status Before/After | Result | Classification |
|---|---|---|---|---|---|---|

Include:
- The full curl / raw request for each 🔴 or 🟠 finding (for
  reproducibility)
- A short remediation recommendation (e.g. "Verify that `TeamId`
  belongs to the session owner before returning the data")

### Execution Constraints (Strategy 1)
- Respect any rate limit specified by the user
- Do not send destructive payloads (do not try DELETE/PUT unless
  the user explicitly authorizes it, and only against test data)
- Stop and ask the user if an endpoint appears to irreversibly
  modify real (production) data

---

## Strategy 2: Full Cross-Account Hunting Methodology

This is the broader, application-wide methodology (not limited to
one endpoint) for deeper engagements, distilled from 26 public bug
bounty reports.

### Crown Jewel Targets

**Why IDOR pays big:**
- Direct access to other users' data without authentication bypass — clear, demonstrable impact
- Chains easily with privilege escalation, financial fraud, and account takeover
- Affects virtually every application with user-owned resources

**Highest-value asset types (by payout potential):**

| Asset Type | Why It Pays |
|---|---|
| Financial documents / billing APIs | PII + financial data exposure (Shopify, Uber, PayPal) |
| Private repositories / source code | IP theft, critical data loss (GitHub) |
| User messages / DMs | Privacy violation at scale (Reddit) |
| Account management endpoints | User addition, deletion, privilege escalation (PayPal, Mozilla) |
| Business/org administration | Cross-tenant escalation, employee PII (Uber) |
| Content moderation/admin actions | Operational sabotage (Reddit mod logs) |

**Programs that pay most for IDOR:**
- Platforms with multi-tenancy (SaaS, B2B tools)
- Fintech and payment processors
- Social platforms with private content
- Developer tools with org/repo isolation

### Attack Surface Signals

**URL patterns that scream IDOR:**
```
/api/v1/users/{id}/
/api/v*/orders/{order_id}
/invoices/download?id=
/reports/{uuid}/
/messages/{thread_id}
/admin/orgs/{org_id}/members
/migration/{migration_id}/files
/graphql (query params with IDs)
/api/business/{business_id}/
/vouchers/{voucher_id}/policy
```

**Response header signals:**
- `Content-Type: application/json` on endpoints accepting raw IDs
- No `X-Frame-Options` or CORS misconfigs paired with ID params
- `Authorization: Bearer` tokens that are user-scoped but hit org-level resources

**JavaScript source patterns:**
```javascript
fetch(`/api/v1/users/${userId}/profile`)
axios.get('/invoices/' + invoiceId)
graphql query { billingDocument(id: $docId) }
state.currentUser.organizationId
```

**Tech stack signals:**
- GraphQL endpoints (query-based IDORs are often missed)
- REST APIs with sequential integer IDs (most vulnerable)
- UUIDs that are predictable or leaked in other responses
- Multi-tenant SaaS apps with `org_id`, `account_id`, `business_id` params
- Mobile apps (Burp the APK — mobile APIs often skip authorization checks)

### Step-by-Step Hunting Methodology

1. **Map all object references in the application**
   - Browse every feature authenticated as the victim account
   - Capture all requests in Burp Suite
   - Filter for requests containing: `id=`, `_id=`, `uuid=`, `/v1/{noun}/{id}`, query params with numeric/UUID values

2. **Enumerate ID types**
   - Sequential integers → enumerate ±1, ±100
   - UUIDs → check if they appear in other responses or JS files
   - Hashed IDs → check if leaked in public endpoints, metadata, or GraphQL introspection

3. **Use the two accounts (same privilege level)**
   - Victim: resource owner
   - Attacker: attacker account
   - Log all IDs belonging to the victim while authenticated as the victim

4. **Replay the victim's resource IDs as the attacker**
   - Use the attacker's session cookie/token
   - Send identical requests referencing the victim's object IDs
   - Test ALL HTTP verbs: GET, POST, PUT, PATCH, DELETE on each endpoint

5. **Test cross-tenant/cross-org scenarios**
   - If accounts exist in separate organizations/businesses
   - Test if the attacker's org session can reference the victim org's IDs
   - Pay special attention to admin/management endpoints

6. **Test GraphQL specifically**
   - Run introspection: `{ __schema { queryType { fields { name } } } }`
   - For every query/mutation taking an `id` argument, substitute the victim's ID
   - Test both queries (read) and mutations (write/delete)

7. **Test write/destructive operations, not just reads**
   - Can the attacker DELETE the victim's resources?
   - Can the attacker MODIFY the victim's content?
   - Can the attacker ADD themselves to the victim's account?

8. **Chain IDORs together**
   - Use one IDOR's leaked data (org IDs, user IDs) to fuel the next
   - IDOR → leaked ID → second IDOR → privilege escalation

9. **Test state-changing edge cases**
   - Expired tokens/invites that can still be accepted
   - Race conditions on resource IDs
   - Indirect references: `?sort=id` or `?filter[user_id]=`

10. **Document the exact differential**
    - Confirm the attacker has NO legitimate access to the victim's resource
    - Log the 200 OK vs expected 403/404

### Payload & Detection Patterns

**Basic IDOR test with curl (swap cookie/token):**
```bash
# Get the victim's resource ID while authenticated as the victim
curl -s -H "Cookie: session=VICTIM_SESSION" \
  https://target.com/api/v1/invoices/12345

# Replay with the attacker's session
curl -s -H "Cookie: session=ATTACKER_SESSION" \
  https://target.com/api/v1/invoices/12345

# Success = 200 OK with the victim's data
```

**GraphQL IDOR test:**
```bash
curl -s -X POST https://target.com/graphql \
  -H "Authorization: Bearer ATTACKER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ billingDocument(id: \"VICTIM_DOC_ID\") { id amount pdfUrl } }"}'
```

**Enumerate sequential IDs with ffuf:**
```bash
ffuf -u "https://target.com/api/v1/orders/FUZZ" \
  -w ids.txt \
  -H "Authorization: Bearer ATTACKER_TOKEN" \
  -mc 200 \
  -o idor_results.json
```

**Generate sequential ID wordlist:**
```python
known_id = 48291
with open("ids.txt", "w") as f:
    for i in range(known_id - 500, known_id + 500):
        f.write(str(i) + "\n")
```

**Burp Intruder payload for IDOR scanning:**
```
GET /api/messages/§12345§ HTTP/1.1
Host: target.com
Authorization: Bearer ATTACKER_TOKEN

# Mark §12345§ as injection point
# Use numeric sequential payload: 12000-13000
# Filter responses by length difference or status 200
```

**JavaScript scraping for leaked IDs:**
```bash
curl -s https://target.com/static/app.js | grep -Eo '"id":"[a-f0-9-]{36}"' | sort -u

curl -s -H "Cookie: session=VICTIM_SESSION" \
  https://target.com/api/v1/dashboard | python3 -m json.tool | grep -i "_id"
```

**Grep patterns for source code review:**
```bash
grep -r "findById\|findOne\|getById" --include="*.js" .
grep -r "params\[:id\]\|params\['id'\]" --include="*.rb" .
grep -r "request\.args\.get\('id'\)" --include="*.py" .

grep -r "Model\.find(params" --include="*.js" .
# vs secure pattern: Model.find({ id: params.id, userId: req.user.id })
```

**IDOR via HTTP method tampering:**
```bash
for method in GET POST PUT PATCH DELETE OPTIONS HEAD; do
  echo "=== $method ==="
  curl -s -X $method \
    -H "Authorization: Bearer ATTACKER_TOKEN" \
    https://target.com/api/v1/users/VICTIM_ID/profile
done
```

### Common Root Causes

1. **Missing ownership check in ORM queries**
   ```javascript
   // VULNERABLE: fetches any record
   const invoice = await Invoice.findById(req.params.id);

   // SECURE: scopes to authenticated user
   const invoice = await Invoice.findOne({ _id: req.params.id, userId: req.user.id });
   ```

2. **Authorization at the route level, not object level**
   - Developer checks "is user logged in?" but not "does this user own this object?"
   - Middleware confirms authentication; individual handlers skip ownership validation

3. **Trusting client-supplied IDs in request bodies**
   - Mobile apps or SPAs send `org_id` in POST body; server uses it directly without verifying caller belongs to that org

4. **GraphQL resolvers without field-level authorization**
   - Query resolvers fetch by ID from database without checking if the requesting user has permission
   - Especially common when resolvers are auto-generated from schema

5. **Inconsistent authorization across HTTP verbs**
   - GET endpoint is protected; POST/DELETE on same resource path is not
   - Common in APIs built incrementally by different developers

6. **Indirect references exposed via related objects**
   - Object A (accessible) contains a reference to Object B (should be private)
   - Developer only protects direct access to B, not indirect references through A

7. **Race conditions and state-based IDORs**
   - Authorization checked at creation time, not at access time
   - Invites/tokens remain valid after the granting permission is revoked

8. **Multi-tenant isolation failures**
   - Developers implement per-user access control but forget cross-org boundaries
   - `user_id` check present; `org_id` / `tenant_id` check absent

### Bypass Techniques

**Defense: UUIDs instead of sequential integers**
- Bypass: UUIDs often leak in other API responses, notification emails, webhooks, GraphQL queries, or JS source
- Technique: Harvest UUIDs from accessible endpoints, then replay against restricted ones

**Defense: Indirect/hashed object references**
- Bypass: Decode the hash (often base64 or simple obfuscation), or find the original ID in another response
- Technique: `echo "dXNlcl8xMjM0NQ==" | base64 -d` → `user_12345`

**Defense: Short-lived tokens per resource**
- Bypass: Tokens sometimes reusable across users if server only validates token format, not binding
- Technique: Use your own token to access another user's resource ID

**Defense: Rate limiting on enumeration**
- Bypass: Slow enumeration (1 req/5s), use distributed IPs, or exploit non-enumeration IDORs (you already know the target's ID from another leak)

**Defense: Checking `user_id` in WHERE clause**
- Bypass: Check if the same endpoint exists at a different API version (`/v1/` vs `/v2/`) — authorization logic is often version-specific
- Technique: Check JS bundles for older API version calls

**Defense: CORS restrictions**
- Bypass: IDOR doesn't require cross-origin exploitation — you're testing API endpoints directly with your own session

**Defense: "Opaque" references via server-side sessions**
- Bypass: Look for any endpoint that *returns* the internal ID, then use it elsewhere; APIs often expose IDs in `Location` headers, error messages, or metadata

**Defense: Parameter filtering/WAF on common patterns**
- Bypass: Try nested JSON `{"data": {"id": "VICTIM_ID"}}`, HTTP parameter pollution `?id=own_id&id=victim_id`, or parameter name variations `user_id`, `userId`, `uid`, `account`

### Gate 0 Validation

Before writing the report, answer all three:

1. **What can the attacker DO right now?**
   Be specific: "Attacker with a valid account can send a GET request to `/api/v1/invoices/{victim_invoice_id}` and receive the victim's full billing document including name, address, and payment amount — without any relationship to that account."

2. **What does the victim LOSE?**
   Map to CIA triad: confidentiality (data exposed), integrity (data modified), or availability (data deleted). "Victim loses confidentiality of private financial records" or "Victim's content is deleted by a third party" — vague answers fail.

3. **Can it be reproduced in 10 minutes from scratch?**
   - Two fresh accounts created ✓
   - Exact HTTP request documented with victim's ID ✓
   - 200 OK response showing victim's data (or confirmed state change) ✓
   - No reliance on pre-existing state or timing ✓

   If you can't demo it reproducibly, do not file the report.

### Real Impact Examples

**Scenario 1: Financial Data Exposure + Cross-Account Billing Fraud (Uber-style)**
An attacker discovers two related IDORs: one allows reading any organization's voucher policy configuration (exposing org IDs, employee email lists, and payment methods), and a second allows modifying voucher policies using those leaked IDs. Chained together, this enables the attacker to redirect charges to an arbitrary business account, expose employee PII across organizations, and take over invitation links — all without any elevated privileges beyond a basic user account. Impact: financial fraud + mass PII exposure across the B2B platform.

**Scenario 2: Private Repository Read via IDOR on Migration Endpoint (GitHub-style)**
A migration feature allows users to upload files to a migration job. The `migration_id` parameter is not validated against the authenticated user's ownership. An attacker creates their own migration, observes the ID format, and substitutes another user's private migration ID — gaining read access to source code files from private repositories they have no access to. Impact: complete confidentiality bypass for private intellectual property.

**Scenario 3: Account Takeover Chain via Message IDOR (Reddit-style)**
An attacker accesses another user's private message threads by substituting their `thread_id` in a messaging API endpoint. The response includes message content, metadata, and — critically — session or verification tokens sent via internal messages. The attacker leverages the token found in the messages to perform account recovery steps, escalating a read-only IDOR into full account takeover. Impact: complete account compromise of targeted users at scale.

### Chains & Compositions (Senior Hunting)

Standalone IDOR gets paid at Low-Medium for cross-tenant *read*. The real money is in chaining IDOR to a *state-change* primitive that doesn't normally permit cross-tenant action — turning "I can see victim's data" into "I own victim's account". The six chains below are the highest-paying IDOR compositions on modern bug-bounty programs.

**Chain 1 — IDOR on `/api/users/{id}/email` + Missing Re-Auth → Password Reset → ATO**
- Confirm IDOR on the email-change endpoint — request `PUT /api/users/{victim_id}/email {"email":"attacker@evil"}` from attacker's session; server changes the victim's email without ownership check.
- Trigger the password-reset flow on the victim's account — server emails the reset link to the new (attacker) email.
- Open reset link, set new password, log in as victim.
- Real shape: classic ATO pattern across many SaaS bug-bounty disclosures 2018-2024. Cross-refs `hunt-ato` Path 2.

**Chain 2 — IDOR on File-Download + Filename-Controlled `Content-Disposition` → Reflected-XSS-Via-Download → Session Theft**
- IDOR on `/api/files/{id}/download` returns any user's file given the ID.
- The download endpoint reflects an unsanitized filename into `Content-Disposition` — a crafted filename injects markup/script.
- Victim downloads the file → injected content executes in victim's session context → cookie/token exfil.
- Real shape: multiple disclosed cases involving SharePoint/GitLab/SaaS export endpoints. Pairs with `hunt-xss` Chain 1.

**Chain 3 — IDOR via GraphQL `node(id:)` GID + Relay Relation Traversal → Cross-Tenant Mass Data Extraction**
- Target uses GraphQL with Relay-style global IDs.
- The top-level `node()` resolver auths the requester, but nested relations don't re-check ownership.
- Iterating IDs exfiltrates emails, order totals, payment methods across the entire customer base.
- Real shape: Shopify Billing IDOR H1 #2207248 ($5,000); HackerOne PolicyPageAssetGroup IDOR H1 #1618347 ($25,000).

**Chain 4 — IDOR on `/api/teams/{id}/members` + Mass-Assignment in Body → Role Escalation on Victim Team**
- Horizontal IDOR adds the attacker as a normal member without ownership check.
- The body accepts unfiltered fields (`role`, `permissions`) — mass assignment leaks into the role field.
- Attacker is added to the victim team as OWNER, gaining full admin access.
- Real shape: Shopify `fileCopy` mutation H1 #981472 (2020); Stripe `UpdateAtlasApplicationPerson` H1 #1066203 (2020).

**Chain 5 — Soft-Delete IDOR + Post-Removal Token Validity → Persistent Cross-Tenant Access**
- The "remove member" endpoint flips an `active=false` flag but doesn't invalidate the session/PAT.
- A removed user's previously captured token keeps working after removal — IDOR is now *temporal*.
- Real shape: Shopify removed-staff persistence class (2022). Cross-refs `hunt-misc` Chain 1.

**Chain 6 — Double-IDOR (`/users/{id}/orders → /orders/{order_id}/refund`) → Financial Impact on Victim Merchant**
- First IDOR leaks the victim's order list and `order_id` values without ownership check.
- Second IDOR issues refunds without checking that the requester owns the merchant/order.
- Money moves from merchant to attacker-controlled customer.
- Real shape: multiple disclosed e-commerce platform IDOR chains 2019-2023.

**Operator-level pattern:** when you confirm a read-IDOR, immediately ask: *what state-change accepts the same ID and might also be IDOR'd?* The chain is usually one of: (1) password reset / email change → ATO; (2) refund / withdraw / transfer → financial; (3) role-change / membership-add → privilege escalation.

### Execution Constraints (Strategy 2)
- Same constraints as Strategy 1: respect rate limits, avoid destructive payloads against production data unless explicitly authorized, stop and ask before any irreversible action.
- Chain steps (email-change → password reset, refunds, role escalation) must only be executed against test/authorized accounts and confirmed reversible, or with explicit user sign-off — never carried out against real third-party accounts even within an authorized bug bounty scope without prior confirmation from the user.

---

## Related Skills & Chains
- **`hunt-auth-bypass`** — missing ORM scoping + missing route-level auth = unauthenticated cross-tenant data read via direct ID substitution.
- **`hunt-ato`** — profile-edit IDOR (`PATCH /api/users/{victim_uid}`) → set attacker email → trigger password reset → full ATO.
- **`hunt-graphql`** — GraphQL introspection → enumerate every mutation accepting `id:` → substitute victim IDs across `updateUser`, `deleteOrg`, `transferBilling`.
- **`security-arsenal`** — IDOR bypass tables: parameter pollution, nested-JSON wrappers, parameter-name variations.
- **`triage-validation`** — run the Pre-Severity Gate before claiming Critical on a 200-with-no-real-data IDOR.

---

## Note
Strategy 1 (Response-Reflected Parameter Tampering) is the fast,
single-endpoint check. Strategy 2 (Full Cross-Account Hunting
Methodology) is the deeper, application-wide pass. Additional
strategies can be appended as further sections later.
