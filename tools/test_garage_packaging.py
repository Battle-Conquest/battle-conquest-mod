"""The complete installation retains the shared injector and reloadable assets."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import build_release
import install_dev


class GaragePackagingTest(unittest.TestCase):
    def test_complete_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'eu.battle-conquest_1.3.0.wotmod'
            package.write_bytes(b'package fixture')
            with patch.object(build_release, 'DIST', root):
                build_release.bundle(package, '1.3.0')
            with zipfile.ZipFile(root / 'battle-conquest-mod_1.3.0.zip') as archive:
                dependency = f'mods/{build_release.GAME_VERSION}/net.openwg/net.openwg.gameface_1.2.2.wotmod'
                self.assertEqual(archive.namelist(), [f'mods/{build_release.GAME_VERSION}/{package.name}',
                                                     dependency, 'LICENSE-openwg-gameface.txt'])
                self.assertEqual(hashlib.sha256(archive.read(dependency)).hexdigest(),
                                 '2bb65f28663e3ab34b5a1102a1bbd1f6e17a65e1f6a898a8645c4ab732b50184')
                self.assertIn(b'MIT License', archive.read('LICENSE-openwg-gameface.txt'))

    def test_dev_resources_in_wotmod_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compiled = root / 'mod_battle_conquest_dev.pyc'
            compiled.write_bytes(b'compiled fixture')
            target = root / 'dev.wotmod'
            install_dev.build_wotmod(compiled, target)
            with zipfile.ZipFile(target) as archive:
                for name in ('gui/gameface/mods/battle_conquest/Garage/Garage.js',
                             'gui/gen_resources/battle_conquest.json', 'mods/configs/res_map/battle_conquest.json'):
                    self.assertIn('res/' + name, archive.namelist())
                self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()))


if __name__ == '__main__':
    unittest.main()
