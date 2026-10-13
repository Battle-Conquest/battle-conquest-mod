"""Checks for the mod's page in modsSettingsApi: what it says, and what its buttons do."""

import os
import sys
import tempfile
import types

from checks.common import check


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

    def setModTemplate(self, linkage, template, on_window, on_button):
        self.templates.append(template)

    def updateModSettings(self, linkage, values):
        self.values.append(values)


class _Session(object):
    def __init__(self):
        self.closers = []

    def repeat(self, interval, func):
        pass

    def on_close(self, func):
        self.closers.append(func)


class _Site(object):
    page = 'https://example.test/my-mod'

    def __init__(self, places):
        self.places = places
        self.running = False
        self.started = 0

    def start(self):
        self.started += 1
        self.running = True

    def unlink(self):
        self.running = False
        self.places.forget()


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
                        url='https://example.test/api/mod/battles')


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
