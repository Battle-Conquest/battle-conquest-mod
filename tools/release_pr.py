"""Keep one release PR open for changes on main; merging stays manual."""
import argparse
import json
import os

from release import SUBJECT, TOLD
from release_state import (BRANCH, PLAN, REPO, REPOSITORY, api, choose, notes,
                           pending, releases, run, validate)


START = "<!-- mod-release:start -->"
END = "<!-- mod-release:end -->"


def proposal(published, git=run):
    baseline, version, prerelease = choose(published)
    source = git(["git", "rev-parse", "HEAD"])
    base = git(["git", "rev-parse", baseline["tag_name"] + "^{commit}"])
    git(["git", "merge-base", base, source])
    # Older manual releases were tagged on a release branch, then squash
    # merged. Their note commit need not be an ancestor of main. Do not,
    # however, discard mod changes which still live only on that branch.
    unpublished = git(["git", "log", "--cherry-pick", "--right-only", "--format=%H",
                       source + "..." + base, "--", ".", ":(exclude)CHANGELOG.md", ":(exclude)" + PLAN])
    if unpublished:
        raise ValueError("merge the published release's source changes into main before refreshing it")
    if not git(["git", "diff", "--name-only", base, source]):
        return None
    if not prerelease and any(item["tag_name"] == "v" + version for item in published):
        raise ValueError("the next version already exists; finish or remove its draft first")
    plan = dict(version=version, prerelease=prerelease, source=source,
                base_tag=baseline["tag_name"], release_id=baseline["id"],
                base_ref=git(["git", "rev-parse", "refs/tags/" + baseline["tag_name"]]))
    validate(plan)
    return plan


def changelog(text, plan, subjects):
    entries = []
    for subject in subjects:
        match = SUBJECT.match(subject.strip())
        if match and match[1] in TOLD:
            entries.append("- " + match[2][0].upper() + match[2][1:])
    if not entries:
        entries = ["- Maintenance updates to the mod and its release tooling."]
    addition = "### Changes in this build\n\n" + "\n".join(dict.fromkeys(entries))
    if plan["prerelease"]:
        try:
            section = notes(text, plan["version"])
        except ValueError:
            section = "## %s\n\nTesting prerelease. In-game acceptance remains pending." % plan["version"]
            text = "# Changelog\n\n" + section + "\n\n" + text.removeprefix("# Changelog").lstrip()
        # Existing installation instructions, observations and manual acceptance
        # notes remain part of the testing release, even after several refreshes.
        updated = section + "\n\n" + addition + (
            "\n\nThis refresh keeps the same version and prerelease status. "
            "Download the ZIP again to replace an earlier build. In-game acceptance must be repeated.")
        return text.replace(section, updated, 1)
    section = "## %s\n\n%s" % (plan["version"], addition)
    return "# Changelog\n\n" + section + "\n\n" + text.removeprefix("# Changelog").lstrip()


def body(plan, previous=""):
    action = ("Actualise la prérelease **%s**, avec le même numéro et le même statut."
              if plan["prerelease"] else "Publie une nouvelle release stable **%s** (incrément patch).")
    report = (START + "\n" + action % plan["version"] +
              "\n\nLa fusion **manuelle** construit et vérifie le paquet avant publication. "
              "Les notes viennent de `CHANGELOG.md` ; les relire dans cette PR. "
              "Le dossier WoT du ZIP reste inchangé ; le joueur l’adapte si nécessaire.\n" + END)
    if not previous:
        return report + ("\n\n- [ ] Relire les changements et les notes de version."
                         "\n- [ ] Valider les contrôles et la recette en jeu utile avant de fusionner.")
    if previous.count(START) != 1 or previous.count(END) != 1:
        raise ValueError("release PR has no unambiguous managed section")
    left, rest = previous.split(START)
    _, right = rest.split(END)
    return left + report + right


def sync(repo, plan, request=api, git=run):
    current = git(["git", "ls-remote", "origin", "refs/heads/main"]).split()[0]
    if current != plan["source"]:
        raise ValueError("main moved while proposing the release; rerun the proposal")
    prs = request(["repos/%s/pulls?state=open&head=%s:%s&base=main" %
                   (repo, repo.split("/")[0], BRANCH)])
    if len(prs) > 1:
        raise ValueError("multiple release PRs")
    pr = prs[0] if prs else None
    remote = git(["git", "ls-remote", "origin", "refs/heads/" + BRANCH])
    remote_sha = remote.split()[0] if remote else ""
    if remote_sha:
        git(["git", "fetch", "origin", BRANCH])
        # Never overwrite an unrelated branch which happens to use this name.
        previous_plan = json.loads(git(["git", "show", "FETCH_HEAD:" + PLAN]))
        validate(previous_plan)
        same = not git(["git", "diff", "--name-only", "FETCH_HEAD", "HEAD", "--", PLAN, "CHANGELOG.md"])
        if same and previous_plan == plan and pr:
            print("The release PR is unchanged: " + pr["html_url"])
            return
    # Validate the managed body before pushing, so a damaged PR does not cause
    # a branch rewrite which the maintainer cannot see explained in the PR.
    payload = dict(title="chore(#47): préparer la release %s" % plan["version"],
                   body=body(plan, pr["body"] if pr else ""))
    git(["git", "push", "--force-with-lease=refs/heads/%s:%s" % (BRANCH, remote_sha),
         "origin", "HEAD:refs/heads/" + BRANCH])
    if pr:
        result = request(["--method", "PATCH", "repos/%s/pulls/%s" % (repo, pr["number"]),
                          "--input", "-"], payload)
    else:
        result = request(["--method", "POST", "repos/%s/pulls" % repo, "--input", "-"],
                         dict(payload, base="main", head=BRANCH))
    print(result["html_url"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="read state; do not change files or GitHub")
    parser.add_argument("--replace-pending", action="store_true",
                        help="replace a stale merged plan through a new manually reviewed PR")
    args = parser.parse_args()
    repo = os.environ.get("GH_REPO", REPOSITORY)
    if repo != REPOSITORY:
        raise ValueError("release automation is disabled outside the official repository")
    published = releases(repo)
    if pending(repo, published):
        if not args.replace_pending:
            return
        old = json.loads((REPO / PLAN).read_text())
        if run(["git", "rev-parse", "refs/tags/" + old["base_tag"]]) != old["base_ref"]:
            raise ValueError("publication already moved the tag; resume that plan instead")
    plan = proposal(published)
    if plan is None:
        print("No changes since the published build.")
        return
    print(json.dumps(plan, indent=2))
    if args.dry_run:
        return
    if run(["git", "status", "--porcelain"]):
        raise ValueError("release proposal requires a clean checkout")
    text = (REPO / "CHANGELOG.md").read_text()
    subjects = run(["git", "log", "--cherry-pick", "--right-only", "--reverse", "--pretty=%s",
                    plan["base_tag"] + "...HEAD"]).splitlines()
    (REPO / "CHANGELOG.md").write_text(changelog(text, plan, subjects))
    (REPO / PLAN).write_text(json.dumps(plan, indent=2) + "\n")
    run(["git", "add", "--", PLAN, "CHANGELOG.md"])
    run(["git", "commit", "-m", "chore(#47): prepare release " + plan["version"]])
    sync(repo, plan)


if __name__ == "__main__":
    main()
