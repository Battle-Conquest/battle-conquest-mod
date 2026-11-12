"""Validate the complete installation ZIP before publication or WGMods submission."""
import argparse
import hashlib
import io
from pathlib import Path
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

GAMEFACE_VERSION = '1.2.2'
GAMEFACE_NAME = 'net.openwg.gameface_%s.wotmod' % GAMEFACE_VERSION
GAMEFACE_SHA256 = '2bb65f28663e3ab34b5a1102a1bbd1f6e17a65e1f6a898a8645c4ab732b50184'
LICENSE = 'LICENSE-openwg-gameface.txt'
CARD_LOADER = 'res/gui/gameface/mods/battle_conquest/Garage/Garage.js'
CARD_RESOURCES = (
    'res/scripts/client/gui/mods/mod_battle_conquest.pyc',
    CARD_LOADER,
    'res/gui/gameface/mods/battle_conquest/Garage/Garage.html',
    'res/gui/gen_resources/battle_conquest.json',
    'res/mods/configs/res_map/battle_conquest.json',
    'res/scripts/client/battle_conquest/web/hangar/garage.js',
    'res/scripts/client/battle_conquest/web/hangar/garage.css',
)
GAMEFACE_RESOURCES = (
    'res/scripts/client/openwg_gameface.pyc',
    'res/gui/gameface/js/index.js',
) + tuple('res/gui/gameface/mods/libs/%s.js' % name
          for name in ('media', 'common', 'views', 'model', 'debug', 'sound'))


def wotmod(data, label, identity, version, required):
    archive = zipfile.ZipFile(io.BytesIO(data))
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError('%s contains duplicate members' % label)
    for name in ('meta.xml',) + required:
        if name not in names or not archive.read(name):
            raise ValueError('%s is missing %s' % (label, name))
    meta = ET.fromstring(archive.read('meta.xml'))
    if meta.findtext('id') != identity or meta.findtext('version') != version:
        raise ValueError('%s metadata does not match its pinned identity/version' % label)
    if any(item.compress_type != zipfile.ZIP_STORED for item in archive.infolist()):
        raise ValueError('%s members must be stored, not deflated' % label)
    return archive


def check_bundle(bundle, package, game_version):
    """Check nested resources as well as the exact files installed into the game."""
    bundle, package = Path(bundle), Path(package)
    match = re.fullmatch(r'eu\.battle-conquest_(\d+\.\d+\.\d+)\.wotmod', package.name)
    if not match:
        raise ValueError('expected a versioned Battle-Conquest .wotmod')
    mod_path = 'mods/%s/%s' % (game_version, package.name)
    dependency_path = 'mods/%s/net.openwg/%s' % (game_version, GAMEFACE_NAME)
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        if len(names) != 3 or set(names) != {mod_path, dependency_path, LICENSE}:
            raise ValueError('installation ZIP must contain exactly the mod, pinned shared Gameface and licence')
        mod_data = archive.read(mod_path)
        if mod_data != package.read_bytes():
            raise ValueError('the ZIP and standalone Battle-Conquest .wotmod differ')
        dependency_data = archive.read(dependency_path)
        if b'MIT License' not in archive.read(LICENSE):
            raise ValueError('Gameface MIT licence is missing')
    with wotmod(mod_data, 'Battle-Conquest', 'eu.battle-conquest', match[1], CARD_RESOURCES) as mod, \
            wotmod(dependency_data, 'Gameface', 'net.openwg.gameface', GAMEFACE_VERSION,
                   GAMEFACE_RESOURCES) as dependency:
        # Resolve the real loader's relative imports against the combined resource tree.
        imports = re.findall(r'''\bfrom\s+['"]([^'"]+)['"]''', mod.read(CARD_LOADER).decode('utf-8'))
        for name in imports:
            target = posixpath.normpath(posixpath.join(posixpath.dirname(CARD_LOADER), name))
            if target not in mod.namelist() and target not in dependency.namelist():
                raise ValueError('unresolved garage-card import: %s' % name)
    if hashlib.sha256(dependency_data).hexdigest() != GAMEFACE_SHA256:
        raise ValueError('Gameface checksum differs from the pinned dependency')
    return hashlib.sha256(bundle.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('package', type=Path)
    parser.add_argument('--game-version', required=True)
    args = parser.parse_args()
    try:
        checksum = check_bundle(args.bundle, args.package, args.game_version)
    except (ValueError, OSError, zipfile.BadZipFile, ET.ParseError) as error:
        raise SystemExit('bundle check failed: %s' % error)
    print('bundle check passed: %s\nSHA-256: %s' % (args.bundle, checksum))


if __name__ == '__main__':
    main()
