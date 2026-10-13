"""Load a built .wotmod the way the client does, outside the game.

    python2.7 tools/release_check.py dist/eu.battle-conquest_1.0.0.wotmod

The selftest drives the mod from its sources. A release is something else:
compiled modules only, imported from scripts/client/. This extracts the
package, imports it from its .pyc files with the fake client of tools/checks,
and checks that the entry point starts and stops the mod, and that nothing in
it is named after the mod it grew out of -- the two have to install side by
side.

Python 2.7, same as the client.
"""
import imp
import logging
import os
import shutil
import sys
import tempfile
import zipfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

from checks.client import install_fake_client
from checks.common import check
from checks.engine import FakeBigWorld


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    logging.basicConfig(level=logging.INFO, format='       %(name)s: %(message)s')
    workdir = tempfile.mkdtemp(prefix='battle-conquest-release-')
    try:
        with zipfile.ZipFile(sys.argv[1]) as archive:
            names = archive.namelist()
            stored = all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist())
            archive.extractall(workdir)
        res = os.path.join(workdir, 'res')
        check('no source file ships', not [n for n in names if n.endswith('.py')])
        # The client rejected deflated members outright in 2.3.1.3.
        check('every member is stored, not deflated', stored)
        check('the entry point is where the client loads mods from',
              'res/scripts/client/gui/mods/mod_battle_conquest.pyc' in names)
        check('the menu icon ships', 'res/gui/maps/icons/battle_conquest/icon.png' in names)
        check('nothing is named after unicum.gg-mod, so the two install side by side',
              not [n for n in names if 'unicum' in n.lower()])

        game = os.path.join(workdir, 'game')
        os.makedirs(game)
        os.chdir(game)
        install_fake_client(FakeBigWorld())
        sys.path.insert(0, os.path.join(res, 'scripts', 'client'))

        entry = imp.load_compiled('mod_battle_conquest',
                                  os.path.join(res, 'scripts', 'client', 'gui', 'mods', 'mod_battle_conquest.pyc'))
        entry.init()
        import battle_conquest
        check('the package is the compiled one from the package',
              os.path.dirname(battle_conquest.__file__) == os.path.join(res, 'scripts', 'client', 'battle_conquest'))
        check('the entry point started the mod', entry._loaded is battle_conquest and battle_conquest._session is not None)
        check('the entry point carries the released version', entry.__version__ == battle_conquest.VERSION)

        entry.fini()
        check('the entry point stops the mod', entry._loaded is None)
    finally:
        os.chdir(TOOLS)
        shutil.rmtree(workdir, ignore_errors=True)
    # check() exits on the first failure.
    print('\nrelease check passed')


if __name__ == '__main__':
    main()
