"""Drive real panel actions through the session-owned game input hooks."""
import os
import shutil
import sys
import tempfile
import types

from checks.common import check
from checks.native_gui import native_gui
from checks.report_sender import _Session, _Response


def check_quest_garage_input():
    from battle_conquest.quest_garage import Garage
    from battle_conquest.quest_garage_input import Input
    from battle_conquest.quest_garage_view import Panel
    from battle_conquest.destinations import Destination, battles_url
    from battle_conquest.runtime.session import Session

    gui, roots, resolution, cursor, node, modes = native_gui()
    keys = types.ModuleType('Keys')
    keys.KEY_LEFTMOUSE, keys.KEY_RETURN, keys.KEY_ESCAPE, keys.KEY_BACKSPACE = 256, 13, 27, 8
    previous = dict((name, sys.modules.get(name)) for name in ('GUI', 'Keys'))
    sys.modules.update(GUI=gui, Keys=keys)
    directory = tempfile.mkdtemp(prefix='bc-garage-input-')
    ownership = Session(958)
    panel = Panel(None, store=os.path.join(directory, 'panel.json'))
    try:
        panel.visible(True)
        in_garage = [True]
        transport = _Session()
        account = type('Account', (object,), {'account': '500883375'})()
        places = type('Places', (object,), {'current': Destination(battles_url(), enabled=True, modes=['random'], secret='a' * 64)})()
        garage = Garage(transport, account, places, panel, garage=lambda: in_garage[0], platoon=lambda: [], now=lambda: 100.0)
        garage.key = garage.identity()
        garage.data = {'schema': 1, 'config': {'version': 1, 'selection': '', 'mode': 'manual', 'manual_ids': [2]},
                       'choices': [], 'selected': None, 'players': []}
        panel.render(garage)
        game = types.ModuleType('game')
        delegated = []
        def original_key(event):
            delegated.append(('key', event))
            gui.handleKeyEvent(event)
            return 'game-key'
        def original_mouse(event):
            delegated.append(('mouse', event))
            gui.handleMouseEvent(event)
            return 'game-mouse'
        game.handleKeyEvent, game.handleMouseEvent = original_key, original_mouse
        router = Input(ownership, panel, game)
        router.install()

        def event(x, y, down=True, key=256, dz=0, character=None):
            return type('Event', (object,), {
                'key': key, 'dz': dz, 'character': character,
                'cursorPosition': (x * 2.0 / resolution[0] - 1, 1 - y * 2.0 / resolution[1]),
                'isKeyDown': lambda self: down, 'isMouseButton': lambda self: key == 256})()

        def center(component):
            x, y = component.screen_position()
            return x + component.width / 2, y + component.height / 2

        def click(component, release=None):
            x, y = center(component)
            game.handleKeyEvent(event(x, y))
            rx, ry = release or (x, y)
            return game.handleKeyEvent(event(rx, ry, False))

        start = panel.position
        x, y = start[0] + 100, start[1] + 20
        safe = True
        try:
            gui.handleKeyEvent(event(x, y))
        except TypeError:
            safe = False
        check('native GUI dispatch cannot enter the unsupported KeyEvent conversion bridge', safe)
        check('left mouse down on the header starts dragging through game input',
              game.handleKeyEvent(event(x, y)) is True and panel.drag is not None)
        game.handleMouseEvent(event(x + 700, y + 200))
        check('dragging continues after the cursor leaves the original window',
              abs(panel.position[0] - start[0] - 700) < 0.001 and abs(panel.position[1] - start[1] - 200) < 0.001)
        game.handleKeyEvent(event(x + 700, y + 200, False))
        restored = Panel(None, store=panel.store)
        check('releasing the mouse ends dragging and persists its pixel position',
              panel.drag is None and restored.position == panel.position)
        check('garage mouse and keyboard commands outside the window are delegated',
              game.handleKeyEvent(event(1, 1)) == 'game-key' and game.handleMouseEvent(event(1, 1)) == 'game-mouse'
              and game.handleKeyEvent(event(1, 1, key=65, character='a')) == 'game-key')
        check('the card uses its own baked dark surfaces and four visible action rectangles',
              panel.root.textureName.endswith('/panel.dds') and panel.header.textureName.endswith('/header.dds')
              and all(button.visible and button.width > 100 and button.height >= 36 for button in panel.buttons))
        click(panel.fold_button)
        check('the Collapse button keeps only the header visible',
              panel.collapsed and panel.root.height == 64 and not panel.region.visible and not any(b.visible for b in panel.buttons))
        click(panel.fold_button)
        check('Expand restores the content and controls', not panel.collapsed and panel.region.visible)
        x, y = center(panel.buttons[0])
        game.handleMouseEvent(event(x, y))
        check('the primary action has a baked hover state independent of vertex tint', panel.buttons[0].textureName.endswith('/primary_hover.dds'))
        game.handleMouseEvent(event(1, 1))
        check('leaving an action restores its normal surface', panel.buttons[0].textureName.endswith('/primary.dds'))
        click(panel.buttons[2], release=(1, 1))
        check('releasing a button outside it cancels the click', panel.editing is None)
        click(panel.buttons[2])
        check('Edit players opens a distinct input field and Save/Cancel controls',
              panel.editing == u'2' and panel.input_box.visible
              and [label.text for label in panel.button_labels[:2]] == [u'Save', u'Cancel'])
        click(panel.buttons[2])
        game.handleKeyEvent(event(1, 1, key=52, character=u'4'))
        check('Clear followed by keyboard input updates the player draft', panel.editing == u'4')
        click(panel.buttons[0])
        check('Save sends the draft once and disables writes while the answer is pending',
              len(transport.sent) == 1 and transport.sent[0]['body']['manual_ids'] == [4]
              and id(panel.buttons[0]) in panel.disabled)
        click(panel.buttons[0])
        check('clicking a disabled Save cannot duplicate the request', len(transport.sent) == 1)
        transport.sent.pop(0)['answer'](_Response(503))
        check('a failed Save preserves the visible draft and exposes the offline state',
              panel.editing == u'4' and panel.input_box.visible and 'Offline' in panel.subtitle.text)
        click(panel.buttons[1])
        check('Cancel closes the editor without saving', panel.editing is None and not transport.sent)
        click(panel.buttons[2])
        game.handleKeyEvent(event(1, 1, key=27))
        check('Escape closes the editor and its key release cannot open the game menu',
              panel.editing is None and game.handleKeyEvent(event(1, 1, down=False, key=27)) is True)
        score = {'available': True, 'battles': 12, 'totals': {'damage': 350}, 'updated_at': None}
        garage.data['criteria'] = [{'criterion_type': 'damage', 'target_value': 1000}] * 10
        garage.data['players'] = [{'username': 'Test player %s' % i, 'participant': True, 'official': score, 'estimate': score} for i in range(5)]
        panel.render(garage)
        x, y = center(panel.region)
        game.handleMouseEvent(event(x, y, dz=-120))
        check('long content scrolls inside its region while all action buttons remain accessible',
              panel.scroll > 0 and panel.track.visible and all(not button.clipped() for button in panel.buttons)
              and panel.root.position[1] + panel.root.height <= resolution[1] - 16)
        game.handleMouseEvent(event(x, y, dz=-120000))
        check('scrolling is bounded at the final row', panel.scroll == panel.overflow)
        check('wheel events outside the card continue to reach the game', game.handleMouseEvent(event(1, 1, dz=-120)) == 'game-mouse')
        x, y = panel.position[0] + 100, panel.position[1] + 20
        game.handleKeyEvent(event(x, y))
        in_garage[0] = False
        check('battle immediately stops a drag and delegates input even before the next visibility tick',
              game.handleMouseEvent(event(x + 50, y + 50)) == 'game-mouse' and panel.drag is None
              and game.handleKeyEvent(event(x, y, False)) == 'game-key')
        check('native GUI dispatch also stays passive in battle before the visibility tick', not gui.handleKeyEvent(event(x, y)))
        in_garage[0] = True
        panel.visible(False)
        check('a hidden panel never captures game commands', game.handleKeyEvent(event(x, y)) == 'game-key')
        ownership.close()
        panel.close()
        check('session teardown restores game input handlers by identity and releases the native root',
              game.handleKeyEvent is original_key and game.handleMouseEvent is original_mouse and not roots and not router.owned_keys)
    finally:
        ownership.close()
        panel.close()
        for name, module in previous.items():
            if module is None:
                del sys.modules[name]
            else:
                sys.modules[name] = module
        shutil.rmtree(directory)
