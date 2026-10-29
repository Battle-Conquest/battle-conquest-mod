"""Hide the panel through hangar loading without delaying report transport."""
import os
import shutil
import sys
import tempfile
import types

from checks.battle_fixtures import owned
from checks.common import check
from checks.report_sender import _Session, _places, _destination, _queue, _answer, _took
from checks.report_sender import _Event, _Account
from checks.native_gui import native_gui


def check_garage_ready():
    from battle_conquest.garage_ready import garage_ready
    from battle_conquest.quest_garage import Garage
    from battle_conquest.quest_garage_input import Input
    from battle_conquest.destinations import Destination, battles_url
    from battle_conquest.report_sender import at_garage

    names = ('helpers', 'skeletons.gui.shared.utils', 'gui.Scaleform.Waiting',
             'gui', 'gui.Scaleform', 'skeletons', 'skeletons.gui', 'skeletons.gui.shared')
    previous = dict((name, sys.modules.get(name)) for name in names)
    player, loaded, waiting = [True], [False], [True]
    space = type('Space', (object,), {'spaceInited': property(lambda self: loaded[0])})()
    helpers = types.ModuleType('helpers')
    helpers.isPlayerAccount = lambda: player[0]
    helpers.dependency = type('Dependency', (object,), {'instance': staticmethod(lambda kind: space)})
    interface = types.ModuleType('skeletons.gui.shared.utils')
    interface.IHangarSpace = type('IHangarSpace', (object,), {})
    overlay = types.ModuleType('gui.Scaleform.Waiting')
    overlay.Waiting = type('Waiting', (object,), {'isVisible': staticmethod(lambda: waiting[0])})
    for name in names[3:]:
        if name not in sys.modules:
            package = types.ModuleType(name)
            package.__path__ = []
            sys.modules[name] = package
    sys.modules.update(helpers=helpers)
    sys.modules[names[1]], sys.modules[names[2]] = interface, overlay
    try:
        check('an account during garage loading is ready for transport but not for display', at_garage() and not garage_ready())
        loaded[0] = True
        check('a loaded space under a waiting overlay still hides the panel', not garage_ready())
        waiting[0] = False
        check('the panel becomes eligible only after the space is loaded and the overlay is gone', garage_ready())
        player[0] = False
        check('a retained hangar space cannot expose the panel in battle', not garage_ready())
        player[0], loaded[0], waiting[0] = True, False, True
        class View(object):
            shown = False
            def visible(self, state, preserve_draft=False):
                self.shown = state
            def reset(self):
                pass
            def render(self, garage):
                pass
        session, view = _Session(), View()
        account = type('Account', (object,), {'account': '500883375'})()
        places = type('Places', (object,), {'current': Destination(battles_url(), secret='a' * 64, enabled=True, modes=['random'])})()
        garage = Garage(session, account, places, view, platoon=lambda: [], now=lambda: 100.0)
        garage.tick()
        snapshot = {'schema': 1, 'config': {'version': 1, 'selection': '', 'mode': 'manual', 'manual_ids': []},
                    'choices': [], 'selected': None, 'players': []}
        _answer(session, 200, snapshot)
        garage.tick()
        check('a completed snapshot during loading stays hidden', garage.data == snapshot and not view.shown)
        loaded[0], waiting[0] = True, False
        garage.tick()
        check('garage readiness reveals the retained snapshot without another network request', view.shown and not session.sent)
        waiting[0] = True
        garage.tick()
        check('a fresh loading overlay hides the panel again', not view.shown)
        panel = type('Panel', (object,), {'root': type('Root', (object,), {'visible': True})(),
                     'garage': garage, 'drag': object(), 'pressed': object(), 'scroller': None})()
        check('loading stops input capture before the next visibility tick', not Input(session, panel).active() and panel.drag is None)
        gui, roots, resolution, cursor, native_node, modes = native_gui()
        old_gui = sys.modules.get('GUI')
        sys.modules['GUI'] = gui
        directory = tempfile.mkdtemp(prefix='bc-ready-draft-')
        from battle_conquest.quest_garage_view import Panel
        native = Panel(None, store=os.path.join(directory, 'panel.json'))
        try:
            loaded[0], waiting[0] = True, False
            live = Garage(session, account, places, native, platoon=lambda: [], now=lambda: 100.0)
            live.key, live.data, live.last_poll = live.identity(), dict(snapshot), 100.0
            live.tick()
            native.edit()
            native.picker.entries = [{'id': 2, 'username': 'Alice'}]
            native.picker.changed()
            native.picker.query = u'Bo'
            native.picker.results = [{'id': 3, 'username': 'Bob'}]
            native.render(live)
            version = native.edit_version
            waiting[0] = True
            live.tick()
            check('a transient waiting overlay preserves named selections, query and draft version',
                  not native.root.visible and native.editing == '2' and native.edit_version == version
                  and native.picker.query == u'Bo' and native.picker.entries[0]['username'] == 'Alice')
            check('hidden suggestions and interaction are cancelled during the wait',
                  not native.picker.results and native.drag is None and native.pressed is None)
            resumed = []
            original_type = native.picker.type
            def typed(query):
                resumed.append(query)
                original_type(query)
            native.picker.type = typed
            waiting[0] = False
            live.tick()
            live.tick()
            check('the retained name query restarts once when the loaded garage returns',
                  native.root.visible and resumed == [u'Bo'] and native.editing == '2' and native.edit_version == version)
            native.toggle()
            waiting[0] = True
            live.tick()
            waiting[0] = False
            live.tick()
            check('a folded suspended draft waits until expanded to restart its query',
                  native.collapsed and resumed == [u'Bo'] and native.picker.query == u'Bo')
            native.toggle()
            check('expanding resumes the retained name query', resumed == [u'Bo', u'Bo'])
            player[0] = False
            live.tick()
            check('leaving for battle still discards the draft and query',
                  not native.root.visible and native.editing is None and not native.picker.query)
            player[0] = True
            live.tick()
            native.edit()
            native.picker.entries = [{'id': 2, 'username': 'Alice'}]
            native.picker.changed()
            waiting[0] = True
            live.tick()
            account.account = '500999999'
            live.tick()
            check('an account change during loading clears the suspended draft', native.editing is None and not native.picker.query)
        finally:
            native.close()
            shutil.rmtree(directory)
            if old_gui is None:
                sys.modules.pop('GUI', None)
            else:
                sys.modules['GUI'] = old_gui
        account.account = '500883375'
        helpers.dependency.instance = staticmethod(lambda kind: None)
        check('an unavailable hangar service never exposes the panel on loading', not garage_ready())
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def check_sender_after_capture():
    from battle_conquest import report_sender as module
    from checks.battle_fixtures import Player, ACCOUNT
    class Timers(_Session):
        def __init__(self):
            _Session.__init__(self)
            self.periodic = []
        def repeat(self, interval, func):
            self.periodic.append((interval, func))
    events = _Event()
    previous = module.service_hooks.account_events
    module.service_hooks.account_events = lambda: _Account(events)
    try:
        session, queue = Timers(), _queue(count=0)
        sender = module.Sender(session, Player(ACCOUNT), queue=queue, destinations=_places(_destination()), garage=lambda: True)
        sender.install()
        events.fire()
        check('returning before the result arrives sends no empty HTTP batch', not session.sent)
        interval, tick = session.periodic[0]
        check('the local queue is checked within five seconds after a late capture', interval <= 5)
        queue.add(owned({'arena_unique_id': '123', 'account': ACCOUNT, 'mode': 'ranked',
                   'finished_at': '2026-10-25T16:00:00Z', 'outcome': 'win', 'survived': True, 'metrics': {}}))
        tick()
        check('a result arriving after the garage event leaves on that next short tick', len(session.sent) == 1)
        tick()
        check('short ticks never duplicate a request already in flight', len(session.sent) == 1)
        _answer(session, 503)
        for unused in range(10):
            tick()
        check('short queue ticks retain the existing network-error backoff', not session.sent and len(queue.all()) == 1)
        sender._waiting.clear()
        tick()
        _answer(session, 200, _took(1))
        for unused in range(10):
            tick()
        check('settled results cause no repeated or empty HTTP requests', not session.sent and not queue.all())
        fetch = session.fetch
        def broken_fetch(*args, **kwargs):
            raise RuntimeError('transport failed before installing a callback')
        queue.add(owned({'arena_unique_id': '124', 'account': ACCOUNT, 'mode': 'ranked',
                   'finished_at': '2026-10-25T16:01:00Z', 'outcome': 'win', 'survived': True, 'metrics': {}}))
        session.fetch = broken_fetch
        raised = False
        try:
            tick()
        except RuntimeError:
            raised = True
        check('a synchronous transport failure releases the send gate and retains the report',
              not raised and not sender._busy and len(queue.all()) == 1 and bool(sender._waiting))
        session.fetch = fetch
        tick()
        check('a failed transport setup also respects the retry backoff', not session.sent)
        sender._waiting.clear()
        tick()
        _answer(session, 200, _took(1))
        check('delivery recovers after transport setup fails, without restarting the mod', not queue.all() and not sender._busy)

    finally:
        module.service_hooks.account_events = previous
