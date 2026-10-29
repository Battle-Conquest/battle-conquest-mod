"""Private collection is manual, account-bound, bounded and reload-safe."""
import json
import os
import sys
import types

from checks.common import REPO, check
from checks.site_link import _Response


class Session(object):
    def __init__(self):
        self.alive, self.pending, self.sent, self.closers = True, [], [], []
        self.patches = []

    def callback(self, delay, callback):
        self.pending.append((delay, callback))

    def on_close(self, callback):
        self.closers.append(callback)

    def patch(self, holder, name, build):
        own = name in holder.__dict__
        stored = holder.__dict__.get(name)
        self.patches.append((holder, name, own, stored))
        setattr(holder, name, build(getattr(holder, name)))

    def fetch(self, url, callback, **kwargs):
        self.sent.append((url, callback, kwargs))

    def next(self):
        self.pending.pop(0)[1]()

    def close(self):
        if not self.alive:
            return
        self.alive = False
        for callback in reversed(self.closers):
            callback()
        for holder, name, own, stored in reversed(self.patches):
            if own:
                setattr(holder, name, stored)
            else:
                delattr(holder, name)


def check_catalog_tester():
    import battle_conquest
    path = os.path.join(REPO, 'tester', 'battle_conquest')
    battle_conquest.__path__.append(path)
    try:
        from battle_conquest.catalog_tester import Collector
        from battle_conquest import catalog_source
        fixture = os.path.join(REPO, 'tools', 'checks', 'fixtures', 'mod_vehicle_catalog.json')
        with open(fixture) as handle:
            payload = json.load(handle)
        entries = payload['vehicles']
        check('Python and PHP use the same catalogue fingerprint',
              catalog_source.fingerprint(list(reversed(entries))) == payload['fingerprint'])
        target = type('Target', (object,), {'url': 'https://example.test/api/mod/battles',
                      'enabled': True, 'secret': 'a' * 64})()
        places = type('Places', (object,), {'current': target})()
        account = type('Account', (object,), {'account': '123', 'on_change': lambda self, fn: None})()
        current = ['123']
        session, messages = Session(), []
        collector = Collector(session, account, places, '1.2.0', garage=lambda: True,
                              current=lambda: current[0], source=lambda: iter(entries),
                              client_version=lambda: 'v.2.4.1.0 #1', notify=lambda *args: messages.append(args))
        check('installation reads and sends nothing', not session.pending and not session.sent)
        collector.start()
        collector.start()
        check('double click schedules only one collection', len(session.pending) == 1 and not session.sent)
        session.next()
        check('only the complete catalogue is sent to its dedicated route',
              len(session.sent) == 1 and session.sent[0][0].endswith('/api/mod/vehicle-catalog'))
        body = json.loads(session.sent[-1][2]['post_data'])
        check('catalogue carries the current account and identical fingerprint',
              body['account']['id'] == 123 and body['fingerprint'] == payload['fingerprint'])
        answer = session.sent[-1][1]
        answer(_Response(503, {'error': 'server_error'}))
        check('temporary refusal schedules a retry, no immediate duplicate',
              len(session.pending) == 1 and session.pending[0][0] == 5.0)
        session.next()
        session.sent[-1][1](_Response(200, {'schema': 2, 'count': 6, 'duplicate': False}))
        check('success still requires admin validation', not collector.busy and 'Admin validation' in collector.status)
        collector.start()
        session.next()
        old_answer = session.sent[-1][1]
        current[0] = '456'
        old_answer(_Response(200, {'schema': 2, 'count': 6, 'duplicate': False}))
        check('an account switch invalidates an in-flight response', not collector.busy and 'cancelled' in collector.status)
        current[0] = '123'
        collector.start()
        session.next()
        session.sent[-1][1](_Response(403, {'error': 'forbidden'}))
        check('permanent refusal is visible and never retried', not collector.busy and not session.pending and 'forbidden' in collector.status)
        collector.start()
        callback = session.pending[0][1]
        session.close()
        sent = len(session.sent)
        callback()
        check('closing prevents late collection and sending', len(session.sent) == sent and not collector.busy)

        def broken():
            yield entries[0]
            raise ValueError('incomplete client surface')
        session = Session()
        broken_collector = Collector(session, account, places, '1.2.0', garage=lambda: True,
            current=lambda: '123', source=broken, client_version=lambda: '2.4', notify=lambda *args: None)
        broken_collector.start()
        session.next()
        check('a partial extraction never uploads', not session.sent and not broken_collector.busy)
        check_source(catalog_source)
        check_ui()
        check_link_invalidation(entries)
        check_notice_retry()
        check_transport_setup(entries)
        check_native_progress(entries)
    finally:
        battle_conquest.__path__.remove(path)


def check_source(source):
    previous = dict((name, sys.modules.get(name)) for name in ('items', 'nations'))
    try:
        entries = {1: type('Descriptor', (object,), {'compactDescr': 101, 'name': 'usa:Example', 'tags': set(['heavyTank'])})()}
        items = types.ModuleType('items')
        items.vehicles = type('Vehicles', (object,), {'g_list': type('List', (object,), {'getList': lambda self, nation: entries})()})()
        nations = types.ModuleType('nations')
        nations.NAMES = ['usa']
        nations.AVAILABLE_NAMES = ['usa']
        sys.modules['items'], sys.modules['nations'] = items, nations
        check('client extraction reads the complete national list without inventory access',
              list(source.vehicles()) == [{'tank_id': 101, 'name': 'usa:Example', 'tags': ['heavyTank']}])
        entries[2] = entries[1]
        try:
            list(source.vehicles())
            check('duplicate client identifiers refused', False)
        except ValueError:
            pass
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def check_ui():
    from battle_conquest import settings_window
    from battle_conquest.catalog_tester_ui import install
    from battle_conquest.catalog_tester import BUTTON
    from battle_conquest.runtime.session import Session as RuntimeSession
    from checks.settings_window import _install_api, _places, _Site
    previous = sys.modules.get('gui.modsSettingsApi')
    original_template = settings_window.template
    original_button = settings_window.SettingsWindow.__dict__['_on_button']
    original_name = settings_window.NAME
    session = RuntimeSession(0)
    calls = []
    try:
        api = _install_api()
        places = _places()
        page = settings_window.SettingsWindow(session, _Site(places), places)
        page.install()
        collector = type('Collector', (object,), {'status': 'Private tester: manual collection', 'busy': False,
            'start': lambda self: calls.append('start'), 'cancel': lambda self: calls.append('cancel'),
            'garage': lambda self: True})()
        install(session, collector, page)
        check('a visible settings page needs no extra phase notifications', not collector.notify_progress)
        check('tester refresh preserves exactly one settings callback', len(api.onButtonClicked.handlers) == 1)
        for handler in list(api.onButtonClicked.handlers):
            handler(settings_window.LINKAGE, BUTTON)
        check('one tester click triggers collection exactly once', calls == ['start'])
        collector.status = 'Complete; waiting for admin review'
        collector.changed()
        check('tester result refresh does not stack subscriptions', len(api.onButtonClicked.handlers) == 1)
        check('tester identity is explicit in the settings page', 'TESTER' in api.templates[-1]['modDisplayName'])
        check('installing tester UI never starts collection', calls == ['start'])
        session.close()
        check('tester teardown restores hooks and removes every settings subscription',
              settings_window.template is original_template
              and settings_window.SettingsWindow.__dict__['_on_button'] is original_button
              and settings_window.NAME == original_name and not api.onButtonClicked.handlers)
    finally:
        session.close()
        if previous is None:
            sys.modules.pop('gui.modsSettingsApi', None)
        else:
            sys.modules['gui.modsSettingsApi'] = previous


def check_link_invalidation(entries):
    from battle_conquest.catalog_tester import Collector
    from checks.site_link import _destinations
    session = Session()
    places = _destinations()
    places.remember('Tester', ['random'], 'a' * 64)
    account = type('Account', (object,), {'account': '123', 'on_change': lambda self, fn: None})()
    collector = Collector(session, account, places, '1.2.0', garage=lambda: True,
        current=lambda: '123', source=lambda: iter(entries), client_version=lambda: '2.4', notify=lambda *args: None)
    try:
        collector.start()
        session.next()
        session.sent[-1][1](_Response(503, {'error': 'server_error'}))
        places.set_enabled(False)
        places.set_enabled(True)
        session.next()
        check('pause followed by resume cannot revive a scheduled upload', not collector.busy and len(session.sent) == 1)

        collector.start()
        session.next()
        answer = session.sent[-1][1]
        places.forget()
        places.remember('Tester', ['random'], 'a' * 64)
        answer(_Response(200, {'schema': 2, 'count': len(entries), 'duplicate': False}))
        check('unlink and relink cannot restore an obsolete result', not collector.busy and 'cancelled' in collector.status)
    finally:
        session.close()
    check('link mutation hooks are removed on close',
          all(name not in places.__dict__ for name in ('set_enabled', 'forget', 'remember')))


def check_notice_retry():
    from battle_conquest import notices
    from battle_conquest.catalog_tester_ui import install
    from battle_conquest.catalog_tester import ACTION
    session = Session()
    attempts, collected = [], []
    original_push, original_handlers = notices.push, notices._actions_handlers
    class Handlers(object):
        def handleAction(self, *args, **kwargs):
            pass
    def push(text):
        attempts.append(text)
        return len(attempts) >= 2
    notices.push = push
    notices._actions_handlers = lambda: Handlers
    page = type('Page', (object,), {'available': False})()
    collector = type('Collector', (object,), {'status': 'Waiting for a manual click', 'busy': False,
        'garage': lambda self: True, 'start': lambda self: collected.append('start')})()
    try:
        install(session, collector, page)
        check('native-only controls also enable phase notifications', collector.notify_progress)
        session.next()
        check('an unavailable notification centre retries the only collect action', len(session.pending) == 1)
        session.next()
        check('a successful collect notification is not repeated', len(attempts) == 2 and not session.pending)
        check('retrying the notification never collects a catalogue', not collected)
        Handlers().handleAction(None, 1, 2, ACTION)
        check('the native collect action starts only after a click', collected == ['start'])
    finally:
        session.close()
        notices.push, notices._actions_handlers = original_push, original_handlers


def check_transport_setup(entries):
    from battle_conquest.catalog_tester import Collector
    from checks.site_link import _destinations
    class TransportSession(Session):
        def __init__(self):
            Session.__init__(self)
            self.attempts = 0
        def fetch(self, url, callback, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                raise IOError('temporary transport setup failure')
            Session.fetch(self, url, callback, **kwargs)
    session = TransportSession()
    places = _destinations()
    places.remember('Tester', ['random'], 'a' * 64)
    account = type('Account', (object,), {'account': '123', 'on_change': lambda self, fn: None})()
    collector = Collector(session, account, places, '1.2.0', garage=lambda: True,
        current=lambda: '123', source=lambda: iter(entries), client_version=lambda: '2.4', notify=lambda *args: None)
    try:
        collector.start()
        session.next()
        check('a transport setup exception preserves the catalogue and schedules a retry',
              collector.busy and len(session.pending) == 1 and session.pending[0][0] == 5.0)
        session.next()
        check('the next transport attempt sends the same complete catalogue',
              session.attempts == 2 and json.loads(session.sent[-1][2]['post_data'])['vehicles'] == entries)
        session.sent[-1][1](_Response(200, {'schema': 2, 'count': len(entries), 'duplicate': False}))
        check('a recovered transport finishes normally', not collector.busy and 'Admin validation' in collector.status)
        session.attempts = 0
        def unavailable(*args, **kwargs):
            session.attempts += 1
            raise IOError('still unavailable')
        session.fetch = unavailable
        collector.start()
        while session.pending:
            session.next()
        check('repeated transport setup failures use at most three retries', not collector.busy and session.attempts == 4)
    finally:
        session.close()


def check_native_progress(entries):
    from battle_conquest.catalog_tester import Collector
    from checks.site_link import _destinations
    session, messages = Session(), []
    places = _destinations()
    places.remember('Tester', ['random'], 'a' * 64)
    account = type('Account', (object,), {'account': '123', 'on_change': lambda self, fn: None})()
    collector = Collector(session, account, places, '1.2.0', garage=lambda: True,
        current=lambda: '123', source=lambda: iter([dict(entry, tank_id=i + 1) for i, entry in enumerate(entries * 10)]), client_version=lambda: '2.4',
        notify=messages.append)
    collector.notify_progress = True
    try:
        collector.start()
        check('native-only collection acknowledges the manual start immediately',
              len(messages) == 1 and 'Collecting the full' in messages[-1])
        session.next()
        check('native progress does not flood notifications for every extraction slice', len(messages) == 1)
        while session.pending:
            session.next()
        check('native-only upload announces sending', len(messages) == 2 and 'Sending' in messages[-1])
        session.sent[-1][1](_Response(503, {'error': 'server_error'}))
        check('native-only temporary errors expose the retry delay', len(messages) == 3 and 'retrying in 5' in messages[-1])
    finally:
        session.close()
