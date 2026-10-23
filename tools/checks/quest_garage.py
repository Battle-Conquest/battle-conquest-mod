"""Garage polling, account isolation, conflicts and native panel teardown."""
import copy
import os
import sys
import tempfile
import types

from checks.common import check
from checks.report_sender import _Session, _Response


def check_quest_garage():
    from battle_conquest.quest_garage import Garage
    from battle_conquest.quest_garage_view import lines
    from battle_conquest.destinations import Destination, battles_url

    class View(object):
        def __init__(self):
            self.shown = False
            self.resets = 0
        def reset(self):
            self.resets += 1
        def visible(self, state):
            self.shown = state
        def render(self, garage):
            pass
        def close(self):
            pass

    session = _Session()
    view = View()
    account = type('Account', (object,), {'account': '500883375'})()
    destination = Destination(battles_url(), enabled=True, modes=['random'], secret='a' * 64)
    places = type('Places', (object,), {'current': destination})()
    clock = [100.0]
    in_garage = [True]
    garage = Garage(session, account, places, view, garage=lambda: in_garage[0],
                    platoon=lambda: ['500883375', '2', '3', '4', '5', '6'], now=lambda: clock[0])
    data = {'schema': 1, 'config': {'version': 1, 'selection': 'individual:1', 'mode': 'platoon', 'manual_ids': []},
            'choices': [{'key': 'individual:1', 'title': 'Quest', 'status': 'active'}], 'selected': {'title': 'Quest'},
            'players': [{'username': 'Self', 'participant': True, 'official': {'available': False, 'updated_at': None}}]}
    garage.tick()
    check('panel waits for an available server before appearing', not view.shown)
    check('garage uses the secret and bounds platoon to four other accounts',
          session.sent[0]['headers']['X-Mod-Secret'] == 'a' * 64 and session.sent[0]['url'].endswith('&platoon=2,3,4,5'))
    session.sent.pop(0)['answer'](_Response(200, copy.deepcopy(data)))
    garage.tick()
    check('native panel shown with no optional menu API', view.shown)
    check('no second poll before fifteen seconds', not session.sent)
    clock[0] += 15
    garage.tick()
    session.sent.pop(0)['answer'](_Response(503))
    check('offline keeps the last values and says so', garage.data == data and garage.offline and 'Offline' in lines(garage)[-1])
    garage.save(mode='manual', manual_ids=[2, 3])
    request = session.sent.pop(0)
    check('write includes the observed version', request['body']['version'] == 1 and request['method'] == 'POST')
    request['answer'](_Response(409, {'error': 'conflict'}))
    garage.save(mode='manual')
    check('conflicting writes stay blocked until explicit reload', garage.conflict and not session.sent)
    garage.poll(force=True)
    newer = copy.deepcopy(data)
    newer['config']['version'] = 2
    session.sent.pop(0)['answer'](_Response(200, newer))
    check('a background poll cannot silently resolve conflict', garage.data['config']['version'] == 1 and garage.conflict)
    garage.reload()
    session.sent.pop(0)['answer'](_Response(200, newer))
    check('explicit reload accepts the current server version', garage.data['config']['version'] == 2 and not garage.conflict)
    garage.poll(force=True)
    stale = session.sent.pop(0)['answer']
    account.account = '500999999'
    garage.tick()
    check('account switch clears the previous configuration and values', garage.data is None and view.resets == 2)
    stale(_Response(200, data))
    check('late response cannot restore previous account', garage.data is None)
    session.sent.pop(0)['answer'](_Response(200, newer))
    in_garage[0] = False
    clock[0] += 15
    garage.tick()
    garage.save(mode='manual')
    check('battle hides panel and prevents reads and writes', not view.shown and not session.sent)
    in_garage[0] = True
    garage.tick()
    check('returning to garage restores panel and retained values', view.shown and garage.data == newer)
    session.sent.pop(0)['answer'](_Response(200, newer))
    destination.secret = 'b' * 64
    garage.tick()
    check('link changes also clear the old account data', garage.data is None)
    session.sent.pop(0)['answer'](_Response(404, {'error': 'unavailable'}))
    garage.tick()
    check('disabled server feature keeps the native panel hidden', not view.shown and garage.unavailable)
    garage.poll(force=True)
    session.sent.pop(0)['answer'](_Response(200, newer))
    garage.tick()
    check('enabling the combined server release restores the panel', view.shown and not garage.unavailable)


def check_quest_garage_panel():
    from battle_conquest.quest_garage_view import Panel

    class Node(object):
        def __init__(self, text):
            self.text = text
            self.position = (0, 0, 0)
            self.children = []
            self.height = 200
            self.visible = True
        def addChild(self, child, name):
            self.children.append((name, child))

    module = types.ModuleType('GUI')
    roots = []
    module.Text = Node
    module.addRoot = roots.append
    module.delRoot = roots.remove
    module.mcursor = lambda: type('Cursor', (object,), {'position': (0.3, 0.4)})()
    previous = sys.modules.get('GUI')
    sys.modules['GUI'] = module
    directory = tempfile.mkdtemp(prefix='bc-garage-test-')
    store = os.path.join(directory, 'panel.json')
    try:
        panel = Panel(None, store=store)
        panel.visible(True)
        check('native panel builds without any third party API', len(roots) == 1 and len(panel.buttons) == 4)
        panel.handleMouseClickEvent()
        panel.handleDragStartEvent(panel.root, (0.0, 0.0))
        panel.handleDragStopEvent()
        position = panel.position
        panel.visible(False)
        check('battle hides all panel children through their root', not panel.root.visible)
        panel.visible(True)
        check('garage preserves folding and position', panel.collapsed and panel.position == position)
        restored = Panel(None, store=store)
        check('reloading preserves saved panel placement', restored.collapsed and restored.position == position)
        panel.close()
        check('stopping releases native GUI root', not roots)
    finally:
        if previous is None:
            del sys.modules['GUI']
        else:
            sys.modules['GUI'] = previous
        import shutil
        shutil.rmtree(directory)


def check_quest_garage_platoon():
    from battle_conquest.quest_garage import platoon_accounts
    names = ('gui.prb_control.dispatcher', 'constants', 'gui.prb_control')
    previous = dict((name, sys.modules.get(name)) for name in names)
    constants = types.ModuleType('constants')
    constants.PREBATTLE_TYPE = type('Types', (object,), {'SQUAD': 1})
    entity = type('Entity', (object,), {'getEntityType': lambda self: 1,
                                       'getPlayers': lambda self: {12: object(), 34: object()}})()
    dispatcher = types.ModuleType(names[0])
    dispatcher.g_prbLoader = type('Loader', (object,), {
        'getDispatcher': lambda self: type('Dispatcher', (object,), {'getEntity': lambda self: entity})()})()
    package = types.ModuleType('gui.prb_control')
    package.__path__ = []
    sys.modules['gui.prb_control'] = package
    sys.modules[names[0]] = dispatcher
    sys.modules['constants'] = constants
    try:
        check('platoon adapter reads the native squad player IDs', set(platoon_accounts()) == set(['12', '34']))
        entity.getEntityType = lambda: 999
        check('a larger unit is never treated as a platoon', platoon_accounts() == [])
    finally:
        for name, module in previous.items():
            if module is None:
                del sys.modules[name]
            else:
                sys.modules[name] = module
