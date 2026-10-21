"""Exercise the real release editor boundary without building or publishing."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('release', ROOT / 'tools/release.py')
RELEASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELEASE)
EDITOR = str(Path(__file__).with_name('notes_editor.py'))


class NotesEditorTest(unittest.TestCase):
    def edit(self, notes=None, missing=False, unset=False):
        with tempfile.TemporaryDirectory(prefix='release notes ') as directory:
            source = Path(directory) / 'prepared notes.md'
            if not missing:
                source.write_text(notes or '', encoding='utf-8')
            with patch.dict(os.environ, {
                'EDITOR': EDITOR,
                'RELEASE_MOD_NOTES': '' if unset else str(source),
            }):
                return RELEASE.edited('## 1.2.3\n\n### Fixed\n\n- Original text.\n')

    def test_prepared_notes_replace_the_generated_text(self):
        notes = '## 1.2.3\n\n### Fixed\n\n- Fix players’ battle reports.'
        self.assertEqual(self.edit(notes), notes)

    def test_different_version_cancels_the_release(self):
        self.assertIsNone(self.edit('## 9.9.9\n\n- Wrong release.'))

    def test_empty_notes_cancel_the_release(self):
        self.assertIsNone(self.edit(''))

    def test_missing_notes_cancel_the_release(self):
        self.assertIsNone(self.edit(missing=True))

    def test_missing_configuration_cancels_the_release(self):
        self.assertIsNone(self.edit(unset=True))


if __name__ == '__main__':
    unittest.main()
