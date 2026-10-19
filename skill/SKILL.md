---
name: pr-risk-reviewer
description: Assess how risky a pull request or code diff is to merge and produce a structured risk report with a verdict, ranked risks with file and line evidence, a pre-merge test plan, and a rollback plan. Use this skill whenever the user shares a PR, pull request URL, git diff, patch, or code change and asks whether it is safe to merge, what could break, what the blast radius is, what to test, or for a PR review, release risk check, change-risk assessment, or "second pair of eyes" before merging, even if they never use the word "risk". Also use it when the user pastes a diff and just says "review this". Covers database migrations, API contract changes, auth and security changes, dependency bumps, and Python backends (Django, FastAPI).
---

# PR Risk Reviewer

Answer one question for the person merging: **how risky is this change, and where should a human look hardest?** This is a risk assessment, not a line-by-line style review. Do not comment on formatting, naming, or taste unless it hides a defect.

## Workflow

### 1. Obtain the diff

Accept any of these:
- A diff or patch pasted into the chat, or an uploaded `.diff` / `.patch` file (look in `/mnt/user-data/uploads`). Save pasted text to a file first.
- A GitHub PR URL or `OWNER/REPO#123`: run `python scripts/fetch_pr_diff.py <ref> > /tmp/pr.diff`. This also prints the PR title and description to stderr; use the author's stated intent when judging scope. Works for public repositories; private ones need `GITHUB_TOKEN`. If the network is blocked, tell the user and ask them to paste the diff.
- Only a description or a few snippets: proceed, but state clearly in Limitations that the review is partial, and lower your confidence accordingly.

If the diff is enormous (over roughly 2,000 changed lines), analyze with the script first, then read only the flagged files and a sample of the rest, and say so in Limitations.

### 2. Gather objective signals

```bash
python scripts/diff_stats.py /tmp/pr.diff --format text
```

This reports size, test-to-source balance, flagged paths (migrations, lockfiles, auth, payments, infra, config, API contract) and risky patterns in added lines. Treat its output as leads to investigate, never as conclusions. It produces false positives (a `print(` in a script) and misses semantic problems (a flipped condition). Use `--format json` if you need the per-file breakdown.

### 3. Read the diff where it matters

Read every file the script flagged, plus any file where added logic is non-trivial. For each, understand what behavior changed, not just which lines changed. When the diff shows only a fragment, note what surrounding code you would need to see.

### 4. Score the dimensions

Read `references/risk-rubric.md` and score all ten dimensions. Load conditionally:
- `references/security-checks.md`: when auth, user input, secrets, serialization, or network calls are involved, or the script reported security findings.
- `references/python-stack.md`: when the diff contains Python backend code (Django, DRF, FastAPI, Alembic, SQLAlchemy, Celery, or ML-serving code).

### 5. Decide the verdict

Apply the overall verdict rules in the rubric. Critical is reserved for credible irreversible data loss, security exploitable by a lower-privileged user, or core-flow outage without rollback.

### 6. Write the report

Follow `assets/report-template.md`. Keep this order: verdict first, then summary, top risks, dimension table, test plan, rollback, questions, limitations.

## Rules that keep the review trustworthy

- **Evidence is mandatory.** Every Medium or higher finding cites `path:line` from the diff. No evidence, no finding.
- **Separate observed from inferred.** If a risk depends on code you were not shown, label it "unverified" and put the question in "Questions for the author".
- **Calibrate, do not inflate.** A small, well-tested, reversible change should get a Low verdict and a short report. Do not pad the template with invented concerns. An assistant that flags everything teaches people to ignore it.
- **Do not under-flag silent changes.** Changed thresholds, defaults, ordering, filters, and removed validation raise no errors, so they deserve extra attention.
- **Tests are evidence only if they assert the right thing.** Read what changed tests check; deleted or skipped tests are a finding.
- **Be specific in the test plan.** Name the input, the user role, the table size, the expected result. Generic advice ("test thoroughly") is not acceptable.
- **Security findings:** describe the weakness and the fix; do not write exploit payloads. If a real-looking secret appears in the diff, recommend rotation, since it persists in git history.
- **Be honest about scope.** You saw a diff, not the running system. Say what that means for confidence.

## Output length

- Low-risk PR: about 150-250 words, with the dimension table collapsed to the dimensions that were touched.
- Medium: full template, concise.
- High or Critical: full template, with each top risk fully developed.

Deliver the report in the chat by default. Produce a file only if the user asks for one.
