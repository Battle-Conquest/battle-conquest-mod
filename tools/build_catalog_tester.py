"""Build the private catalogue tester, never a public release artifact.

Install instead of the standard mod, whose entry point this variant shares.
No collection code is added to src/: build_release.py remains unchanged.
"""
import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path

import build_release as release

TESTER = release.REPO / 'tester' / 'battle_conquest'


def stage_tester(stage: Path, version: str) -> Path:
    package = release.stage_package(stage, version)
    for source in TESTER.glob('*.py'):
        shutil.copy2(source, package / source.name)
    init = package / '__init__.py'
    text = init.read_text(encoding='utf-8')
    anchor = '        notices.install(_session, site, places, player, page)'
    if text.count(anchor) != 1:
        raise SystemExit('tester installation anchor missing or ambiguous')
    text = text.replace(anchor, anchor + '\n        from battle_conquest import catalog_tester\n'
                        '        catalog_tester.install(_session, player, places, page, VERSION)')
    init.write_text(text, encoding='utf-8')
    return package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--python27')
    parser.add_argument('--game-version', default=release.GAME_VERSION)
    args = parser.parse_args()
    if not release.VERSION.match(args.version) or not release.re.fullmatch(r'\d+(?:\.\d+){3}', args.game_version):
        raise SystemExit('expected --version x.y.z and --game-version a.b.c.d')
    python = release.python27(args.python27)
    release.DIST.mkdir(exist_ok=True)
    target = release.DIST / ('eu.battle-conquest-catalog-tester_%s.wotmod' % args.version)
    with tempfile.TemporaryDirectory() as scratch:
        stage = Path(scratch)
        stage_tester(stage, args.version)
        release.compile_all(python, stage)
        metadata = release.meta(args.version).replace('<id>eu.battle-conquest</id>', '<id>eu.battle-conquest.catalog-tester</id>')
        metadata = metadata.replace('<name>Battle-Conquest</name>', '<name>Battle-Conquest TESTER - private catalogue</name>')
        metadata = metadata.replace(release.DESCRIPTION, 'Private manual catalogue collection for one authorized tester. Not for public distribution.')
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_STORED) as archive:
            archive.writestr('meta.xml', metadata)
            for source, inside in release.members(stage):
                archive.write(source, inside)
    bundle = release.DIST / ('battle-conquest-catalog-tester_%s.zip' % args.version)
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(target, 'mods/%s/%s' % (args.game_version, target.name))
        archive.writestr('TESTER-README.txt',
            'PRIVATE TESTER BUILD - do not distribute.\n'
            'Remove the standard Battle-Conquest .wotmod before installing this variant.\n'
            'Use the existing account link. Collection starts only when you click Collect\n'
            'in mod settings or Collect and send catalogue in garage notifications.\n'
            'All uploads require an admin review and a server-authorized tester account.\n'
            'To return to the public mod: remove this tester .wotmod and reinstall the standard package.\n')
    print('Private tester only: %s\n%s' % (target, bundle))


if __name__ == '__main__':
    main()
