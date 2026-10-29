"""Verify that normal releases cannot contain private collection code."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_release
import build_catalog_tester


class CataloguePackagingTest(unittest.TestCase):
    def test_wrong_interpreter_preserves_existing_artifacts(self):
        with tempfile.TemporaryDirectory() as scratch:
            dist = Path(scratch)
            package = dist / 'eu.battle-conquest-catalog-tester_1.2.0.wotmod'
            bundle = dist / 'battle-conquest-catalog-tester_1.2.0.zip'
            for target in (package, bundle):
                target.write_bytes(b'previous working artifact')
            argv = ['build_catalog_tester.py', '--version', '1.2.0', '--python27', sys.executable]
            with patch.object(build_catalog_tester.release, 'DIST', dist), patch.object(sys, 'argv', argv):
                with self.assertRaises(SystemExit):
                    build_catalog_tester.main()
            for target in (package, bundle):
                self.assertEqual(target.read_bytes(), b'previous working artifact')

    def test_private_code_only_in_explicit_tester_build(self):
        with tempfile.TemporaryDirectory() as normal, tempfile.TemporaryDirectory() as tester:
            public_package = build_release.stage_package(Path(normal), '1.2.0')
            private_package = build_catalog_tester.stage_tester(Path(tester), '1.2.0')
            self.assertFalse(list(public_package.glob('catalog_*.py')))
            self.assertNotIn('catalog_tester', (public_package / '__init__.py').read_text())
            self.assertEqual(len(list(private_package.glob('catalog_*.py'))), 3)
            self.assertIn('catalog_tester.install(', (private_package / '__init__.py').read_text())
            for source in build_release.SRC.rglob('*.py'):
                relative = source.relative_to(build_release.SRC)
                if relative.name != '__init__.py' and source.name not in build_release.EXCLUDED:
                    self.assertEqual(source.read_bytes(), (public_package / relative).read_bytes())


if __name__ == '__main__':
    unittest.main()
