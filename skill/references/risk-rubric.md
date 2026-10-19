# Risk Rubric

Contents: scoring principle, the ten dimensions, overall verdict rules, calibration guardrails.

## Scoring principle

Risk = likelihood of a defect reaching production x impact if it does x difficulty of recovering.
Score each dimension on that basis, not on how "scary" the code looks. A 600-line mechanical rename is lower risk than a 6-line change to a permission check.

Levels:
- **None**: dimension not touched. Write "Not touched" and move on.
- **Low**: touched, but failure is unlikely, contained, or trivially reversible.
- **Medium**: plausible failure, or moderate blast radius, recoverable with a normal deploy.
- **High**: plausible failure with large blast radius, data impact, security impact, or hard recovery.

Every Medium and High needs evidence: `path:line` plus one sentence on the failure scenario.

## Dimensions

### 1. Size and scope
- Low: under about 200 changed lines, one concern.
- Medium: 200-500 lines, or two loosely related concerns.
- High: over 500 lines, or several unrelated concerns bundled (refactor + feature + dependency bump). Large unfocused PRs hide defects because reviewers tire.
- Discount mechanical changes (renames, formatting, generated code) when you can verify they are mechanical.

### 2. Critical paths
Authentication, authorization, payments, billing, data export/deletion, core domain logic, anything on the main user journey.
- Low: touches a critical module only for comments, logging, or typing.
- Medium: modifies behavior in a critical module with tests covering the change.
- High: modifies access checks, money calculations, or core logic without matching tests.

### 3. Data and schema
- Low: additive, nullable columns or new tables nothing reads yet.
- Medium: new NOT NULL column with default, new index on a mid-size table, data backfill in a migration.
- High: dropping or renaming columns/tables, type changes, non-reversible migrations, long locks on large tables, destructive data operations, backfills with no batching.
- Check ordering: code that reads a column must not deploy before the migration that creates it, and code must tolerate the old schema while the migration runs.

### 4. API contract
- Low: purely additive (new optional field, new endpoint).
- Medium: behavior change behind the same contract, new required parameter with a default.
- High: removed or renamed fields, changed types, changed status codes or error shapes, changed auth requirements, anything external consumers or mobile clients depend on.

### 5. Dependencies
- Low: patch bump of a well-known library, lockfile-only drift.
- Medium: minor bump, new well-maintained dependency.
- High: major version bump, new dependency with a small maintainer base, change to a security-sensitive library (crypto, auth, serialization), pinned version removed.

### 6. Concurrency and state
- Low: no shared state touched.
- Medium: new caching, new background job, new transaction boundary.
- High: changed locking, check-then-act sequences without atomicity, removed idempotency, retry logic on non-idempotent operations, shared mutable globals.

### 7. Security
See `security-checks.md`. High if any exploitable weakness is introduced, or a protection is weakened.

### 8. Config and infrastructure
- Low: documentation-adjacent config, test-only config.
- Medium: new env var with safe default, CI change.
- High: changed production defaults, new required env var with no default (deploy fails), Dockerfile base image change, changed resource limits, infra-as-code changes, secrets handling.

### 9. Test coverage
This dimension scores the *gap*, not the code.
- Low: new or changed behavior has tests that would fail if it broke.
- Medium: tests exist but only cover the happy path, or coverage is unclear.
- High: behavior changes in a Medium/High area with no test changes, or tests were deleted, skipped, or weakened to make the PR pass.
- Never accept "tests touched" as proof of coverage. Read what they assert.

### 10. Reversibility
- Low: revert the commit and redeploy restores the previous state.
- Medium: revert works but requires a coordinated step (cache flush, config change).
- High: revert does not restore state (data migrated or deleted, messages sent, external systems updated), or rollback requires a second migration.

## Overall verdict

Start from the highest dimension score, then apply these rules:

- **Critical**: reserved for a credible path to irreversible data loss, a security vulnerability exploitable by an unauthenticated or lower-privileged user, or an outage of a core flow with no rollback. Use rarely.
- **High**: any dimension is High with evidence, or three or more dimensions are Medium and one of them is a critical path, data, or security.
- **Medium**: no High dimensions, but at least two Medium, or one Medium in a critical path/data/security.
- **Low**: everything Low or None.

Merge recommendation mapping:
- Low -> merge
- Medium -> merge with conditions (list the conditions)
- High -> hold until listed risks are addressed or explicitly accepted by the owner
- Critical -> do not merge

## Calibration guardrails

- A reviewer that flags everything is ignored. If a PR is genuinely low risk, say so plainly and keep the report short. Do not invent concerns to fill the template.
- Only cite evidence you actually saw in the diff. If a risk depends on code outside the diff, label it as "unverified: depends on <thing not shown>" and ask for it.
- Separate what you observed (in the diff) from what you infer (about the wider system).
- Prefer specific test cases over generic advice. "Test with a user who has role X and resource owned by Y" beats "test permissions".
