"""Name search, stale replies, hidden identifiers and editor write races."""
import copy
import os
import sys
import types

from checks.common import check
from checks.native_gui import native_gui
from checks.report_sender import _Session, _Response


class Transport(_Session):
    def __init__(self):
        _Session.__init__(self)
        self.later = []

    def callback(self, delay, func):
        self.later.append(func)

    def run(self):
        due, self.later = self.later, []
        for func in due:
            func()


def check_quest_garage_players():
    from battle_conquest.quest_garage import Garage
    from battle_conquest.quest_garage_view import Panel
    from battle_conquest.destinations import Destination, battles_url

    gui, roots, resolution, cursor, node, modes = native_gui()
    keys = types.ModuleType('Keys')
    keys.KEY_RETURN, keys.KEY_ESCAPE, keys.KEY_BACKSPACE, keys.KEY_DOWNARROW, keys.KEY_UPARROW = 13, 27, 8, 208, 200
    old = dict((key, sys.modules.get(key)) for key in ('GUI', 'Keys'))
    sys.modules.update(GUI=gui, Keys=keys)
    panel = Panel(None, store=os.path.join(os.getcwd(), 'player-search-panel.json'))
    try:
        panel.visible(True)
        transport = Transport()
        account = type('Account', (object,), {'account': '500883375'})()
        places = type('Places', (object,), {'current': Destination(battles_url(), secret='a' * 64, enabled=True, modes=['random'])})()
        garage = Garage(transport, account, places, panel, garage=lambda: True, platoon=lambda: [], now=lambda: 100.0)
        garage.key = garage.identity()
        data = {'schema': 1, 'config': {'version': 1, 'selection': '', 'mode': 'manual', 'manual_ids': [2]},
                'manual_players': [{'id': 2, 'username': 'Alice'}], 'selected': None, 'choices': [], 'players': []}
        garage.data = copy.deepcopy(data)
        panel.render(garage)
        panel.edit()
        picker = panel.picker
        check('saved players open by name rather than a visible numeric identifier',
              picker.selected_rows[0][1].text == 'Alice' and not picker.query and panel.editing == '2')
        def key(value, char=None):
            return type('Key', (object,), {'key': value, 'character': char,
                        'isKeyDown': lambda self: True, 'isMouseButton': lambda self: False})()
        picker.type(u'A')
        transport.run()
        check('one character never starts a player lookup', not transport.sent)
        picker.type(u'Al')
        picker.type(u'Ali')
        transport.run()
        check('typing is debounced and search carries only current account authentication',
              len(transport.sent) == 1 and '/quest-garage/players?' in transport.sent[0]['url']
              and 'q=Ali' in transport.sent[0]['url'] and transport.sent[0]['headers']['X-Mod-Secret'] == 'a' * 64)
        stale = transport.sent.pop()['answer']
        picker.type(u'Bo')
        transport.run()
        latest = transport.sent.pop()['answer']
        stale(_Response(200, {'results': [{'id': 3, 'username': 'Alina'}]}))
        check('a late previous query cannot populate the current dropdown', not picker.results)
        latest(_Response(200, {'results': [{'id': 2, 'username': 'Alice'}, {'id': 4, 'username': 'Bob'}]}))
        check('already selected names are excluded from suggestions', [row['username'] for row in picker.results] == ['Bob'])
        panel.handleKeyEvent(key(keys.KEY_DOWNARROW))
        panel.handleKeyEvent(key(keys.KEY_RETURN))
        check('arrows and Enter select a suggestion, keeping its ID internal',
              panel.editing == '2,4' and picker.entries[-1]['username'] == 'Bob' and not picker.query and not transport.sent)
        picker.results = [{'id': 5, 'username': 'Carol'}]
        panel.render(garage)
        row = picker.result_rows[0][0]
        pressed_action = next(action for target, action in panel.actions if target is row)
        picker.results = [{'id': 6, 'username': 'David'}]
        panel.render(garage)
        pressed_action()
        check('a dropdown refreshed between press and release cannot select a different player', panel.editing == '2,4')
        picker.pick(0)
        picker.results = [{'id': 5, 'username': 'Carol'}]
        picker.pick(0)
        check('four other players are the hard selection limit', len(picker.entries) == 4 and panel.editing == '2,4,6,5')
        panel.handleKeyEvent(key(50, u'More'))
        check('typing cannot add a fifth player', not picker.query and len(picker.entries) == 4)
        for width, height in ((1280, 720), (1920, 1080), (2560, 1440)):
            resolution[:] = (width, height)
            panel.render(garage)
            check('named selections and Save remain accessible at %sx%s' % (width, height),
                  all(not target.clipped() for target in picker.targets if target.visible)
                  and all(not button.clipped() for button in panel.buttons)
                  and panel.position[1] + panel.root.height <= height - 16)
        picker.remove(1)
        check('a selected player can be removed by its name row', panel.editing == '2,6,5')
        picker.clear()
        picker.results = [{'id': 5, 'username': 'Carol'}]
        picker.pick(0)
        panel.submit_edit()
        saved_request = transport.sent.pop()
        check('Save serializes selected IDs, never the typed username', saved_request['body']['manual_ids'] == [5])
        picker.type(u'Da')
        saved = copy.deepcopy(data)
        saved['config'].update(saved_request['body'], version=2)
        saved['manual_players'] = [{'id': 5, 'username': 'Carol'}]
        saved_request['answer'](_Response(200, saved))
        check('typing a name during save preserves the query and advances the draft version',
              panel.editing == '5' and picker.query == 'Da' and panel.edit_version == 2)
        transport.run()
        search = transport.sent.pop()
        search['answer'](_Response(503))
        check('a search failure preserves chosen names and exposes a retry message',
              picker.entries[0]['username'] == 'Carol' and 'unavailable' in picker.message)
        panel.submit_edit()
        check('unselected search text cannot be saved as an ID', not transport.sent and 'suggestions' in picker.message)
        picker.type(u'Bo')
        transport.run()
        delayed = transport.sent.pop()['answer']
        panel.cancel_edit()
        delayed(_Response(200, {'results': [{'id': 4, 'username': 'Bob'}]}))
        check('closing the editor discards its in-flight search', panel.editing is None and not picker.results)
        panel.edit()
        picker.type(u'Bo')
        transport.run()
        delayed = transport.sent.pop()['answer']
        account.account = '500999999'
        delayed(_Response(200, {'results': [{'id': 4, 'username': 'Bob'}]}))
        check('old-account replies cannot reopen suggestions', not picker.results)
        account.account = '500883375'
        picker.type(u'Bo')
        panel.close()
        transport.run()
        check('closing the native panel prevents pending search callbacks and frees its root', not transport.sent and not roots)
    finally:
        panel.close()
        for key, module in old.items():
            if module is None:
                del sys.modules[key]
            else:
                sys.modules[key] = module
