"""Offline decisions, release notes and PR lifecycle, including real Git refs."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import release_pr as proposer
import release_state as shared
from release_publish import validate_checkout


SOURCE, BASE, COMMIT = "a" * 40, "b" * 40, "c" * 40


def released(tag="v1.2.1", testing=False, draft=False, identity=1):
    return dict(id=identity, tag_name=tag, prerelease=testing, draft=draft, assets=[], body="")


def planned(testing=False):
    return dict(version="1.2.2", prerelease=testing, source=SOURCE, base_ref=BASE,
                base_tag="v1.2.2" if testing else "v1.2.1", release_id=1)


class ReleaseDecisionTests(unittest.TestCase):
    def test_numeric_latest_stable_gets_patch_not_minor(self):
        baseline, version, testing = shared.choose([released("v1.2.9"), released("v1.2.10")])
        self.assertEqual((baseline["tag_name"], version, testing), ("v1.2.10", "1.2.11", False))

    def test_active_prerelease_keeps_version_and_status(self):
        baseline, version, testing = shared.choose([released(), released("v1.3.0", testing=True)])
        self.assertEqual((baseline["tag_name"], version, testing), ("v1.3.0", "1.3.0", True))

    def test_drafts_and_obsolete_prereleases_do_not_select_testing(self):
        _, version, testing = shared.choose([released("v1.2.0", testing=True), released(),
                                             released("v1.4.0", draft=True)])
        self.assertEqual((version, testing), ("1.2.2", False))

    def test_multiple_active_prereleases_and_unknown_tags_fail(self):
        for items in ([], [released("nightly")],
                      [released(), released("v1.2.2", testing=True), released("v1.3.0", testing=True)]):
            with self.subTest(items=items), self.assertRaises(ValueError):
                shared.choose(items)

    def test_plan_validation_prevents_version_and_ref_injection(self):
        shared.validate(planned())
        shared.validate(planned(True))
        for changes in ({"version": "1.3.0"}, {"prerelease": "false"}, {"source": "main"},
                        {"base_ref": "v1.2.1\n"}, {"release_id": True}, {"unexpected": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                shared.validate(dict(planned(), **changes))

    def test_paginated_api_stream_includes_all_pages_and_failures_propagate(self):
        result = subprocess.CompletedProcess([], 0, '[{"id":1}]\n[{"id":2}]', "")
        with patch.object(shared.subprocess, "run", return_value=result):
            self.assertEqual(shared.api(["--paginate", "repos/o/r/releases"]), [{"id": 1}, {"id": 2}])
        result.returncode, result.stderr = 1, "HTTP 403"
        with patch.object(shared.subprocess, "run", return_value=result), self.assertRaisesRegex(RuntimeError, "403"):
            shared.releases("o/r")

    def test_merged_plan_blocks_proposals_until_a_complete_receipt_exists(self):
        plan = planned(True)
        release = released("v1.2.2", testing=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github").mkdir()
            (root / shared.PLAN).write_text(json.dumps(plan))
            self.assertTrue(shared.pending("o/r", [], root))
            for record in (None, {"plan": shared.digest(plan)}):
                with patch.object(shared, "receipt", return_value=record):
                    self.assertTrue(shared.pending("o/r", [release], root))
            files = {"eu.battle-conquest_1.2.2.wotmod": "f" * 64, "battle-conquest-mod_1.2.2.zip": "e" * 64}
            release["assets"] = [dict(name=name, digest="sha256:" + value) for name, value in files.items()]
            record = dict(plan=shared.digest(plan), commit=COMMIT, files=files)
            with patch.object(shared, "receipt", return_value=record):
                self.assertFalse(shared.pending("o/r", [release], root,
                                                request=lambda _: {"object": {"sha": COMMIT}}))
                with self.assertRaisesRegex(ValueError, "receipt.*tag"):
                    shared.pending("o/r", [release], root,
                                   request=lambda _: {"object": {"sha": "d" * 40}})
            release["assets"][0]["digest"] = "sha256:" + "0" * 64
            with patch.object(shared, "receipt", return_value=record):
                self.assertTrue(shared.pending("o/r", [release], root))

    def test_dry_run_does_not_change_files_or_write_to_github(self):
        with patch.object(proposer, "releases", return_value=[released()]), \
                patch.object(proposer, "pending", return_value=False), \
                patch.object(proposer, "proposal", return_value=planned()), \
                patch.object(proposer, "sync") as sync, \
                patch.object(proposer, "run") as git, \
                patch("sys.argv", ["release_pr.py", "--dry-run"]):
            proposer.main()
        sync.assert_not_called()
        git.assert_not_called()

    def test_stale_plan_can_be_reproposed_only_before_its_tag_moves(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github").mkdir()
            (root / shared.PLAN).write_text(json.dumps(planned(True)))
            for reference, allowed in ((BASE, True), (COMMIT, False)):
                with self.subTest(reference=reference), \
                        patch.object(proposer, "REPO", root), \
                        patch.object(proposer, "releases", return_value=[released()]), \
                        patch.object(proposer, "pending", return_value=True), \
                        patch.object(proposer, "run", return_value=reference), \
                        patch.object(proposer, "proposal", return_value=None) as proposal, \
                        patch("sys.argv", ["release_pr.py", "--dry-run", "--replace-pending"]):
                    if allowed:
                        proposer.main()
                        proposal.assert_called_once()
                    else:
                        with self.assertRaisesRegex(ValueError, "already moved"):
                            proposer.main()
                        proposal.assert_not_called()


class ReleaseNotesTests(unittest.TestCase):
    def test_refresh_keeps_curated_notes_and_history_without_duplicate_version(self):
        before = "# Changelog\n\n## 1.2.2\n\nCurated installation.\n- [x] Manual observation\n\n## 1.2.1\n\nOlder release.\n"
        result = proposer.changelog(before, planned(True), ["fix(#45): load the card (#48)"])
        self.assertIn("Curated installation.\n- [x] Manual observation", result)
        self.assertIn("- Load the card", result)
        self.assertIn("same version and prerelease status", result)
        self.assertEqual(result.count("## 1.2.2\n"), 1)
        next_build = proposer.changelog(result, planned(True), ["fix(#46): keep controls readable"])
        self.assertIn("- Load the card", next_build)
        self.assertIn("- Keep controls readable", next_build)
        self.assertTrue(next_build.endswith("## 1.2.1\n\nOlder release.\n"))

    def test_stable_patch_adds_notes_and_retains_previous_releases(self):
        before = "# Changelog\n\n## 1.2.1\n\nOld notes.\n"
        result = proposer.changelog(before, planned(), ["feat(#12): add a display", "chore(#47): automate releases"])
        self.assertIn("## 1.2.2\n\n### Changes in this build\n\n- Add a display", result)
        self.assertNotIn("automate releases", result)
        self.assertTrue(result.endswith("## 1.2.1\n\nOld notes.\n"))

    def test_missing_testing_section_is_created_without_removing_old_notes(self):
        result = proposer.changelog("# Changelog\n\n## 1.2.1\n\nOld.\n", planned(True), [])
        self.assertIn("In-game acceptance remains pending", result)
        self.assertIn("## 1.2.1\n\nOld.", result)

    def test_pr_refresh_preserves_manual_checkboxes_and_notes(self):
        before = "Introduction\n" + proposer.body(planned()) + "\n- [x] Checked\nKeep my note"
        result = proposer.body(planned(True), before)
        self.assertIn("prérelease **1.2.2**", result)
        self.assertTrue(result.startswith("Introduction\n"))
        self.assertTrue(result.endswith("\n- [x] Checked\nKeep my note"))
        self.assertEqual(result.count("- [ ]"), before.count("- [ ]"))
        with self.assertRaises(ValueError):
            proposer.body(planned(), before.replace(proposer.END, "broken"))


class GitReleasePRTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "work"
        self.repo.mkdir()
        self.git(["git", "init", "--bare", str(self.root / "remote")])
        self.git(["git", "init", "-b", "main"])
        self.git(["git", "config", "user.name", "Test"])
        self.git(["git", "config", "user.email", "test@example.invalid"])
        (self.repo / "CHANGELOG.md").write_text("# Changelog\n\n## 1.2.1\n\nOld notes.\n")
        self.commit("initial")
        self.git(["git", "tag", "v1.2.1"])
        self.git(["git", "remote", "add", "origin", str(self.root / "remote")])
        self.git(["git", "push", "origin", "main", "--tags"])
        self.prs, self.writes = [], []

    def git(self, arguments):
        return shared.run(arguments, cwd=self.repo)

    def commit(self, message):
        paths = ["CHANGELOG.md"]
        if message not in {"initial", "release proposal"}:
            (self.repo / "feature.txt").write_text(message)
            paths.append("feature.txt")
        if (self.repo / shared.PLAN).exists():
            paths.append(shared.PLAN)
        self.git(["git", "add", "--", *paths])
        self.git(["git", "commit", "--allow-empty", "-m", message])

    def request(self, arguments, payload=None):
        if payload is None:
            return copy.deepcopy(self.prs)
        self.writes.append((arguments, payload))
        if "POST" in arguments:
            self.prs.append(dict(payload, number=9, html_url="https://example.invalid/pull/9"))
        else:
            self.prs[0].update(payload)
        return self.prs[0]

    def prepare(self):
        plan = proposer.proposal([released()], self.git)
        text = proposer.changelog((self.repo / "CHANGELOG.md").read_text(), plan, ["fix(#47): improve capture"])
        (self.repo / "CHANGELOG.md").write_text(text)
        (self.repo / ".github").mkdir(exist_ok=True)
        (self.repo / shared.PLAN).write_text(json.dumps(plan))
        self.commit("release proposal")
        return plan

    def test_unchanged_main_does_not_propose_release(self):
        self.assertIsNone(proposer.proposal([released()], self.git))

    def test_one_pr_is_created_and_repeated_sync_does_not_push_or_edit(self):
        self.commit("feat(#1): feature still earns only a patch")
        self.git(["git", "push", "origin", "main"])
        plan = self.prepare()
        self.assertEqual(plan["version"], "1.2.2")
        proposer.sync("owner/repo", plan, self.request, self.git)
        remote = self.git(["git", "ls-remote", "origin", "refs/heads/release/next"])
        proposer.sync("owner/repo", plan, self.request, self.git)
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(remote, self.git(["git", "ls-remote", "origin", "refs/heads/release/next"]))

    def test_new_main_refreshes_same_pr_and_preserves_notes(self):
        self.commit("fix(#1): first fix")
        source = self.git(["git", "rev-parse", "HEAD"])
        self.git(["git", "push", "origin", "main"])
        proposer.sync("owner/repo", self.prepare(), self.request, self.git)
        self.prs[0]["body"] += "\n- [x] Tested\nMy note"
        self.git(["git", "switch", "--detach", source])
        self.commit("fix(#2): next fix")
        self.git(["git", "push", "origin", "HEAD:main"])
        proposer.sync("owner/repo", self.prepare(), self.request, self.git)
        self.assertEqual(len(self.prs), 1)
        self.assertEqual(len(self.writes), 2)
        self.assertTrue(self.prs[0]["body"].endswith("\n- [x] Tested\nMy note"))

    def test_a_newer_main_prevents_pushing_a_stale_proposal(self):
        self.commit("fix(#1): fix")
        self.git(["git", "push", "origin", "main"])
        plan = self.prepare()
        self.git(["git", "push", "origin", "HEAD:main"])
        with self.assertRaisesRegex(ValueError, "main moved"):
            proposer.sync("owner/repo", plan, self.request, self.git)
        self.assertEqual(self.writes, [])

    def test_conflicting_draft_does_not_allocate_another_version(self):
        self.commit("fix(#1): fix")
        with self.assertRaisesRegex(ValueError, "already exists"):
            proposer.proposal([released(), released("v1.2.2", draft=True)], self.git)

    def test_manual_tag_on_squashed_notes_branch_can_be_refreshed(self):
        base = self.git(["git", "rev-parse", "HEAD"])
        self.git(["git", "switch", "--detach", base])
        (self.repo / "CHANGELOG.md").write_text("# Changelog\n\n## 1.2.2\n\nTesting notes.\n")
        self.commit("release proposal")
        self.git(["git", "tag", "v1.2.2"])
        self.git(["git", "switch", "main"])
        self.commit("fix(#3): a later source fix")
        plan = proposer.proposal([released("v1.2.2", testing=True)], self.git)
        self.assertEqual((plan["version"], plan["prerelease"]), ("1.2.2", True))

    def test_manual_tag_with_code_not_on_main_cannot_lose_that_code(self):
        base = self.git(["git", "rev-parse", "HEAD"])
        self.git(["git", "switch", "--detach", base])
        self.commit("feat(#3): unmerged feature")
        self.git(["git", "tag", "v1.2.2"])
        self.git(["git", "switch", "main"])
        self.commit("fix(#4): unrelated main fix")
        with self.assertRaisesRegex(ValueError, "source changes into main"):
            proposer.proposal([released("v1.2.2", testing=True)], self.git)

    def test_squashed_release_source_commits_already_on_main_do_not_block_refresh(self):
        self.git(["git", "switch", "-c", "manual-release"])
        self.commit("feat(#3): first source change")
        self.commit("fix(#4): second source change")
        self.git(["git", "tag", "v1.2.2"])
        self.git(["git", "switch", "main"])
        self.git(["git", "merge", "--squash", "manual-release"])
        self.git(["git", "commit", "-m", "feat(#3): integrate both source changes"])
        self.commit("fix(#5): later mod fix")
        plan = proposer.proposal([released("v1.2.2", testing=True)], self.git)
        self.assertEqual((plan["version"], plan["prerelease"]), ("1.2.2", True))

    def test_publication_accepts_a_merged_plan_and_refuses_an_unmerged_one(self):
        self.commit("fix(#1): mod change")
        self.git(["git", "push", "origin", "main"])
        plan = self.prepare()
        with self.assertRaises(RuntimeError):
            validate_checkout(plan, self.git)
        self.git(["git", "push", "origin", "HEAD:main"])
        self.assertEqual(validate_checkout(plan, self.git), self.git(["git", "rev-parse", "HEAD"]))
        self.commit("fix(#2): source changed during review")
        self.git(["git", "push", "origin", "HEAD:main"])
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_checkout(plan, self.git)


if __name__ == "__main__":
    unittest.main()
