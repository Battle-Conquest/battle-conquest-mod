"""Shared release state. Python 3, never imported by the game.

The merged plan is an approval to publish one build. A receipt attached last
to that release prevents a second proposal while publication is incomplete.
"""
import hashlib
import json
import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
PLAN = ".github/release-plan.json"
RECEIPT = "release-build.json"
BRANCH = "release/next"
REPOSITORY = "Battle-Conquest/battle-conquest-mod"
TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
SHA = re.compile(r"[0-9a-f]{40}")


def run(arguments, cwd=REPO):
    result = subprocess.run(arguments, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError("%s failed:\n%s" % (arguments[0], result.stderr or result.stdout))
    return result.stdout.strip()


def api(arguments, payload=None):
    result = subprocess.run(["gh", "api"] + arguments,
                            input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError("GitHub request failed: %s" % result.stderr)
    if "--paginate" not in arguments:
        return json.loads(result.stdout) if result.stdout.strip() else None
    pages, remaining = [], result.stdout.strip()
    decoder = json.JSONDecoder()
    while remaining:
        page, end = decoder.raw_decode(remaining)
        pages.extend(page)
        remaining = remaining[end:].strip()
    return pages


def releases(repo, request=api):
    return request(["--paginate", "repos/%s/releases?per_page=100" % repo])


def number(tag):
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError("release tags must use vX.Y.Z: %r" % tag)
    return tuple(int(part) for part in match.groups())


def choose(published):
    visible = [item for item in published if not item["draft"]]
    for item in visible:
        number(item["tag_name"])
    stable = [item for item in visible if not item["prerelease"]]
    latest = max(stable, key=lambda item: number(item["tag_name"])) if stable else None
    testing = [item for item in visible if item["prerelease"]
               and (latest is None or number(item["tag_name"]) > number(latest["tag_name"]))]
    if len(testing) > 1:
        raise ValueError("multiple active prereleases; select one before proposing a release")
    if testing:
        return testing[0], testing[0]["tag_name"][1:], True
    if latest is None:
        raise ValueError("no published release to use as a baseline")
    major, minor, patch = number(latest["tag_name"])
    return latest, "%d.%d.%d" % (major, minor, patch + 1), False


def digest(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()


def receipt(repo, release):
    assets = [asset for asset in release["assets"] if asset["name"] == RECEIPT]
    if len(assets) > 1:
        raise ValueError("ambiguous release receipt")
    if not assets:
        return None
    # gh follows GitHub's redirect and authenticates private/draft assets too.
    return json.loads(run(["gh", "api", "repos/%s/releases/assets/%s" % (repo, assets[0]["id"]),
                           "-H", "Accept: application/octet-stream"]))


def completed(plan, record, release):
    if not record or record.get("plan") != digest(plan) or not SHA.fullmatch(record.get("commit", "")):
        return False
    expected = {template % plan["version"] for template in
                ("eu.battle-conquest_%s.wotmod", "battle-conquest-mod_%s.zip")}
    files = record.get("files", {})
    assets = {asset["name"]: asset for asset in release["assets"]}
    if set(files) != expected or not expected <= set(assets):
        return False
    for name, checksum in files.items():
        if not re.fullmatch(r"[0-9a-f]{64}", checksum):
            return False
        if assets[name].get("digest") and assets[name]["digest"] != "sha256:" + checksum:
            return False
    return True


def confirmed(repo, plan, release, request=api, read_receipt=receipt):
    record = read_receipt(repo, release)
    if not completed(plan, record, release):
        return False
    reference = request(["repos/%s/git/ref/tags/%s" % (repo, release["tag_name"])])
    if reference["object"]["sha"] != record["commit"]:
        raise ValueError("the completed release receipt and tag disagree; resolve the moved tag first")
    return True


def validate(plan):
    if set(plan) != {"version", "prerelease", "source", "base_tag", "base_ref", "release_id"}:
        raise ValueError("invalid release plan fields")
    number("v" + plan["version"])
    number(plan["base_tag"])
    if type(plan["prerelease"]) is not bool or type(plan["release_id"]) is not int:
        raise ValueError("invalid release plan state")
    if not SHA.fullmatch(plan["source"]) or not SHA.fullmatch(plan["base_ref"]):
        raise ValueError("invalid release plan commit")
    expected = number(plan["base_tag"])
    if not plan["prerelease"]:
        expected = expected[:2] + (expected[2] + 1,)
    if number("v" + plan["version"]) != expected:
        raise ValueError("a release must refresh the prerelease or increment the patch")


def notes(changelog, version):
    match = re.search(r"^## " + re.escape(version) + r"\n.*?(?=^## |\Z)", changelog, re.M | re.S)
    if not match:
        raise ValueError("release section is missing from CHANGELOG.md")
    return match.group().strip()


def pending(repo, published, root=REPO, request=api):
    path = root / PLAN
    if not path.exists():
        return False
    plan = json.loads(path.read_text())
    validate(plan)
    found = [item for item in published if item["tag_name"] == "v" + plan["version"]]
    if len(found) == 1 and not found[0]["draft"] and confirmed(repo, plan, found[0], request, receipt):
        return False
    print("The merged release plan is not complete; rerun Mod release for its merge commit.")
    return True
