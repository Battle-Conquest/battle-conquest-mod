"""Offline tests for WoT detection and the published installation archive."""
import io
import json
import unittest
from unittest.mock import patch
import zipfile

import client_watch as watch


REPO = "Battle-Conquest/battle-conquest-mod"
URL = "https://github.com/%s/releases/download/v1.2.0/battle-conquest-mod_1.2.0.zip" % REPO


def mirror(version):
    return ('<root><Paths><Path>./mods/%s</Path></Paths></root>' % version).encode()


def hub(*versions):
    data = json.dumps({"gameVersions": [{"version": value} for value in versions]})
    return data.replace('"', r"\\u0022").encode()


def archive(*names):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as result:
        for name in names:
            result.writestr(name, b"dummy package")
    return buffer.getvalue()


def package(version):
    return "mods/%s/eu.battle-conquest_1.2.0.wotmod" % version


class ClientWatchTests(unittest.TestCase):
    def fixtures(self, upstream="2.4.1.0", current="2.4.1.1", shipped="2.4.1.0"):
        self.responses = {watch.MIRROR: mirror(upstream), watch.HUB: hub(current),
                          URL: archive(package(shipped))}
        self.release = {"tag_name": "v1.2.0", "assets": [
            {"name": "battle-conquest-mod_1.2.0.zip", "browser_download_url": URL},
            {"name": "eu.battle-conquest_1.2.0.wotmod"},
        ]}

    def fetch(self, url):
        result = self.responses[url]
        if isinstance(result, Exception):
            raise result
        return result

    def api(self, arguments):
        self.assertEqual(arguments, ["repos/%s/releases/latest" % REPO])
        return self.release

    def compare(self):
        return watch.compare(REPO, api=self.api, fetcher=self.fetch)

    def test_numeric_ordering_handles_minor_and_patch_versions(self):
        self.assertGreater(watch.numbers("2.4.1.10"), watch.numbers("2.4.1.9"))
        self.assertGreater(watch.numbers("2.10.0.0"), watch.numbers("2.9.9.9"))
        self.assertEqual(watch.numbers("02.04.1.1"), watch.numbers("2.4.1.1"))
        for invalid in ("", "2.4.1", "2.4.1.1-beta", "2.4.1.1\noutput=yes"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                watch.numbers(invalid)

    def test_mirror_ignores_res_mods_and_rejects_ambiguous_versions(self):
        value = b'<root><Paths><Path>./res_mods/9.9.9.9</Path><Path>./mods/2.4.1.1</Path></Paths></root>'
        self.assertEqual(watch.parse_mirror(value), "2.4.1.1")
        for invalid in (b"bad XML", b"<root/>", mirror("2.4.1"),
                        b"<root><Paths><Path>./mods/2.4.1.0</Path><Path>./mods/2.4.1.1</Path></Paths></root>"):
            with self.subTest(invalid=invalid), self.assertRaises((ValueError, watch.ElementTree.ParseError)):
                watch.parse_mirror(invalid)

    def test_hub_handles_escaped_quotes_and_unsorted_version_lists(self):
        self.assertEqual(watch.parse_hub(hub("2.4.1.9", "2.4.1.10", "2.4.0.0")), "2.4.1.10")
        plain = b'{"gameVersions":[{"version":"2.4.1.1"}],"version":"9.9.9.9"}'
        self.assertEqual(watch.parse_hub(plain), "2.4.1.1")
        self.assertEqual(watch.parse_hub(hub("2.4.1.1").replace(b"\\\\u", b"\\u")), "2.4.1.1")
        for invalid in (b"<html>version 9.9.9.9</html>", hub(), hub("2.4.1"),
                        b'{"gameVersions":[{"id":1}]}'):
            with self.subTest(invalid=invalid), self.assertRaises((ValueError, KeyError)):
                watch.parse_hub(invalid)

    def test_newest_source_detects_outdated_zip_and_reports_disagreement(self):
        self.fixtures()
        result = self.compare()
        self.assertEqual(result["live"], "2.4.1.1")
        self.assertTrue(result["news"])
        self.assertTrue(result["disagree"])
        self.assertIn("une nouvelle release est nécessaire", watch.report(result))
        self.assertIn("divergent", watch.report(result))

    def test_mirror_can_be_newer_than_hub(self):
        self.fixtures(upstream="2.4.1.2")
        self.assertEqual(self.compare()["live"], "2.4.1.2")

    def test_equal_or_ahead_package_never_alerts(self):
        for shipped in ("2.4.1.1", "2.4.1.2"):
            self.fixtures(shipped=shipped)
            result = self.compare()
            self.assertFalse(result["news"])
            expected = "cible la version" if shipped == "2.4.1.1" else "en avance"
            self.assertIn(expected, watch.report(result))

    def test_one_failed_source_still_compares_and_exposes_unavailability(self):
        for source in (watch.MIRROR, watch.HUB):
            for failure in (TimeoutError("timeout"), b"broken response"):
                self.fixtures()
                self.responses[source] = failure
                result = self.compare()
                self.assertIn("indisponible", watch.report(result))
                self.assertFalse(result["disagree"])

    def test_both_sources_failed_never_report_current(self):
        self.fixtures()
        self.responses.update({watch.MIRROR: TimeoutError(), watch.HUB: b"maintenance"})
        with self.assertRaisesRegex(ValueError, "neither"):
            self.compare()

    def test_missing_or_multiple_zip_assets_fail(self):
        self.fixtures()
        self.release["assets"] = []
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.compare()
        self.fixtures()
        self.release["assets"].append(self.release["assets"][0])
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.compare()

    def test_zip_rejects_corruption_empty_misplaced_or_multiple_packages(self):
        cases = [b"not a zip", archive(), archive("eu.battle-conquest_1.2.0.wotmod"),
                 archive(package("2.4.1.0"), package("2.4.1.1")),
                 archive(package("2.4.1.1"), "other.wotmod"),
                 archive("mods/2.4.1.1/../../eu.battle-conquest_1.2.0.wotmod")]
        for invalid in cases:
            with self.subTest(invalid=invalid[:20]), self.assertRaises((ValueError, zipfile.BadZipFile)):
                watch.shipped_version(invalid)

    def test_unexpected_download_host_is_rejected(self):
        self.fixtures()
        self.release["assets"][0]["browser_download_url"] = "https://example.com/mod.zip"
        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.compare()

    def test_unavailable_zip_and_missing_stable_release_fail(self):
        self.fixtures()
        self.responses[URL] = TimeoutError("download failed")
        with self.assertRaises(TimeoutError):
            self.compare()
        def unavailable_release(arguments):
            raise RuntimeError("no stable release")
        with self.assertRaisesRegex(RuntimeError, "no stable release"):
            watch.compare(REPO, api=unavailable_release, fetcher=self.fetch)

    def test_dry_run_never_writes_even_when_outdated(self):
        self.fixtures()
        with patch.object(watch, "compare", return_value=self.compare()), \
                patch.object(watch, "sync_issue") as sync, \
                patch.object(watch, "write_summary"), \
                patch("sys.argv", ["client_watch.py", "--dry-run"]):
            watch.main()
        sync.assert_not_called()

    def test_normal_run_only_syncs_outdated_packages(self):
        for shipped, calls in (("2.4.1.0", 1), ("2.4.1.1", 0), ("2.4.1.2", 0)):
            self.fixtures(shipped=shipped)
            with patch.object(watch, "compare", return_value=self.compare()), \
                    patch.object(watch, "sync_issue") as sync, \
                    patch.object(watch, "write_summary"), \
                    patch("sys.argv", ["client_watch.py"]):
                watch.main()
            self.assertEqual(sync.call_count, calls)

    def test_comparison_failure_writes_error_summary_and_no_issue(self):
        with patch.object(watch, "compare", side_effect=ValueError("no source")), \
                patch.object(watch, "sync_issue") as sync, \
                patch.object(watch, "write_summary") as summary, \
                patch("sys.argv", ["client_watch.py"]):
            with self.assertRaises(ValueError):
                watch.main()
        sync.assert_not_called()
        self.assertIn("Échec", summary.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
