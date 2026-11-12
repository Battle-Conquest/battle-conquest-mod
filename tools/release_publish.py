"""Build and publish only the reviewed, merged release plan. Python 3."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from build_release import GAME_VERSION
from bundle_check import check_bundle
from release_state import (PLAN, RECEIPT, REPO, REPOSITORY, api, choose,
                           confirmed, digest, notes, receipt, releases, run, validate)


def existing_tag(repo, tag, commit, request):
    refs = request(["repos/%s/git/matching-refs/tags/%s" % (repo, tag)])
    exact = [ref for ref in refs if ref["ref"] == "refs/tags/" + tag]
    if exact and (len(exact) != 1 or exact[0]["object"]["sha"] != commit):
        raise ValueError("the new release tag already points to another build")
    return bool(exact)


def state(repo, plan, commit, request=api, read_receipt=receipt):
    published = releases(repo, request)
    matches = [item for item in published if item["tag_name"] == "v" + plan["version"]]
    if len(matches) > 1:
        raise ValueError("multiple releases for the planned version")
    target = matches[0] if matches else None
    if target and not target["draft"] and confirmed(repo, plan, target, request, read_receipt):
        return target, True
    baseline, _, testing = choose(published)
    if baseline["id"] != plan["release_id"] or testing != plan["prerelease"]:
        raise ValueError("the release state changed after review; prepare a fresh PR")
    reference = request(["repos/%s/git/ref/tags/%s" % (repo, plan["base_tag"])])["object"]["sha"]
    allowed = {plan["base_ref"], commit} if testing else {plan["base_ref"]}
    if reference not in allowed:
        raise ValueError("the baseline tag moved after review")
    if testing:
        if target is None or target["id"] != plan["release_id"] or target["draft"] or not target["prerelease"]:
            raise ValueError("only the active prerelease can be replaced")
    elif target:
        marker = "<!-- release-plan:%s -->" % digest(plan)
        if not target["draft"] or marker not in (target["body"] or ""):
            raise ValueError("the planned version already exists; stable releases are never replaced")
    if not testing:
        existing_tag(repo, "v" + plan["version"], commit, request)
    return target, False


def validate_checkout(plan, git=run):
    validate(plan)
    commit = git(["git", "rev-parse", "HEAD"])
    git(["git", "merge-base", "--is-ancestor", commit, "origin/main"])
    git(["git", "merge-base", "--is-ancestor", plan["source"], commit])
    if git(["git", "status", "--porcelain"]):
        raise ValueError("publication requires a clean checkout")
    # A stale PR may merge alongside newer main changes. They were absent from
    # the proposal and its notes; do not silently include them in this build.
    changed = git(["git", "diff", "--name-only", plan["source"], commit]).splitlines()
    if PLAN not in changed or set(changed) - {PLAN, "CHANGELOG.md"}:
        raise ValueError("the release PR is stale or contains changes beyond its plan and notes")
    return commit


def build(plan, python27, command=run):
    command([sys.executable, "-B", "tools/build_release.py", "--version", plan["version"],
             "--python27", python27])
    command([python27, "-B", "tools/release_check.py",
             "dist/eu.battle-conquest_%s.wotmod" % plan["version"]])


def publish(repo, plan, commit, text, files, request=api, command=run, read_receipt=receipt):
    target, done = state(repo, plan, commit, request, read_receipt)
    if done:
        print("This release plan was already published.")
        return
    # Recheck the exact upload files before any tag or release mutation.
    check_bundle(files[1], files[0], GAME_VERSION)
    tag = "v" + plan["version"]
    marker = "<!-- release-plan:%s -->" % digest(plan)
    body = text.strip() + "\n\n" + marker
    if target is None:
        target = request(["--method", "POST", "repos/%s/releases" % repo, "--input", "-"],
                         dict(tag_name=tag, target_commitish=commit, name=plan["version"],
                              body=body, draft=True, prerelease=False))
    if plan["prerelease"]:
        # Stable tags are never moved. The user explicitly asked testing builds
        # to keep their version, so only this prerelease's ref can be refreshed.
        request(["--method", "PATCH", "repos/%s/git/refs/tags/%s" % (repo, tag), "--input", "-"],
                {"sha": commit, "force": True})
    else:
        if not existing_tag(repo, tag, commit, request):
            request(["--method", "POST", "repos/%s/git/refs" % repo, "--input", "-"],
                    {"ref": "refs/tags/" + tag, "sha": commit})
    # All checks have passed before replacing files. A receipt goes up last;
    # if an upload fails, rerunning this same merged plan repairs that version.
    command(["gh", "release", "upload", tag, *[str(path) for path in files],
             "--repo", repo, "--clobber"])
    request(["--method", "PATCH", "repos/%s/releases/%s" % (repo, target["id"]), "--input", "-"],
            dict(name=plan["version"], body=body, target_commitish=commit,
                 prerelease=plan["prerelease"]))
    record = files[0].parent / RECEIPT
    record.write_text(json.dumps(dict(plan=digest(plan), commit=commit, game_version=GAME_VERSION,
                                     files={path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                            for path in files}), indent=2) + "\n")
    command(["gh", "release", "upload", tag, str(record), "--repo", repo, "--clobber"])
    if not plan["prerelease"]:
        request(["--method", "PATCH", "repos/%s/releases/%s" % (repo, target["id"]), "--input", "-"],
                {"draft": False, "make_latest": "true"})
    print("Published https://github.com/%s/releases/tag/%s" % (repo, tag))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python27", required=True, help="Python 2.7 executable or container wrapper")
    args = parser.parse_args()
    repo = os.environ.get("GH_REPO", REPOSITORY)
    if repo != REPOSITORY:
        raise ValueError("release automation is disabled outside the official repository")
    plan = json.loads((REPO / PLAN).read_text())
    commit = validate_checkout(plan)
    text = notes((REPO / "CHANGELOG.md").read_text(), plan["version"])
    _, done = state(repo, plan, commit)
    if done:
        print("This release plan was already published.")
    else:
        build(plan, str(Path(args.python27).resolve()))
        files = [REPO / "dist" / (template % plan["version"])
                 for template in ("eu.battle-conquest_%s.wotmod", "battle-conquest-mod_%s.zip")]
        publish(repo, plan, commit, text, files)
    # A main push during publication was intentionally blocked by pending().
    # No push occurs when assets finish uploading, so explicitly replay the
    # proposal then. A completed retry also repairs a failed dispatch.
    run(["gh", "workflow", "run", "release-pr.yml", "--repo", repo, "--ref", "main"])


if __name__ == "__main__":
    main()
