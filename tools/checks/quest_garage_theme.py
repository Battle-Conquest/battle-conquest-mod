"""Validate baked native surfaces, legibility and structured score semantics."""
import os
import struct
import sys

from checks.common import REPO, check
from checks.native_gui import native_gui


def luminance(rgb):
    values = [value / 255.0 for value in rgb[:3]]
    values = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
    return sum(value * weight for value, weight in zip(values, (0.2126, 0.7152, 0.0722)))


def check_quest_garage_theme():
    from battle_conquest.quest_garage_widgets import PALETTE, TEXTURES
    from battle_conquest.quest_garage_content import Content, progress_ratio
    from battle_conquest.quest_garage_view import Panel
    check('numeric API strings produce bounded progress without inventing unknown values',
          progress_ratio('350', '1000') == 0.35 and progress_ratio(2000, 1000) == 1
          and progress_ratio(-10, 50) == 0 and progress_ratio(None, 50) is None
          and progress_ratio(10, 'unknown') is None and progress_ratio(10, 0) is None
          and progress_ratio(float('nan'), 50) is None and progress_ratio(10, float('inf')) is None)

    for role, colour in sorted(PALETTE.items()):
        with open(os.path.join(REPO, 'res', TEXTURES, role + '.dds'), 'rb') as handle:
            raw = handle.read()
        header = struct.unpack('<31I', raw[4:128])
        b, g, r, a = bytearray(raw[128:132])
        check('baked %s DDS contains its display colour and alpha without native tint' % role,
              raw[:4] == 'DDS ' and header[0] == 124 and header[2:5] == (4, 4, 16)
              and header[19:22] == (0x41, 0, 32) and header[22:26] == (0xff0000, 0xff00, 0xff, 0xff000000)
              and (r, g, b, a) == colour and raw[128:] == raw[128:132] * 16)
    combinations = {'text': ('panel', 'header', 'card', 'button', 'hover', 'primary', 'primary_hover', 'input'),
                    'muted': ('panel', 'header', 'card', 'disabled'), 'accent': ('header', 'card'),
                    'official': ('card',), 'estimate': ('card',), 'error': ('panel',)}
    for foreground, backgrounds in combinations.items():
        for background in backgrounds:
            contrast = (luminance(PALETTE[foreground]) + 0.05) / (luminance(PALETTE[background]) + 0.05)
            check('%s text on %s exceeds 4.5:1 contrast' % (foreground, background), contrast >= 4.5)

    gui, roots, resolution, cursor, node, modes = native_gui()
    previous = sys.modules.get('GUI')
    sys.modules['GUI'] = gui
    try:
        parent = gui.Window('')
        content = Content(parent)
        data = {'selected': {'title': 'A selected quest'}, 'choices': [],
                'criteria': [{'criterion_type': 'damage', 'target_value': 1000},
                             {'criterion_type': 'credits_net', 'target_value': 50}],
                'players': [{'username': 'Self', 'participant': True,
                             'official': {'available': True, 'battles': 2, 'totals': {'damage': 350, 'credits_net': None},
                                          'known_totals': {'credits_net': -10}, 'incomplete': True},
                             'estimate': {'available': True, 'battles': 4, 'totals': {}, 'comparable': False}},
                            {'username': 'Followed', 'participant': False, 'official': None, 'estimate': None}]}
        content.render(data, 596)
        def descendants(component):
            for name, child in component.children:
                yield child
                for nested in descendants(child):
                    yield nested
        nodes = list(descendants(content.node))
        texts = [component.text for component in nodes if not component.window]
        text = u'\n'.join(texts)
        check('the selected quest, player names, official values and estimates have separate cards and labels',
              'A selected quest' in text and 'Self' in text and 'OFFICIAL' in text and 'MOD ESTIMATE' in text
              and len(content.node.children) == 3)
        check('unknown, partial, incomparable and followed-player states keep their meaning',
              '-10 + ? / 50' in text and 'Not comparable' in text and 'Incomplete data' in text
              and 'Followed only - no rewards' in text and 'No results for this period.' in text)
        bars = [component for component in nodes if component.window and component.textureName.endswith('/official.dds')]
        check('only a known comparable value creates a progress fill, with the correct bounded ratio',
              len(bars) == 1 and abs(bars[0].width / bars[0].parent.width - 0.35) < 0.00001)
        check('all measured card labels and bars fit their native parent windows', not any(component.clipped() for component in nodes))
        before = content.node
        check('a stable snapshot reuses its native nodes', not content.render(data, 596) and content.node is before)
        data['selected']['title'] = '<script> A very long untrusted title ' * 12
        content.render(data, 596)
        check('a changed snapshot replaces rather than accumulates its native tree', len(parent.children) == 1 and content.node is not before)
        check('untrusted labels keep formatting disabled', all(not component.colourFormatting for component in descendants(content.node) if not component.window))
        data['selected']['status'] = 'receiving'
        data['criteria'][0]['criterion_type'] = 'damage_dealt'
        data['battle_feedback'] = {'stage': 'sending', 'source': 'local', 'mode': 'other', 'totals': {'damage_dealt': 28806}}
        content.render(data, 596)
        provisional = u'\n'.join(component.text for component in descendants(content.node) if not component.window)
        check('one provisional card displays local damage and closed state without a success verdict',
              '28 806' in provisional and 'LAST BATTLE - provisional' in provisional
              and 'Sending to Battle-Conquest' in provisional and 'Closed - receiving final results' in provisional
              and len(content.node.children) == 4)
        data['battle_feedback'] = {'stage': 'received', 'source': 'site', 'mode': 'other', 'totals': {'damage_dealt': 28000}}
        content.render(data, 596)
        confirmed = u'\n'.join(component.text for component in descendants(content.node) if not component.window)
        check('site data replaces the provisional card without accumulating battle history',
              '28 000' in confirmed and '28 806' not in confirmed and 'LAST BATTLE - Battle-Conquest' in confirmed
              and len(content.node.children) == 4)
        check('new status messages wrap inside their native cards', not any(component.clipped() for component in descendants(content.node)))
        content.clear()
        check('clearing an account snapshot removes its player cards', not parent.children and content.node is None)
        garage = type('Garage', (object,), {'display_data': lambda self: self.data,
            'data': data, 'error': None, 'offline': False, 'conflict': False, 'busy': None,
            'now': lambda self: 100.0, 'next_quest': lambda self: None, 'toggle_mode': lambda self: None})()
        data['config'] = {'version': 1, 'selection': '', 'mode': 'manual', 'manual_ids': []}
        for width, height in ((1280, 720), (1920, 1080), (2560, 1440)):
            resolution[:] = (width, height)
            panel = Panel(None, store=os.path.join(os.getcwd(), 'theme-panel.json'))
            panel.visible(True)
            panel.render(garage)
            check('structured cards retain accessible controls and status in %sx%s' % (width, height),
                  panel.cards_shown and panel.content.height > 0
                  and all(not button.clipped() for button in panel.buttons)
                  and panel.root.position[1] + panel.root.height <= height - 16
                  and not panel.footer.clipped())
            panel.close()
        check('structured-card teardown leaves no GUI roots', not roots)
    finally:
        if previous is None:
            del sys.modules['GUI']
        else:
            sys.modules['GUI'] = previous
