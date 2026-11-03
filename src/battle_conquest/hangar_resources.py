"""Read reloadable UI resources from disk or from the release resource tree."""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def read(name):
    path = os.path.join(ROOT, *name.split('/'))
    if os.path.isfile(path):
        with open(path, 'rb') as handle:
            return handle.read().decode('utf-8')
    import ResMgr
    section = ResMgr.openSection('scripts/client/battle_conquest/' + name)
    if section is None:
        raise IOError('missing hangar resource: ' + name)
    return section.asBinary.decode('utf-8')
