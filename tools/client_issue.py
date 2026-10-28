"""Keep one client-update issue per WoT version, without daily comments.

Adapted from unicum.gg-mod; see NOTICE and LICENSE (AGPL-3.0).

Python 3; called by the client workflow, never shipped inside the mod.
Only the marked report belongs to the bot. Everything outside it stays intact.
"""
import json
import re
import subprocess


VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){3}")


def gh_json(arguments, payload=None):
    try:
        result = subprocess.run(
            ["gh", "api"] + arguments,
            input=json.dumps(payload) if payload is not None else None,
            text=True, capture_output=True, check=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError("GitHub API request failed: %s" % (error.stderr or str(error))) from error
    if "--paginate" not in arguments:
        return json.loads(result.stdout)
    # gh emits one JSON array per page. Decode that stream without requiring
    # --slurp, which is absent from older CLI installations used locally.
    pages = []
    remaining = result.stdout.strip()
    decoder = json.JSONDecoder()
    while remaining:
        page, end = decoder.raw_decode(remaining)
        pages.append(page)
        remaining = remaining[end:].strip()
    return pages


def sync_issue(repo, live, report, title, suffix="", api=gh_json):
    if not VERSION.fullmatch(live):
        raise ValueError("invalid client version")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", repo):
        raise ValueError("invalid repository")
    start = "<!-- client-watch:%s:start -->" % live
    end = "<!-- client-watch:%s:end -->" % live
    block = start + "\n" + report.strip() + "\n" + end
    pages = api(["--paginate", "repos/%s/issues?state=all&per_page=100" % repo])
    candidates = [issue for page in pages for issue in page
                  if "pull_request" not in issue
                  and issue.get("user", {}).get("login") == "github-actions[bot]"
                  and start in (issue.get("body") or "")]
    if not candidates:
        return api(["--method", "POST", "repos/%s/issues" % repo, "--input", "-"],
                   {"title": title, "body": block + suffix})

    # Reuse the oldest issue, including closed ones.
    issue = min(candidates, key=lambda item: item["number"])
    previous = issue.get("body") or ""
    if previous.count(start) != 1 or previous.count(end) != 1:
        raise ValueError("ambiguous managed issue section")
    left, rest = previous.split(start, 1)
    _, right = rest.split(end, 1)
    body = left + block + right
    changes = {}
    if body != previous:
        changes["body"] = body
    if issue.get("state") == "closed":
        changes["state"] = "open"
    # Existing titles may have been edited by a maintainer. The marker, not
    # the title, identifies the issue, so there is no reason to reset it.
    if changes:
        return api(["--method", "PATCH", "repos/%s/issues/%s" % (repo, issue["number"]),
                    "--input", "-"], changes)
    print("Client %s: #%s is unchanged" % (live, issue["number"]))
    return issue
