"""Offline publication, retries and protection of releases already accepted."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import release_publish as publisher
import release_state as shared
from test_release_plan import BASE, COMMIT, planned, released


class GitHub:
    def __init__(self, testing=False):
        self.items = [released("v1.2.2" if testing else "v1.2.1", testing=testing)]
        self.refs = {self.items[0]["tag_name"]: BASE}
        self.records, self.writes, self.uploads = {}, [], []
        self.fail_file = None

    def __call__(self, arguments, payload=None):
        endpoint = next(arg for arg in arguments if arg.startswith("repos/"))
        if payload is None:
            if "/releases?" in endpoint:
                return copy.deepcopy(self.items)
            if "/git/ref/tags/" in endpoint:
                return {"object": {"sha": self.refs[endpoint.rsplit("/", 1)[1]]}}
            if "/git/matching-refs/tags/" in endpoint:
                prefix = endpoint.rsplit("/", 1)[1]
                return [dict(ref="refs/tags/" + tag, object={"sha": value})
                        for tag, value in self.refs.items() if tag.startswith(prefix)]
            raise AssertionError(endpoint)
        self.writes.append((arguments, copy.deepcopy(payload)))
        if endpoint.endswith("/releases"):
            item = dict(payload, id=len(self.items) + 1, assets=[])
            self.items.append(item)
            return copy.deepcopy(item)
        if "/git/refs/tags/" in endpoint:
            self.refs[endpoint.rsplit("/", 1)[1]] = payload["sha"]
        elif endpoint.endswith("/git/refs"):
            self.refs[payload["ref"].removeprefix("refs/tags/")] = payload["sha"]
        elif "/releases/" in endpoint:
            item = next(item for item in self.items if item["id"] == int(endpoint.rsplit("/", 1)[1]))
            item.update(payload)
        else:
            raise AssertionError(endpoint)
        return {}

    def upload(self, command):
        self.uploads.append(command)
        self.assert_upload(command)
        target = next(item for item in self.items if item["tag_name"] == command[3])
        paths = command[4:command.index("--repo")]
        for filename in paths:
            path = Path(filename)
            if self.fail_file == path.name:
                self.fail_file = None
                raise RuntimeError("simulated interrupted upload")
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            target["assets"] = [item for item in target["assets"] if item["name"] != path.name]
            target["assets"].append(dict(name=path.name, digest="sha256:" + checksum))
            if path.name == shared.RECEIPT:
                self.records[target["tag_name"]] = json.loads(path.read_text())

    def assert_upload(self, command):
        assert command[:3] == ["gh", "release", "upload"]
        assert command[-1] == "--clobber"

    def receipt(self, repo, target):
        return self.records.get(target["tag_name"])


class ReleasePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = [self.root / name for name in
                      ("eu.battle-conquest_1.2.2.wotmod", "battle-conquest-mod_1.2.2.zip")]
        for path in self.files:
            path.write_bytes(b"checked build fixture")

    def publish(self, hub, testing=False):
        publisher.publish("owner/repo", planned(testing), COMMIT, "## 1.2.2\n\nReviewed notes.",
                          self.files, request=hub, command=hub.upload, read_receipt=hub.receipt)

    def test_prerelease_refresh_moves_only_its_tag_and_keeps_its_identity(self):
        hub = GitHub(True)
        self.publish(hub, True)
        self.assertEqual(len(hub.items), 1)
        self.assertEqual(hub.items[0]["id"], 1)
        self.assertTrue(hub.items[0]["prerelease"])
        self.assertFalse(hub.items[0]["draft"])
        self.assertEqual(hub.refs, {"v1.2.2": COMMIT})
        self.assertIn("Reviewed notes", hub.items[0]["body"])
        self.assertEqual(hub.uploads[-1][4], str(self.root / shared.RECEIPT))
        self.assertTrue(shared.completed(planned(True), hub.records["v1.2.2"], hub.items[0]))

    def test_stable_patch_uses_a_draft_until_all_assets_are_uploaded(self):
        hub = GitHub()
        self.publish(hub)
        self.assertEqual(hub.refs, {"v1.2.1": BASE, "v1.2.2": COMMIT})
        target = hub.items[-1]
        self.assertFalse(target["prerelease"])
        self.assertFalse(target["draft"])
        self.assertEqual(hub.writes[0][1]["draft"], True)
        self.assertEqual(hub.writes[-1][1], {"draft": False, "make_latest": "true"})

    def test_completed_plan_is_idempotent_for_both_release_types(self):
        for testing in (False, True):
            with self.subTest(testing=testing):
                hub = GitHub(testing)
                self.publish(hub, testing)
                before = (len(hub.writes), len(hub.uploads), len(hub.items))
                self.publish(hub, testing)
                self.assertEqual((len(hub.writes), len(hub.uploads), len(hub.items)), before)

    def test_interrupted_upload_resumes_same_version_without_publishing_a_partial_stable(self):
        for testing in (False, True):
            with self.subTest(testing=testing):
                hub = GitHub(testing)
                hub.fail_file = self.files[-1].name
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    self.publish(hub, testing)
                self.assertNotIn("v1.2.2", hub.records)
                if not testing:
                    self.assertTrue(hub.items[-1]["draft"])
                count = len(hub.items)
                self.publish(hub, testing)
                self.assertEqual(len(hub.items), count)
                self.assertIn("v1.2.2", hub.records)
                self.assertFalse(hub.items[-1]["draft"])

    def test_receipt_upload_failure_also_resumes_without_creating_another_version(self):
        hub = GitHub(True)
        hub.fail_file = shared.RECEIPT
        with self.assertRaises(RuntimeError):
            self.publish(hub, True)
        self.assertFalse(hub.records)
        self.publish(hub, True)
        self.assertEqual(len(hub.items), 1)
        self.assertTrue(hub.items[0]["prerelease"])

    def test_promotion_during_review_is_never_reversed(self):
        hub = GitHub(True)
        hub.items[0]["prerelease"] = False
        with self.assertRaisesRegex(ValueError, "state changed"):
            self.publish(hub, True)
        self.assertFalse(hub.writes)
        self.assertFalse(hub.uploads)

    def test_new_testing_release_during_review_blocks_stable_publication(self):
        hub = GitHub()
        hub.items.append(released("v1.3.0", testing=True, identity=2))
        with self.assertRaisesRegex(ValueError, "state changed"):
            self.publish(hub)
        self.assertFalse(hub.writes)

    def test_moved_baseline_or_unrelated_draft_cannot_be_overwritten(self):
        hub = GitHub(True)
        hub.refs["v1.2.2"] = "d" * 40
        with self.assertRaisesRegex(ValueError, "tag moved"):
            self.publish(hub, True)
        self.assertFalse(hub.writes)
        hub = GitHub()
        hub.items.append(released("v1.2.2", draft=True, identity=2))
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.publish(hub)
        self.assertFalse(hub.writes)

    def test_existing_stable_release_is_never_replaced(self):
        hub = GitHub()
        hub.items.append(released("v1.2.2", identity=2))
        with self.assertRaises(ValueError):
            self.publish(hub)
        self.assertFalse(hub.writes)
        self.assertFalse(hub.uploads)

    def test_new_tag_pointing_to_another_commit_is_never_moved(self):
        hub = GitHub()
        hub.refs["v1.2.2"] = "d" * 40
        with self.assertRaisesRegex(ValueError, "another build"):
            self.publish(hub)
        self.assertEqual(hub.refs["v1.2.2"], "d" * 40)
        self.assertFalse(hub.uploads)
        self.assertFalse(hub.writes)
        self.assertEqual(len(hub.items), 1)

    def test_build_failure_never_enters_publication(self):
        (self.root / ".github").mkdir()
        (self.root / shared.PLAN).write_text(json.dumps(planned()))
        (self.root / "CHANGELOG.md").write_text("# Changelog\n\n## 1.2.2\n\nNotes.\n")
        with patch.object(publisher, "REPO", self.root), \
                patch.object(publisher, "validate_checkout", return_value=COMMIT), \
                patch.object(publisher, "state", return_value=(None, False)), \
                patch.object(publisher, "build", side_effect=RuntimeError("failed check")), \
                patch.object(publisher, "publish") as publish, \
                patch("sys.argv", ["release_publish.py", "--python27", "/fake/python"]):
            with self.assertRaisesRegex(RuntimeError, "failed check"):
                publisher.main()
        publish.assert_not_called()

    def test_checkout_must_be_clean_merged_and_contain_only_reviewed_metadata(self):
        calls = []

        def git(arguments):
            calls.append(arguments)
            if arguments[1] == "rev-parse":
                return COMMIT
            if arguments[1] == "diff":
                return shared.PLAN + "\nCHANGELOG.md"
            return ""

        self.assertEqual(publisher.validate_checkout(planned(), git), COMMIT)
        self.assertIn(["git", "merge-base", "--is-ancestor", COMMIT, "origin/main"], calls)

        def stale(arguments):
            return git(arguments) + "\nsrc/battle_conquest/config.py" if arguments[1] == "diff" else git(arguments)

        with self.assertRaisesRegex(ValueError, "stale"):
            publisher.validate_checkout(planned(), stale)


if __name__ == "__main__":
    unittest.main()
