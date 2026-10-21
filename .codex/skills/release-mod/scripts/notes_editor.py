#!/usr/bin/env python3
"""Supply prepared release notes to tools/release.py through EDITOR."""

import os
from pathlib import Path
import sys


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Expected the release editor buffer path')
    target = Path(sys.argv[1])
    expected_heading = target.read_text(encoding='utf-8').splitlines()[0]
    # release.py ignores the editor's exit code; an empty buffer cancels safely.
    target.write_text('', encoding='utf-8')
    source = os.environ.get('RELEASE_MOD_NOTES')
    if not source:
        raise SystemExit('RELEASE_MOD_NOTES must point to the prepared notes')
    try:
        notes = Path(source).read_text(encoding='utf-8').strip()
    except OSError as error:
        raise SystemExit(str(error))
    if not notes or notes.splitlines()[0] != expected_heading:
        raise SystemExit('Prepared notes must retain the generated version heading')
    target.write_text(notes + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
