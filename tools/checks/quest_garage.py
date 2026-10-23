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
    from battle_conquest.quest_garage_view import lines, metric_value
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

    check('absent metrics are not rendered as zero', metric_value({'totals': {'credits_net': None}}, 'credits_net') == '?')
    check('partial known values remain readable', metric_value({'totals': {'credits_net': None}, 'known_totals': {'credits_net': -10}}, 'credits_net') == '-10 + ?')
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
    garage.poll(force=True)
    session.sent.pop(0)['answer'](_Response(200, {'schema': 1, 'config': []}))
    check('malformed successful replies retain the last readable snapshot', garage.offline and garage.data == data)
    malformed = copy.deepcopy(data)
    malformed['players'][0]['official'] = ['invalid score']
    garage.poll(force=True)
    session.sent.pop(0)['answer'](_Response(200, malformed))
    check('malformed score structures cannot replace readable values', garage.offline and garage.data == data)
    garage.save(mode='manual')
    repeated = copy.deepcopy(data)
    repeated['config']['version'] = 3
    session.sent.pop(0)['answer'](_Response(200, repeated))
    check('a concurrent write after successful saving is still visible', garage.conflict and garage.data == data)
    garage.reload()
    session.sent.pop(0)['answer'](_Response(200, copy.deepcopy(data)))
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

        # Full native editor with a poll arriving between typing and Enter.
        from battle_conquest.quest_garage import Garage
        from battle_conquest.destinations import Destination, battles_url
        session = _Session()
        account = type('Account', (object,), {'account': '500883375'})()
        places = type('Places', (object,), {'current': Destination(battles_url(), enabled=True, modes=['random'], secret='a' * 64)})()
        panel = Panel(None, store=store)
        panel.collapsed = False
        panel.visible(True)
        garage = Garage(session, account, places, panel, garage=lambda: True, platoon=lambda: [], now=lambda: 100.0)
        garage.key = garage.identity()
        garage.data = {'schema': 1, 'config': {'version': 1, 'selection': '', 'mode': 'manual', 'manual_ids': [2]},
                       'choices': [], 'selected': None, 'players': []}
        panel.garage = garage
        panel.edit()
        newer = copy.deepcopy(garage.data)
        newer['config'].update(version=2, manual_ids=[3])
        garage.poll(force=True)
        enter = type('Key', (object,), {'key': 13, 'isKeyDown': lambda self: True})()
        keys = types.ModuleType('Keys')
        keys.KEY_RETURN, keys.KEY_ESCAPE, keys.KEY_BACKSPACE = 13, 27, 8
        previous_keys = sys.modules.get('Keys')
        sys.modules['Keys'] = keys
        try:
            panel.editing = u'4'
            panel.handleKeyEvent(enter)
            check('Enter while a poll is in flight retains the pending input', panel.editing == '4')
            session.sent.pop(0)['answer'](_Response(200, newer))
            panel.handleKeyEvent(enter)
            request = session.sent.pop(0)
            check('manual edits keep the version observed at the start of editing', request['body']['version'] == 1)
            request['answer'](_Response(409, {'error': 'conflict'}))
            check('polling cannot hide a conflicting manual edit', garage.conflict)
            panel.reload()
            session.sent.pop(0)['answer'](_Response(200, newer))
            check('explicit Reload discards the old draft and accepts fresh settings', panel.editing is None and garage.data['config']['version'] == 2)
        finally:
            if previous_keys is None:
                del sys.modules['Keys']
            else:
                sys.modules['Keys'] = previous_keys
        panel.close()
        with open(store, 'wb') as handle:
            handle.write('[]')
        damaged = Panel(None, store=store)
        check('a valid JSON value of the wrong shape cannot break mod startup', damaged.root is None)
        count = [0]
        def broken_text(value):
            count[0] += 1
            if count[0] == 2:
                raise ValueError('native component unavailable')
            return Node(value)
        module.Text = broken_text
        damaged.visible(True)
        check('a partially built panel cleans up without removing an unregistered GUI root', damaged.failed and damaged.root is None and not roots)

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
