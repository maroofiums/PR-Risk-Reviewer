#!/usr/bin/env python3
"""
diff_stats.py - deterministic signals from a unified diff.

Usage:
    python diff_stats.py <diff-file>            # JSON to stdout
    python diff_stats.py <diff-file> --format text
    cat change.diff | python diff_stats.py -    # read from stdin

This script only counts and pattern-matches. It does NOT judge risk.
The reviewer (Claude) reads the flagged files and makes the actual call.
"""

import argparse
import json
import re
import sys
from collections import defaultdict

# ---------------------------------------------------------------- path rules
PATH_RULES = {
    "migration": [
        r"(^|/)(migrations?|alembic|db/migrate|flyway|liquibase)(/|$)",
        r"\.sql$",
    ],
    "lockfile": [
        r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Pipfile\.lock|uv\.lock|Cargo\.lock|go\.sum|Gemfile\.lock|composer\.lock)$",
    ],
    "dependency_manifest": [
        r"(^|/)(package\.json|requirements[^/]*\.txt|pyproject\.toml|setup\.py|setup\.cfg|Pipfile|go\.mod|Cargo\.toml|Gemfile|pom\.xml|build\.gradle(\.kts)?|composer\.json)$",
    ],
    "auth_security": [
        r"(?i)(^|/)[^/]*(auth|login|logout|session|permission|rbac|acl|oauth|jwt|token|password|credential|security|crypto)[^/]*",
    ],
    "payments_billing": [
        r"(?i)(payment|billing|invoice|checkout|stripe|paypal|ledger|refund|subscription)",
    ],
    "infra_ci": [
        r"(?i)(^|/)(Dockerfile[^/]*|docker-compose[^/]*\.ya?ml|Jenkinsfile|Makefile)$",
        r"(^|/)\.github/workflows/",
        r"(^|/)\.gitlab-ci\.ya?ml$",
        r"\.tf$",
        r"(?i)(^|/)(k8s|kubernetes|helm|terraform|ansible|nginx)(/|$)",
    ],
    "config": [
        r"(^|/)\.env[^/]*$",
        r"(?i)(^|/)(settings|config|configuration)[^/]*\.(py|ya?ml|json|toml|ini|js|ts)$",
        r"\.(ini|cfg|toml)$",
    ],
    "api_contract": [
        r"(?i)(openapi|swagger|schema|serializers?|routes?|urls?|endpoints?|views|controllers?)[^/]*\.(py|ts|js|json|ya?ml|go|java|rb)$",
        r"\.(proto|graphql|gql)$",
        r"(^|/)api/",
    ],
    "test": [
        r"(^|/)tests?(/|$)",
        r"(^|/)__tests__(/|$)",
        r"(^|/)test_[^/]*$",
        r"_test\.[a-z]+$",
        r"\.(spec|test)\.[a-z]+$",
    ],
    "docs": [r"\.(md|rst|txt)$", r"(^|/)docs?(/|$)"],
}

# Categories that count as "production code" for the test-to-source ratio.
NON_SOURCE = {"test", "docs", "lockfile"}

# ----------------------------------------------------- added-line patterns
CONTENT_RULES = [
    ("destructive_sql", "high", r"(?i)\b(drop\s+(table|column|database|schema)|truncate\s+table|delete\s+from\s+\w+\s*(;|$)|alter\s+table\s+\w+\s+drop)"),
    ("schema_change", "medium", r"(?i)\b(alter\s+table|add\s+column|rename\s+(column|table)|create\s+index|RemoveField|RenameField|AlterField|DeleteModel|drop_column|drop_table)"),
    ("dynamic_exec", "high", r"\b(eval|exec)\s*\("),
    ("shell_injection_risk", "high", r"(shell\s*=\s*True|os\.system\s*\(|child_process\.exec\s*\()"),
    ("unsafe_deserialization", "high", r"(pickle\.loads?|yaml\.load\s*\((?!.*Loader\s*=\s*(yaml\.)?SafeLoader)|marshal\.loads)"),
    ("tls_verification_disabled", "high", r"(verify\s*=\s*False|rejectUnauthorized\s*:\s*false|InsecureSkipVerify\s*:\s*true|CURLOPT_SSL_VERIFYPEER\s*,\s*(0|false))"),
    ("possible_hardcoded_secret", "high", r"(?i)(api[_-]?key|secret|passwd|password|token|private[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-/+=]{12,}['\"]"),
    ("debug_enabled", "medium", r"(?i)\b(DEBUG\s*=\s*True|debug\s*:\s*true|ALLOWED_HOSTS\s*=\s*\[\s*['\"]\*['\"]\s*\])"),
    ("cors_wildcard", "medium", r"(?i)(allow_origins\s*=\s*\[\s*['\"]\*['\"]|CORS_ALLOW_ALL_ORIGINS\s*=\s*True|Access-Control-Allow-Origin['\"]?\s*[:,]\s*['\"]\*)"),
    ("auth_bypass_marker", "high", r"(?i)(permission_classes\s*=\s*\[\s*AllowAny|@csrf_exempt|skip_auth|no[_-]?auth|authentication_classes\s*=\s*\[\s*\])"),
    ("broad_exception_swallow", "medium", r"(except\s*:\s*$|except\s+Exception\s*:\s*(pass)?\s*$|catch\s*\(\s*\w*\s*\)\s*\{\s*\})"),
    ("test_disabled", "medium", r"(?i)(@pytest\.mark\.skip|@unittest\.skip|\.skip\(|xit\(|xdescribe\(|it\.skip|@Ignore)"),
    ("todo_marker", "low", r"(?i)\b(TODO|FIXME|HACK|XXX)\b"),
    ("debug_print", "low", r"(\bprint\s*\(|console\.log\s*\(|\bdebugger\b|breakpoint\s*\()"),
]

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def categorize(path):
    cats = []
    for cat, patterns in PATH_RULES.items():
        if any(re.search(p, path) for p in patterns):
            cats.append(cat)
    return cats


def parse_diff(text):
    files = []
    current = None
    in_hunk = False
    new_line_no = 0

    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*?) b/(.*)$", raw)
            old, new = (m.group(1), m.group(2)) if m else ("?", "?")
            current = {
                "path": new, "old_path": old, "status": "modified",
                "additions": 0, "deletions": 0, "binary": False,
                "added_lines": [],  # (line_no, text)
            }
            files.append(current)
            in_hunk = False
            continue
        if current is None:
            # plain "---/+++" diffs without a git header
            if raw.startswith("+++ "):
                path = re.sub(r"^[ab]/", "", raw[4:].split("\t")[0].strip())
                current = {
                    "path": path, "old_path": path, "status": "modified",
                    "additions": 0, "deletions": 0, "binary": False,
                    "added_lines": [],
                }
                files.append(current)
            continue
        if raw.startswith("new file mode"):
            current["status"] = "added"
        elif raw.startswith("deleted file mode"):
            current["status"] = "deleted"
        elif raw.startswith("rename from "):
            current["status"] = "renamed"
            current["old_path"] = raw[len("rename from "):]
        elif raw.startswith("rename to "):
            current["path"] = raw[len("rename to "):]
        elif raw.startswith("Binary files") or raw.startswith("GIT binary patch"):
            current["binary"] = True
        elif raw.startswith("+++ "):
            p = raw[4:].split("\t")[0].strip()
            if p != "/dev/null":
                current["path"] = re.sub(r"^b/", "", p)
        elif raw.startswith("--- "):
            if not in_hunk:
                continue
        if raw.startswith("@@"):
            in_hunk = True
            m = re.search(r"\+(\d+)", raw)
            new_line_no = int(m.group(1)) if m else 0
            continue
        if not in_hunk:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            current["additions"] += 1
            current["added_lines"].append((new_line_no, raw[1:]))
            new_line_no += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            current["deletions"] += 1
        elif raw.startswith(" "):
            new_line_no += 1
    return files


def size_tier(changed, nfiles):
    if changed < 50 and nfiles <= 3:
        return "small"
    if changed < 200 and nfiles <= 10:
        return "medium"
    if changed < 500 and nfiles <= 25:
        return "large"
    return "very_large"


def analyze(text):
    files = parse_diff(text)
    cat_files = defaultdict(list)
    findings = []

    for f in files:
        f["categories"] = categorize(f["path"])
        for c in f["categories"]:
            cat_files[c].append(f["path"])
        if f["status"] == "deleted":
            cat_files["deleted_file"].append(f["path"])
        if f["status"] == "renamed":
            cat_files["renamed_file"].append(f["path"])
        if f["binary"]:
            cat_files["binary_file"].append(f["path"])

        # content patterns apply to non-doc added lines only
        if "docs" in f["categories"] and "config" not in f["categories"]:
            continue
        for line_no, text_line in f["added_lines"]:
            for name, sev, pat in CONTENT_RULES:
                if re.search(pat, text_line):
                    findings.append({
                        "rule": name, "severity": sev, "file": f["path"],
                        "line": line_no, "snippet": text_line.strip()[:160],
                    })

    findings.sort(key=lambda x: (SEVERITY_ORDER[x["severity"]], x["file"], x["line"]))

    adds = sum(f["additions"] for f in files)
    dels = sum(f["deletions"] for f in files)
    src_files = [f for f in files if not (set(f["categories"]) & NON_SOURCE)]
    test_files = [f for f in files if "test" in f["categories"]]
    src_changed = sum(f["additions"] + f["deletions"] for f in src_files)
    test_changed = sum(f["additions"] + f["deletions"] for f in test_files)

    summary = {
        "files_changed": len(files),
        "additions": adds,
        "deletions": dels,
        "lines_changed": adds + dels,
        "size_tier": size_tier(adds + dels, len(files)),
        "source_files_changed": len(src_files),
        "test_files_changed": len(test_files),
        "source_lines_changed": src_changed,
        "test_lines_changed": test_changed,
        "tests_touched": bool(test_files),
        "source_without_tests": bool(src_files) and not test_files,
        "top_level_dirs_touched": sorted({f["path"].split("/")[0] for f in files if "/" in f["path"]}),
    }

    return {
        "summary": summary,
        "flagged_paths": {k: sorted(set(v)) for k, v in cat_files.items() if k not in ("docs",)},
        "content_findings": findings[:60],
        "content_findings_truncated": len(findings) > 60,
        "files": [
            {k: v for k, v in f.items() if k != "added_lines"} for f in files
        ],
    }


def to_text(result):
    s = result["summary"]
    out = [
        "DIFF SUMMARY",
        f"  files: {s['files_changed']}  +{s['additions']} -{s['deletions']}  tier: {s['size_tier']}",
        f"  source files: {s['source_files_changed']}  test files: {s['test_files_changed']}"
        + ("   (SOURCE CHANGED, NO TESTS TOUCHED)" if s["source_without_tests"] else ""),
        "",
        "FLAGGED PATHS",
    ]
    if not result["flagged_paths"]:
        out.append("  none")
    for cat, paths in result["flagged_paths"].items():
        out.append(f"  [{cat}]")
        out.extend(f"    {p}" for p in paths)
    out += ["", "CONTENT FINDINGS (added lines only)"]
    if not result["content_findings"]:
        out.append("  none")
    for f in result["content_findings"]:
        out.append(f"  [{f['severity'].upper()}] {f['rule']}  {f['file']}:{f['line']}  {f['snippet']}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("diff", help="path to a unified diff, or - for stdin")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()

    text = sys.stdin.read() if args.diff == "-" else open(args.diff, encoding="utf-8", errors="replace").read()
    if not text.strip():
        print("error: empty diff", file=sys.stderr)
        sys.exit(2)

    result = analyze(text)
    if not result["files"]:
        print("error: no files found; input does not look like a unified diff", file=sys.stderr)
        sys.exit(2)
    print(to_text(result) if args.format == "text" else json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
