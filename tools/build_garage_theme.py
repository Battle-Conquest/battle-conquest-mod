"""Generate tiny native DDS surfaces with their actual display colours.

These are flat UI primitives, not externally sourced artwork. Regenerate after
changing the palette: python3 tools/build_garage_theme.py
"""
import runpy
import struct
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / 'res/gui/maps/battle_conquest/garage'


def dds(colour):
    # Uncompressed A8R8G8B8, 4x4, one mip. Native texture alpha supports the
    # transparent content windows too; no empty-texture fallback can turn white.
    fields = [124, 0x100f, 4, 4, 16, 0, 0] + [0] * 11
    fields += [32, 0x41, 0, 32, 0xff0000, 0xff00, 0xff, 0xff000000]
    fields += [0x1000, 0, 0, 0, 0]
    red, green, blue, alpha = colour
    return b'DDS ' + struct.pack('<31I', *fields) + bytes((blue, green, red, alpha)) * 16


def main():
    palette = runpy.run_path(str(REPO / 'src/battle_conquest/quest_garage_widgets.py'))['PALETTE']
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for role, colour in sorted(palette.items()):
        (OUTPUT / (role + '.dds')).write_bytes(dds(colour))
    print('Generated %s native DDS surfaces.' % len(palette))


if __name__ == '__main__':
    main()
