#!/usr/bin/env python3
"""
fetch_pr_diff.py - download a GitHub pull request as a unified diff.

Usage:
    python fetch_pr_diff.py https://github.com/OWNER/REPO/pull/123 > pr.diff
    python fetch_pr_diff.py OWNER/REPO#123 > pr.diff

Also prints PR metadata (title, author, base branch, description) to stderr
so the reviewer can use the author's stated intent.

Uses api.github.com directly. Set GITHUB_TOKEN for private repositories or to
avoid the unauthenticated rate limit (60 requests per hour).
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request


def parse_ref(ref):
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", ref)
    if m:
        return m.group(1), m.group(2), m.group(3)
    m = re.match(r"([^/\s]+)/([^#\s]+)#(\d+)$", ref)
    if m:
        return m.group(1), m.group(2), m.group(3)
    sys.exit(f"error: cannot parse PR reference: {ref}")


def api(url, accept):
    headers = {"Accept": accept, "User-Agent": "pr-risk-reviewer"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        hint = ""
        if e.code in (401, 403, 404):
            hint = " (private repo, bad token, or rate limit; set GITHUB_TOKEN)"
        sys.exit(f"error: GitHub API returned {e.code}{hint}")
    except urllib.error.URLError as e:
        sys.exit(f"error: network failure: {e.reason}. The sandbox may block this domain.")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    owner, repo, num = parse_ref(sys.argv[1])
    base = f"https://api.github.com/repos/{owner}/{repo}/pulls/{num}"

    meta = json.loads(api(base, "application/vnd.github+json"))
    sys.stderr.write(json.dumps({
        "title": meta.get("title"),
        "author": (meta.get("user") or {}).get("login"),
        "base": (meta.get("base") or {}).get("ref"),
        "head": (meta.get("head") or {}).get("ref"),
        "changed_files": meta.get("changed_files"),
        "additions": meta.get("additions"),
        "deletions": meta.get("deletions"),
        "description": (meta.get("body") or "")[:2000],
    }, indent=2) + "\n")

    sys.stdout.write(api(base, "application/vnd.github.diff"))


if __name__ == "__main__":
    main()
