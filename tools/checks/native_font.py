# -*- coding: utf-8 -*-
"""Read the actual shipped font metrics without Pillow or a game client."""
import os
import re
import struct
import xml.etree.ElementTree as ET

from checks.common import REPO, check


def metrics(resource='battle_conquest/garage.font', root=None):
    root = root or os.path.join(REPO, 'res')
    tree = ET.parse(os.path.join(root, 'system', 'fonts', resource)).getroot()
    characters = []
    for row in tree.findall('creation/unicodeRange'):
        first, last = [int(part, 16) for part in re.match(r'U\+([0-9A-F]+)-U\+([0-9A-F]+)', row.text).groups()]
        characters.extend(range(first, last + 1))
    widths = tree.findtext('generated/widths')
    positions = tree.findtext('generated/uvs')
    result = {}
    for index, code in enumerate(characters):
        width = int(widths[index * 4:index * 4 + 4], 16)
        x = int(positions[index * 8:index * 8 + 4], 16)
        y = int(positions[index * 8 + 4:index * 8 + 8], 16) + 1
        result[code] = (x, y, width)
    return tree, result, int(tree.findtext('generated/height'))


def check_native_font():
    from battle_conquest.translations_fr import MESSAGES
    from battle_conquest.quest_garage_widgets import native_text
    tree, glyphs, height = metrics()
    check('font glyph order uses explicit Unicode ranges rather than the Windows ACP',
          tree.find('creation/startChar') is None and tree.find('creation/endChar') is None
          and len(tree.findall('creation/unicodeRange')) > 0)
    check('every printable French catalogue character has a Unicode glyph',
          all(ord(char) in glyphs for value in MESSAGES.values() for char in native_text(value) if not char.isspace()))
    check('NFC preserves French accents in Unicode and UTF-8 labels',
          native_text(u'Pe\u0301riode') == u'Période' and native_text(u'Période'.encode('utf-8')) == u'Période')
    image_path = os.path.join(REPO, 'res', tree.findtext('generated/map'))
    with open(image_path, 'rb') as handle:
        data = handle.read()
    header = struct.unpack('<31I', data[4:128])
    width, atlas_height = header[3], header[2]
    check('the font atlas has uncompressed 32-bit glyph pixels and complete bounds',
          data[:4] == 'DDS ' and header[19:22] == (0x41, 0, 32)
          and len(data) == 128 + width * atlas_height * 4
          and all(x >= 0 and y >= 0 and x + advance <= width and y + height <= atlas_height
                  for x, y, advance in glyphs.values()))
    def alpha(char):
        x, y, advance = glyphs[ord(char)]
        return ''.join(data[128 + ((y + line) * width + x) * 4 + 3:
                            128 + ((y + line) * width + x + advance) * 4:4] for line in range(height))
    check('French accented letters and ligatures contain actual visible glyph pixels',
          all(any(ord(pixel) for pixel in alpha(char)) for char in u'éèêëàâçîïôùûüÿœŒÉÀÇ'))
    check('e-acute is its own glyph, separate from plain e and Cyrillic short i',
          glyphs[ord(u'é')] != glyphs[ord(u'й')] and alpha(u'é') != alpha(u'e') and alpha(u'é') != alpha(u'й'))
    check('the DejaVu redistribution notice accompanies the generated atlas',
          os.path.isfile(os.path.join(os.path.dirname(image_path), 'LICENSE-DejaVu.txt')))
