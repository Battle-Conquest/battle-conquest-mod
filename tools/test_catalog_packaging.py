"""Verify that normal releases cannot contain private collection code."""
import tempfile
import unittest
from pathlib import Path

import build_release
import build_catalog_tester


class CataloguePackagingTest(unittest.TestCase):
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
