"""Install the dev bootstrap into a World of Tanks client.

Renders dev/mod_battle_conquest_dev.py.in with this checkout's src/ path and
installs it, so the client loads a stub that watches src/ and reloads it in
place. Also copies res/ (the menu icon). Run once per client, or again after
moving the checkout.

    python tools/install_dev.py --game "C:/Games/World_of_Tanks_EU"

Two install shapes, because which one a client accepts is not a given:

  wotmod  a .wotmod package in mods/<version>/, the format every installed
          mod here uses, and the only one observed to load on a client
          running Aslain's script loader
  loose   a plain .py in res_mods/<version>/scripts/client/gui/mods/, which
          the loader's source says it accepts but which was not picked up

Both are installed by default; the game log says which one won. The stub is
static either way, so packaging costs nothing at edit time.

Runs on Python 3. The stub itself has to be Python 2.7, as the client is.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / 'dev' / 'mod_battle_conquest_dev.py.in'
SRC = REPO / 'src'
STUB_NAME = 'mod_battle_conquest_dev.py'
MOD_ID = 'eu.battle-conquest.dev'
MOD_VERSION = '0.1.0'

# The client's loader only picks up files named mod_*.py or mod_*.pyc, and
# only from this path inside a res_mods version folder or a .wotmod root.
MODS_SUBPATH = Path('scripts') / 'client' / 'gui' / 'mods'

RES = REPO / 'res'

PYTHON27_CANDIDATES = [
    Path(os.path.expanduser('~/scoop/apps/python27/current/python.exe')),
    Path('C:/Python27/python.exe'),
    Path(os.path.expanduser('~/.local/bin/python2.7')),
    Path('/usr/bin/python2.7'),
]


def find_version(game: Path) -> str:
    """Pick the version folder matching the installed client."""
    res_mods = game / 'res_mods'
    if not res_mods.is_dir():
        raise SystemExit(f'no res_mods folder in {game}')

    versions = sorted(p.name for p in res_mods.iterdir() if p.is_dir())
    if not versions:
        raise SystemExit(f'no version folder under {res_mods}')

    # version.xml is the authority; fall back to the only folder present.
    version_xml = game / 'version.xml'
    if version_xml.is_file():
        text = version_xml.read_text(encoding='utf-8', errors='replace')
        match = re.search(r'v\.([\d.]+)', text)
        if match and match.group(1) in versions:
            return match.group(1)

    if len(versions) == 1:
        return versions[0]
    raise SystemExit(
        f'cannot tell which version to use, pass --version: {versions}')


def find_python27(explicit: str | None) -> list[str]:
    """The command running Python 2.7, checked: a stub compiled by any other
    Python has the wrong magic and the client will not load it."""
    if explicit:
        if not Path(explicit).is_file():
            raise SystemExit(f'no such interpreter: {explicit}')
        candidates = [[explicit]]
    else:
        candidates = [[str(path)] for path in PYTHON27_CANDIDATES if path.is_file()]
        launcher = shutil.which('py')
        if launcher:
            candidates.append([launcher, '-2.7'])
    for command in candidates:
        result = subprocess.run(command + ['-c', 'import sys; print(sys.version_info[:2] == (2, 7))'],
                                capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip() == 'True':
            return command
    raise SystemExit('no Python 2.7 found, pass --python27')


def render_stub() -> str:
    # A raw string holds the path in the stub, so a trailing backslash would
    # escape the closing quote. Forward slashes work fine on Windows here.
    return TEMPLATE.read_text(encoding='utf-8').replace(
        '__SRC_ROOT__', SRC.as_posix())


def compile_stub(python27: list[str], stub: Path) -> Path:
    """Byte-compile with the client's own Python, so the magic matches."""
    pyc = stub.with_suffix('.pyc')
    if pyc.exists():
        pyc.unlink()
    result = subprocess.run(
        python27 + ['-c',
         'import py_compile, sys; py_compile.compile(sys.argv[1], '
         'cfile=sys.argv[2], doraise=True)',
         str(stub), str(pyc)],
        capture_output=True, text=True)
    if result.returncode != 0 or not pyc.is_file():
        raise SystemExit(f'compiling the stub failed:\n{result.stderr}')
    return pyc


def build_wotmod(pyc: Path, target: Path) -> None:
    """Package the compiled stub as a .wotmod.

    Stored, never deflated: the client rejected deflated members outright in
    2.3.1.3, before the entry point was even imported.
    """
    meta = (
        '<root>\n'
        f'    <id>{MOD_ID}</id>\n'
        f'    <version>{MOD_VERSION}</version>\n'
        '    <name>Battle-Conquest (dev bootstrap)</name>\n'
        '    <description>Loads the Battle-Conquest mod from a working copy and '
        'reloads it when its sources change.</description>\n'
        '</root>\n'
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_STORED) as archive:
        archive.writestr('meta.xml', meta)
        archive.write(pyc, str(Path('res') / MODS_SUBPATH / pyc.name).replace('\\', '/'))


def install_res(game: Path, version: str) -> int:
    """Copy res/ as it is: the menu icon, indexed when the client starts."""
    count = 0
    for source in sorted(p for p in RES.rglob('*') if p.is_file()):
        target = game / 'res_mods' / version / source.relative_to(RES)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', required=True, type=Path,
                        help='World of Tanks install directory')
    parser.add_argument('--version',
                        help='version folder to target (autodetected)')
    parser.add_argument('--python27',
                        help='Python 2.7 interpreter used to compile the stub')
    parser.add_argument('--shape', choices=('both', 'wotmod', 'loose'),
                        default='both', help='how to install (default: both)')
    args = parser.parse_args()

    game = args.game.resolve()
    if not game.is_dir():
        raise SystemExit(f'not a directory: {game}')

    version = args.version or find_version(game)
    stub_source = render_stub()
    print(f'sources  {SRC.as_posix()}')
    print(f'client   {version}')

    if args.shape in ('both', 'loose'):
        target_dir = game / 'res_mods' / version / MODS_SUBPATH
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / STUB_NAME).write_text(stub_source, encoding='utf-8')
        print(f'loose    {target_dir / STUB_NAME}')

        print(f'res      {install_res(game, version)} files -> res_mods/{version}')

    if args.shape in ('both', 'wotmod'):
        python27 = find_python27(args.python27)
        staging = REPO / 'build'
        staging.mkdir(exist_ok=True)
        stub = staging / STUB_NAME
        stub.write_text(stub_source, encoding='utf-8')
        pyc = compile_stub(python27, stub)
        package = game / 'mods' / version / f'{MOD_ID}_{MOD_VERSION}.wotmod'
        build_wotmod(pyc, package)
        print(f'wotmod   {package}')

    print('\nRestart the client once. After that, saving a file under src/ is enough.')


if __name__ == '__main__':
    sys.exit(main())
