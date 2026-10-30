"""Checks for the mod's page in modsSettingsApi: what it says, and what its buttons do."""

import copy
import os
import sys
import tempfile
import types

from checks.battle_fixtures import owned
from checks.common import check
from checks.engine import FakeEvent


class _Templates(object):
    """modsSettingsApi's templates, as plain dicts a check can read."""

    @staticmethod
    def createLabel(text, tooltip=None):
        return {'type': 'Label', 'text': text, 'tooltip': tooltip}

    @staticmethod
    def createButton(width=None, height=None, text=None):
        return {'type': 'Button', 'text': text}

    @staticmethod
    def createEmpty(height=None):
        return {'type': 'Empty'}


class _Api(object):
    def __init__(self):
        self.templates = []
        self.values = []
        self.onSettingsChanged = FakeEvent()
        self.onButtonClicked = FakeEvent()
        self.onWindowClosed = FakeEvent()
        self.live = []
        self.visible = None
        self.redraws = 0

    def setModTemplate(self, linkage, template, on_window, on_button):
        self.templates.append(template)
        self.onSettingsChanged += on_window
        self.onButtonClicked += on_button

    def updateModSettings(self, linkage, values):
        self.values.append(values)
        for handler in list(self.onSettingsChanged.handlers):
            handler(linkage, values)

    def open(self):
        # setModTemplate only changes the stored template, just like the API.
        self.visible = copy.deepcopy(self.templates[-1])

    def close(self):
        self.visible = None
        for handler in list(self.onWindowClosed.handlers):
            handler()

    def registerLiveSettingsChange(self, linkage, callback):
        self.live.append(callback)

    def unregisterLiveSettingsChange(self, linkage, callback):
        self.live.remove(callback)

    def toggle(self, enabled):
        from battle_conquest.settings_window import LINKAGE
        self.visible['enabled'] = enabled
        for handler in list(self.live):
            handler(LINKAGE, {'enabled': enabled})

    def reloadModTemplate(self, linkage, template):
        if self.visible is not None:
            self.visible = copy.deepcopy(template)
            self.redraws += 1


class _Session(object):
    def __init__(self):
        self.closers = []
        self.later = []
        self.ticks = []

    def repeat(self, interval, func):
        self.ticks.append(func)

    def callback(self, delay, func):
        self.later.append(func)

    def run_later(self):
        due, self.later = self.later, []
        for func in due:
            func()

    def on_close(self, func):
        self.closers.append(func)

    def subscribe(self, event, handler):
        event += handler
        self.on_close(lambda: event.__isub__(handler))


class _Site(object):
    page = 'https://example.test/my-mod'

    def __init__(self, places):
        self.places = places
        self.running = False
        self.started = 0
        self.listeners = []

    def on_change(self, callback):
        self.listeners.append(callback)

    def changed(self):
        for callback in list(self.listeners):
            callback()

    def start(self):
        self.started += 1
        self.running = True
        self.changed()

    def unlink(self):
        self.running = False
        self.places.forget()
        self.changed()


def _install_api():
    api = _Api()
    module = types.ModuleType('gui.modsSettingsApi')
    module.templates = _Templates
    module.g_modsSettingsApi = api
    sys.modules['gui.modsSettingsApi'] = module
    return api


def _places():
    from battle_conquest.destinations import Destinations

    return Destinations(('random', 'ranked', 'onslaught'), store=os.path.join(tempfile.mkdtemp(), 'link.json'),
                        url='https://example.test/api/mod/battles', account=lambda: '500123456')


def _texts(column):
    return [component.get('text') for component in column]


def _buttons(column):
    return [(component['varName'], component['button']['text']) for component in column if 'button' in component]


def check_settings_window_labels():
    from battle_conquest.settings_window import last_sent_label, link_label, modes_label, waiting_label

    check('an unlinked game says so', link_label(False, False) == u'Account: not linked')
    check('a linking under way sends the player to the browser',
          link_label(False, True) == u'Account: confirm in your browser')
    check('a linked game says so', link_label(True, False) == u'Account: linked')
    check('the modes sent are named', modes_label(['random', 'onslaught'], True)
          == u'Sending: random, onslaught battles')
    check('a pause is said rather than the modes', modes_label(['random'], False) == u'Sending: paused')
    check('nothing sent yet says so', last_sent_label(None, None) == u'Last sent: nothing this session')
    said = last_sent_label(0.0, {'code': 200, 'battles': 3, 'accepted': 2, 'duplicates': 1, 'rejected': 0})
    check('a batch taken says what came of it', said.endswith(u'2 accepted, 1 already known'))
    refused = last_sent_label(0.0, {'code': 503, 'battles': 3})
    check('a refusal says it will be tried again', u'HTTP 503' in refused and u'try again' in refused)
    check('one battle waiting is one battle', waiting_label(1) == u'Waiting to be sent: 1 battle')
    check('and more are counted', waiting_label(4) == u'Waiting to be sent: 4 battles')


def check_settings_window():
    from battle_conquest.settings_window import (LINK_VAR, LINKAGE, PAGE_VAR, UNLINK_VAR, SettingsWindow)

    api = _install_api()
    try:
        places = _places()
        site = _Site(places)
        opened = []
        from battle_conquest import site_link
        standing = site_link.open_url
        site_link.open_url = opened.append
        try:
            window = SettingsWindow(_Session(), site, places)
            window.install()
            page = api.templates[-1]
            check('the page is registered under the mod\'s name', page['modDisplayName'] == 'Battle-Conquest')
            check('the account heading has no decorative characters or extra spaces',
                  page['column1'][0]['text'] == u'ACCOUNT')
            check('the sending heading has no decorative characters or extra spaces',
                  page['column2'][0]['text'] == u'SENDING')
            check('an unlinked game offers to link', (LINK_VAR, 'Link') in _buttons(page['column1']))
            check('and its own page on the site', (PAGE_VAR, 'Open') in _buttons(page['column1']))
            check('the sending column says nothing was sent', u'Last sent: nothing this session'
                  in _texts(page['column2']))
            check('the box is ticked while unlinked', api.values[-1] == {'enabled': True})

            window._on_button(LINKAGE, LINK_VAR)
            check('Link starts the linking', site.started == 1)
            check('and the page follows it at once',
                  u'Account: confirm in your browser' in _texts(api.templates[-1]['column1']))
            window._on_button('someone.else', LINK_VAR)
            check('a click on another mod\'s page is not ours', site.started == 1)

            site.running = False
            places.remember('Battle-Conquest', ['random', 'onslaught'], 'd' * 64)
            window._check_state()
            page = api.templates[-1]
            check('a linked game offers to unlink', (UNLINK_VAR, 'Unlink') in _buttons(page['column1']))
            check('and names what it sends', u'Sending: random, onslaught battles' in _texts(page['column1']))

            window._on_window(LINKAGE, {'enabled': False})
            check('unticking the box pauses sending', not places.enabled and places.linked)
            check('and the page says so', u'Sending: paused' in _texts(api.templates[-1]['column1']))
            window._on_window(LINKAGE, {'enabled': True})
            check('ticking it again resumes', places.enabled)

            window._on_button(LINKAGE, PAGE_VAR)
            check('Open sends the player to their page on the site', opened == ['https://example.test/my-mod'])

            window._on_button(LINKAGE, UNLINK_VAR)
            check('Unlink forgets the link', not places.linked)
            check('and the page offers to link again', (LINK_VAR, 'Link') in _buttons(api.templates[-1]['column1']))

            count = len(api.templates)
            window._remove()
            window._on_button(LINKAGE, LINK_VAR)
            check('a page from a closed session does nothing', site.started == 1 and len(api.templates) == count)
        finally:
            site_link.open_url = standing
    finally:
        del sys.modules['gui.modsSettingsApi']


def check_settings_window_without_api():
    from battle_conquest.settings_window import SettingsWindow

    places = _places()
    session = _Session()
    SettingsWindow(session, _Site(places), places).install()
    check('without modsSettingsApi there is no page, and nothing to close', session.closers == [])


def check_settings_window_live():
    from battle_conquest.report_queue import Queue
    from battle_conquest.settings_window import CANCEL_VAR, LINK_VAR, UNLINK_VAR, SettingsWindow
    from checks.report_sender import _answer, _queue, _sender, _took

    api = _install_api()
    try:
        places = _places()
        site = _Site(places)
        sending, sender = _sender(_queue(count=1), places=places)
        session = _Session()
        window = SettingsWindow(session, site, places, sender)
        window.install()
        api.open()
        check('an open page initially shows the one queued battle',
              u'Waiting to be sent: 1 battle' in _texts(api.visible['column2']))

        site.start()
        check('a redraw waits until the click has returned',
              (LINK_VAR, 'Link') in _buttons(api.visible['column1']))
        session.run_later()
        check('a link started outside the page updates the open controls',
              (CANCEL_VAR, 'Cancel') in _buttons(api.visible['column1']))

        site.running = False
        places.remember('Battle-Conquest', ['ranked'], 'd' * 64)
        site.changed()
        session.run_later()
        check('browser confirmation redraws the open page without reopening it',
              (UNLINK_VAR, 'Unlink') in _buttons(api.visible['column1'])
              and u'Account: linked' in _texts(api.visible['column1']))

        sender.drain()
        _answer(sending, 200, _took(1))
        session.run_later()
        check('one accepted battle shows last sent one and waiting zero together',
              any(text and text.endswith('1 accepted') for text in _texts(api.visible['column2']))
              and u'Waiting to be sent: 0 battles' in _texts(api.visible['column2']))
        check('the accepted battle is also gone from disk', Queue(sender._queue._store).all() == [])

        sender._queue.add(owned({'arena_unique_id': '2', 'mode': 'ranked', 'account': sender._account.account}))
        for tick in session.ticks:
            tick()
        session.run_later()
        check('the periodic check also redraws newly captured battles',
              u'Waiting to be sent: 1 battle' in _texts(api.visible['column2']))
        sender.drain()
        _answer(sending, 503)
        session.run_later()
        check('a failed send still shows one waiting with the failure',
              u'Waiting to be sent: 1 battle' in _texts(api.visible['column2'])
              and any(text and 'HTTP 503' in text for text in _texts(api.visible['column2'])))

        before = api.redraws
        site.changed()
        session.run_later()
        check('an unchanged state causes no Flash rebuild', api.redraws == before)
        check('refreshes keep exactly one of each API callback',
              len(api.onSettingsChanged.handlers) == len(api.onButtonClicked.handlers) == 1)
        site.unlink()
        site.start()
        session.run_later()
        check('same-frame changes coalesce into one redraw of the latest state',
              api.redraws == before + 1 and (CANCEL_VAR, 'Cancel') in _buttons(api.visible['column1']))
        site.unlink()
        for close in session.closers:
            close()
        count = len(api.templates)
        session.run_later()
        site.changed()
        check('closing removes API callbacks and blocks pending redraws and link events',
              not api.onSettingsChanged.handlers and not api.onButtonClicked.handlers
              and len(api.templates) == count and api.redraws == before + 1)
    finally:
        del sys.modules['gui.modsSettingsApi']


def check_settings_window_api_variants():
    from battle_conquest.settings_window import SettingsWindow

    api = _install_api()
    module = sys.modules['gui.modsSettingsApi']
    api.registerLiveSettingsChange = None
    # Both public shapes have shipped: a direct instance and a private wrapper.
    wrapper = type('Wrapper', (object,), {})()
    wrapper._ModsSettingsApi__instance = api
    wrapper.setModTemplate = api.setModTemplate
    wrapper.updateModSettings = api.updateModSettings
    module.g_modsSettingsApi = wrapper
    sys.modules['gui.aslainMenu'] = module
    del sys.modules['gui.modsSettingsApi']
    try:
        places = _places()
        site = _Site(places)
        session = _Session()
        window = SettingsWindow(session, site, places)
        window.install()
        api.open()
        site.start()
        session.run_later()
        check('Aslain alone and the older wrapped API both support live redraw', api.redraws == 1)
        # Original modsSettingsApi has no live channel. Updating stored data
        # must still work there without calling an unsupported Flash method.
        api.reloadModTemplate = None
        site.unlink()
        session.run_later()
        api.open()
        check('legacy APIs without live redraw still get current data on reopen',
              u'Account: not linked' in _texts(api.visible['column1']))
        window._remove()
        check('wrapped API callbacks are removed as well',
              not api.onSettingsChanged.handlers and not api.onButtonClicked.handlers)
    finally:
        del sys.modules['gui.aslainMenu']


def check_settings_window_pending_pause():
    from battle_conquest.settings_window import LINKAGE, SettingsWindow

    api = _install_api()
    try:
        places = _places()
        places.remember('Battle-Conquest', ['random'], 'd' * 64)
        site = _Site(places)
        session = _Session()
        window = SettingsWindow(session, site, places)
        window.install()
        api.open()
        api.toggle(False)
        check('changing the pause switch waits for Apply', places.enabled)
        # A changed mode triggers the same redraw as an answered batch.
        places.current.modes.append('onslaught')
        site.changed()
        session.run_later()
        check('a status redraw preserves an unapplied pause without persisting it',
              api.visible['enabled'] is False and places.enabled)
        check('the saved page still reflects the committed setting', api.templates[-1]['enabled'] is True)
        window._on_window(LINKAGE, {'enabled': False})
        session.run_later()
        check('Apply commits the preserved pause', not places.enabled and api.visible['enabled'] is False)

        api.toggle(True)
        places.current.modes.remove('onslaught')
        site.changed()
        session.run_later()
        check('an unapplied resume survives redraws too', api.visible['enabled'] is True and not places.enabled)
        api.close()
        api.open()
        check('Cancel discards the preview on the next open', api.visible['enabled'] is False)
        places.current.modes.append('onslaught')
        site.changed()
        session.run_later()
        check('subsequent redraws cannot resurrect a cancelled preview', api.visible['enabled'] is False)
        for close in session.closers:
            close()
        check('closing the session detaches preview callbacks as well',
              not api.live and not api.onWindowClosed.handlers)
    finally:
        del sys.modules['gui.modsSettingsApi']
