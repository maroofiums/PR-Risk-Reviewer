# PR Risk Report: {PR title or short description}

**Verdict: {Low | Medium | High | Critical}** | **Recommendation: {Merge | Merge with conditions | Hold | Do not merge}**

Scope reviewed: {what was provided: full diff / partial diff / description only} | Size: {N files, +A / -D lines, tier}

## Summary
{Two to four sentences. What the PR does, the single biggest concern, and why the verdict follows from it.}

## Top risks
1. **{Risk title}** ({dimension}, {Medium|High|Critical})
   - Evidence: `{path}:{line}` - {what the code does}
   - Failure scenario: {who or what breaks, and how}
   - Fix or mitigation: {specific action}
2. ...

(List at most five. If the PR is Low risk, write "No significant risks found." and omit invented items.)

## Dimension scores
| Dimension | Level | Evidence or note |
|---|---|---|
| Size and scope | | |
| Critical paths | | |
| Data and schema | | |
| API contract | | |
| Dependencies | | |
| Concurrency and state | | |
| Security | | |
| Config and infrastructure | | |
| Test coverage | | |
| Reversibility | | |

Use "Not touched" for dimensions the PR does not affect.

## Pre-merge test plan
- {Specific, runnable check: input, expected outcome}
- ...

## Rollback and monitoring
- Rollback: {how to revert, and whether revert fully restores state}
- Watch after deploy: {specific metrics, logs, or errors to monitor, and for how long}

## Questions for the author
- {Question whose answer would change the verdict}

## Limitations
{What was not visible: surrounding code, runtime configuration, test results, production data volume. Mark any risk that depends on these as unverified.}
