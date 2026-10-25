"""Fixed viewport, compact scores, mouse scrolling and clipped editor targets."""
import copy
import os
import shutil
import sys
import tempfile
import types

from checks.common import check
from checks.native_gui import native_gui
from checks.report_sender import _Session


def check_quest_garage_scroll():
    from battle_conquest.quest_garage import Garage
    from battle_conquest.quest_garage_input import Input
    from battle_conquest.quest_garage_view import Panel
    from battle_conquest.destinations import Destination, battles_url
    from battle_conquest.runtime.session import Session

    gui, roots, resolution, cursor, node, modes = native_gui()
    keys = types.ModuleType('Keys')
    keys.KEY_LEFTMOUSE, keys.KEY_RETURN, keys.KEY_ESCAPE = 256, 13, 27
    keys.KEY_UPARROW, keys.KEY_DOWNARROW, keys.KEY_BACKSPACE = 200, 208, 8
    previous = dict((name, sys.modules.get(name)) for name in ('GUI', 'Keys'))
    sys.modules.update(GUI=gui, Keys=keys)
    directory = tempfile.mkdtemp(prefix='bc-garage-scroll-')
    ownership = Session(958)
    panel = Panel(None, store=os.path.join(directory, 'panel.json'))
    try:
        panel.visible(True)
        in_garage = [True]
        account = type('Account', (object,), {'account': '500883375'})()
        places = type('Places', (object,), {'current': Destination(battles_url(), secret='a' * 64, enabled=True, modes=['random'])})()
        garage = Garage(_Session(), account, places, panel, garage=lambda: in_garage[0], ready=lambda: in_garage[0], platoon=lambda: [], now=lambda: 100.0)
        garage.key = garage.identity()
        score = {'available': True, 'battles': 2, 'totals': {'damage': 350, 'kills': 3}, 'updated_at': None}
        data = {'config': {'version': 1, 'selection': 'session:1', 'mode': 'manual', 'manual_ids': [2, 3, 4]},
                'manual_players': [{'id': index, 'username': 'Player %s' % index} for index in (2, 3, 4)],
                'selected': {'title': 'Shared objective'},
                'criteria': [{'criterion_type': 'damage', 'target_value': 1000}, {'criterion_type': 'kills', 'target_value': 5}],
                'period': {'start': '2026-10-25 00:00:00', 'end': '2026-10-26 00:00:00'},
                'choices': [{'title': 'Other quest %s' % i} for i in range(12)],
                'players': [{'username': 'Player %s' % i, 'participant': True,
                             'official': copy.deepcopy(score), 'estimate': copy.deepcopy(score)} for i in range(5)]}
        garage.data = copy.deepcopy(data)
        panel.render(garage)
        game = types.ModuleType('game')
        game.handleKeyEvent = lambda event: 'game-key'
        game.handleMouseEvent = lambda event: 'game-mouse'
        Input(ownership, panel, game).install()
        def event(x, y, down=True, dz=0, key=256):
            return type('Event', (object,), {'key': key, 'dz': dz,
                        'cursorPosition': (x * 2.0 / resolution[0] - 1, 1 - y * 2.0 / resolution[1]),
                        'isKeyDown': lambda self: down, 'isMouseButton': lambda self: key == 256})()
        def center(component):
            x, y = component.screen_position()
            return x + component.width / 2, y + component.height / 2
        def texts(component):
            result = [] if component.window else [component.text]
            for name, child in component.children:
                result.extend(texts(child))
            return result
        text = u'\n'.join(texts(panel.content.node))
        check('compact cards retain both score sources and remove duplicated quest lists and raw dates',
              'OFFICIAL' in text and 'MOD ESTIMATE' in text and '350 / 1 000' in text
              and 'Other quest' not in text and '2026-10-25' not in text and panel.content.height < 1500)
        for width, height in ((1024, 480), (1280, 720), (1920, 1080), (2560, 1440)):
            resolution[:] = width, height
            garage.data = copy.deepcopy(data)
            panel.render(garage)
            fixed_height = panel.root.height
            controls = [button.screen_position() for button in panel.buttons]
            check('five players fit a fixed visible viewport at %sx%s' % (width, height),
                  fixed_height == min(520, height - 32) and panel.overflow > 0 and panel.track.visible
                  and not any(button.clipped() for button in panel.buttons) and not panel.footer.clipped()
                  and panel.position[1] + fixed_height <= height - 16)
            garage.data['players'] = garage.data['players'][:1]
            panel.render(garage)
            check('fewer scores never shrink the window or move its controls',
                  panel.root.height == fixed_height and controls == [button.screen_position() for button in panel.buttons])
            garage.data = copy.deepcopy(data)
            panel.render(garage)
            x, y = center(panel.region)
            game.handleMouseEvent(event(x, y, dz=-120))
            check('wheel scrolling moves pixels while actions stay pinned',
                  panel.scroll > 0 and panel.content.node.position[1] == -panel.scroll
                  and controls == [button.screen_position() for button in panel.buttons])
            before, tree = panel.scroll, panel.content.node
            garage.data['server_time'] = '2026-10-25 01:00:01'
            panel.render(garage)
            check('clock-only refreshes preserve both scroll position and native card nodes',
                  panel.scroll == before and panel.content.node is tree)
            garage.data['players'][0]['official']['totals']['damage'] += 1
            panel.render(garage)
            check('updated scores also preserve the reading position', panel.scroll == before)
            x, y = center(panel.thumb)
            check('the scrollbar thumb is interactive through game input', game.handleKeyEvent(event(x, y)) is True and panel.scroller.drag is not None)
            game.handleMouseEvent(event(x + 200, height + 200))
            game.handleKeyEvent(event(x + 200, height + 200, down=False))
            last = panel.content.node.children[-1][1]
            last_bottom = last.screen_position()[1] + last.height
            viewport_bottom = panel.region.screen_position()[1] + panel.region.height
            check('dragging to the end reveals the final player and releases outside the window',
                  panel.scroll == panel.overflow and panel.scroller.drag is None and abs(last_bottom - viewport_bottom) < 0.001)
            x, y = center(panel.track)
            game.handleKeyEvent(event(x, y))
            game.handleKeyEvent(event(x, y, down=False))
            check('clicking the scrollbar track jumps within its bounds', 0 < panel.scroll < panel.overflow)
            before = panel.scroll
            panel.toggle()
            check('folding hides the scrollbar and reduces the window to its header',
                  panel.root.height == 64 and not panel.track.visible and panel.scroller.drag is None)
            panel.toggle()
            check('unfolding restores the fixed height and reading position', panel.root.height == fixed_height and panel.scroll == before)
            panel.edit()
            picker = panel.picker
            picker.query = u'Candidate'
            picker.results = [{'id': i, 'username': 'Candidate %s' % i} for i in range(10, 15)]
            panel.render(garage)
            check('a long player editor scrolls instead of growing the window', panel.root.height == fixed_height and panel.overflow > 0)
            # Starting with no active option, Up selects the last suggestion.
            panel.handleKeyEvent(event(1, 1, key=keys.KEY_UPARROW))
            target = picker.result_rows[-1][0]
            x, y = center(target)
            hidden = picker.remove_buttons[0][0]
            check('keyboard navigation reveals the active result',
                  panel.contains(panel.region, (x, y)) and panel.contains(target, (x, y)))
            panel.scroller.wheel(-120000)
            check('clipped editor rows cannot receive clicks', not panel.contains(hidden, center(hidden)))
            x, y = center(target)
            game.handleKeyEvent(event(x, y))
            game.handleKeyEvent(event(x, y, down=False))
            check('a scrolled suggestion selects its own player without losing chosen names',
                  [row['id'] for row in picker.entries] == [2, 3, 4, 14] and panel.root.height == fixed_height)
            panel.cancel_edit()
        check('wheel events outside the panel remain available to the game', game.handleMouseEvent(event(1, 1, dz=-120)) == 'game-mouse')
        x, y = center(panel.thumb)
        game.handleKeyEvent(event(x, y))
        in_garage[0] = False
        check('entering battle releases a scrollbar drag immediately',
              game.handleMouseEvent(event(x, y)) == 'game-mouse' and panel.scroller.drag is None)
        check('scrollbar and editor components keep the native GUI event bridge passive', not gui.handleKeyEvent(event(x, y)))
    finally:
        ownership.close()
        panel.close()
        shutil.rmtree(directory)
        for name, module in previous.items():
            if module is None:
                del sys.modules[name]
            else:
                sys.modules[name] = module
    check('scrolling teardown frees every GUI root', not roots)
