"""The complete installation retains the shared injector and reloadable assets."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import build_release
import install_dev
from bundle_check import (CARD_LOADER, CARD_RESOURCES, GAMEFACE_NAME, check_bundle)


def write_package(path, version):
    """A structurally complete package; release_check covers real compiled Python."""
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as archive:
        archive.writestr('meta.xml', build_release.meta(version))
        for name in CARD_RESOURCES:
            content = (build_release.RES / CARD_LOADER.removeprefix('res/')).read_bytes() \
                if name == CARD_LOADER else b'packaged resource fixture'
            archive.writestr(name, content)


def write_bundle(root, version='1.2.2'):
    package = root / ('eu.battle-conquest_%s.wotmod' % version)
    write_package(package, version)
    with patch.object(build_release, 'DIST', root):
        build_release.bundle(package, version)
    return package, root / ('battle-conquest-mod_%s.zip' % version)


class GaragePackagingTest(unittest.TestCase):
    def test_complete_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package, bundle = write_bundle(root, '1.3.0')
            with zipfile.ZipFile(bundle) as archive:
                dependency = f'mods/{build_release.GAME_VERSION}/net.openwg/net.openwg.gameface_1.2.2.wotmod'
                self.assertEqual(archive.namelist(), [f'mods/{build_release.GAME_VERSION}/{package.name}',
                                                     dependency, 'LICENSE-openwg-gameface.txt'])
                self.assertEqual(hashlib.sha256(archive.read(dependency)).hexdigest(),
                                 '2bb65f28663e3ab34b5a1102a1bbd1f6e17a65e1f6a898a8645c4ab732b50184')
                self.assertIn(b'MIT License', archive.read('LICENSE-openwg-gameface.txt'))
            self.assertEqual(check_bundle(bundle, package, build_release.GAME_VERSION),
                             hashlib.sha256(bundle.read_bytes()).hexdigest())

    def test_incomplete_or_changed_installations_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            package, bundle = write_bundle(Path(directory))
            original = bundle.read_bytes()
            with zipfile.ZipFile(bundle) as archive:
                contents = {name: archive.read(name) for name in archive.namelist()}
            dependency = next(name for name in contents if name.endswith(GAMEFACE_NAME))
            mod = next(name for name in contents if name.endswith(package.name))
            cases = [
                ({name: data for name, data in contents.items() if name != dependency}, 'exactly'),
                ({**contents, 'mods/wrong/net.openwg/' + GAMEFACE_NAME: contents[dependency]}, 'exactly'),
                ({**contents, mod: b'another Battle-Conquest package'}, 'differ'),
                ({**contents, 'LICENSE-openwg-gameface.txt': b''}, 'licence'),
            ]
            for members, message in cases:
                with self.subTest(message=message):
                    with zipfile.ZipFile(bundle, 'w') as archive:
                        for name, data in members.items():
                            archive.writestr(name, data)
                    with self.assertRaisesRegex(ValueError, message):
                        check_bundle(bundle, package, build_release.GAME_VERSION)
            bundle.write_bytes(original)
            package.write_bytes(b'a stale standalone package')
            with self.assertRaisesRegex(ValueError, 'differ'):
                check_bundle(bundle, package, build_release.GAME_VERSION)

    def test_missing_python_javascript_or_wrong_gameface_version_blocks_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'eu.battle-conquest_1.2.2.wotmod'
            write_package(package, '1.2.2')
            vendor = root / 'vendor'
            vendor.mkdir()
            source = build_release.GAMEFACE
            (vendor / 'LICENSE-gameface').write_bytes((source / 'LICENSE-gameface').read_bytes())
            with zipfile.ZipFile(source / GAMEFACE_NAME) as archive:
                contents = {name: archive.read(name) for name in archive.namelist()}
            for missing in ('res/scripts/client/openwg_gameface.pyc',
                            'res/gui/gameface/mods/libs/model.js', 'res/gui/gameface/js/index.js', None):
                with self.subTest(missing=missing):
                    with zipfile.ZipFile(vendor / GAMEFACE_NAME, 'w', zipfile.ZIP_STORED) as archive:
                        for name, data in contents.items():
                            if name == missing:
                                continue
                            if missing is None and name == 'meta.xml':
                                data = data.replace(b'<version>1.2.2</version>', b'<version>9.9.9</version>')
                            archive.writestr(name, data)
                    with patch.object(build_release, 'DIST', root), \
                            patch.object(build_release, 'GAMEFACE', vendor), \
                            self.assertRaisesRegex(ValueError, 'missing|version'):
                        build_release.bundle(package, '1.2.2')
            (vendor / GAMEFACE_NAME).write_bytes((source / GAMEFACE_NAME).read_bytes() + b'altered')
            with patch.object(build_release, 'DIST', root), patch.object(build_release, 'GAMEFACE', vendor), \
                    self.assertRaisesRegex(ValueError, 'checksum'):
                build_release.bundle(package, '1.2.2')

    def test_loader_imports_must_resolve_in_the_complete_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package, bundle = write_bundle(root)
            with zipfile.ZipFile(package) as archive:
                contents = {name: archive.read(name) for name in archive.namelist()}
            contents[CARD_LOADER] += b"\nimport { Missing } from '../../libs/missing.js';"
            with zipfile.ZipFile(package, 'w', zipfile.ZIP_STORED) as archive:
                for name, data in contents.items():
                    archive.writestr(name, data)
            with patch.object(build_release, 'DIST', root), self.assertRaisesRegex(ValueError, 'unresolved'):
                build_release.bundle(package, '1.2.2')

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
