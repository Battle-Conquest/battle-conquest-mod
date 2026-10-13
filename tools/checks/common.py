"""Shared by every check: the assertion and the bootstrap stub."""

import os


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STUB_TEMPLATE = os.path.join(REPO, 'dev', 'mod_battle_conquest_dev.py.in')


def render_stub(workdir, src_root):
    with open(STUB_TEMPLATE) as handle:
        text = handle.read().replace('__SRC_ROOT__', src_root.replace('\\', '/'))
    path = os.path.join(workdir, 'mod_battle_conquest_dev.py')
    with open(path, 'w') as handle:
        handle.write(text)
    return path


def check(label, condition):
    print('%-4s %s' % ('ok' if condition else 'FAIL', label))
    if not condition:
        raise SystemExit(1)
