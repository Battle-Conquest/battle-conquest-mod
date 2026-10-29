"""Checks for the garage's notices: the way to link that needs no other mod."""

import os
import sys
import tempfile
import types

from checks.common import check


class _Handlers(object):
    """The client's notification actions handler, as the notices patch it."""

    def handleAction(self, model, typeID, entityID, actionName):
        return 'the client handled %s' % actionName


ORIGINAL_HANDLE = _Handlers.__dict__['handleAction']


class _Account(object):
    def __init__(self, account=None):
        self.account = account
        self._listeners = []

    def on_change(self, callback):
        self._listeners.append(callback)

    def log_in(self, account='500123456'):
        self.account = account
        for callback in list(self._listeners):
            callback()


class _Site(object):
    def __init__(self, places, can_start=True):
        self.running = False
        self.started = 0
        self._can_start = can_start
        self._endings = []
        self._listeners = []
        self.places = places

    def on_change(self, callback):
        self._listeners.append(callback)

    def changed(self):
        for callback in list(self._listeners):
            callback()

    def on_done(self, callback):
        self._endings.append(callback)

    def start(self):
        self.started += 1
        if self._can_start:
            self.running = True
            self.changed()
        return self._can_start

    def end(self, destination):
        self.running = False
        if destination is not None:
            self.places.remember('Battle-Conquest', destination.modes, 'f' * 64)
        self.changed()
        for callback in list(self._endings):
            callback(destination)


class _Page(object):
    def __init__(self, available):
        self.available = available


class _Session(object):
    """A real Session for its patches, with callbacks run when a check says."""

    def __init__(self):
        from battle_conquest.runtime.session import Session

        self.real = Session(0)
        self.later = []

    def patch(self, holder, name, build):
        return self.real.patch(holder, name, build)

    def callback(self, delay, func):
        self.later.append(func)

    def run_later(self):
        due, self.later = self.later, []
        for func in due:
            func()


def _places():
    from battle_conquest.destinations import Destinations

    return Destinations(('random', 'onslaught'), store=os.path.join(tempfile.mkdtemp(), 'link.json'),
                        url='https://example.test/api/mod/battles', account=lambda: '500123456')


def _with_handlers(present):
    if present:
        package = types.ModuleType('notification')
        package.__path__ = []
        module = types.ModuleType('notification.actions_handlers')
        module.NotificationsActionsHandlers = _Handlers
        package.actions_handlers = module
        sys.modules['notification'] = package
        sys.modules['notification.actions_handlers'] = module
    else:
        sys.modules.pop('notification', None)
        sys.modules.pop('notification.actions_handlers', None)


def _notices(handlers=True, page=False, can_start=True, places=None):
    from battle_conquest.notices import Notices

    _with_handlers(handlers)
    pushed = []
    session = _Session()
    account = _Account()
    places = places or _places()
    site = _Site(places, can_start)
    notices = Notices(session, site, places, account, _Page(page),
                      push=lambda text, warning=False: pushed.append((text, warning)) or True)
    notices.install()
    return notices, session, account, site, places, pushed


def check_notices_texts():
    from battle_conquest.notices import ACTION, ended_text, not_linked_text

    clickable = not_linked_text(True, False)
    check('a clickable notice carries the link action', 'href="event:%s"' % ACTION in clickable)
    check('and says battles are not sent until then', 'not sent' in clickable)
    check('without a link but with the page, it sends the player to the mods list',
          'mods list' in not_linked_text(False, True) and 'href' not in not_linked_text(False, True))
    check('without either, it names the two mods the page needs',
          'modsSettingsApi' in not_linked_text(False, False) and 'modsListApi' in not_linked_text(False, False))

    class _Destination(object):
        modes = ['random', 'onslaught']

    check('a link made says which battles leave', 'random, onslaught battles' in ended_text(_Destination(), True))
    check('a link that gave up offers to try again', 'event:%s' % ACTION in ended_text(None, True))
    check('but not where nothing could catch the click', 'href' not in ended_text(None, False))


def check_notices_remind():
    notices, session, account, site, places, pushed = _notices()
    check('the actions handler is patched', _Handlers.__dict__['handleAction'] is not ORIGINAL_HANDLE)
    check('so the notice can carry a link', notices.clickable)
    check('nothing is said before an account is in the garage', pushed == [] and session.later == [])

    account.log_in()
    check('nothing in the very frame the garage shows', pushed == [])
    session.run_later()
    check('then the garage says the game is not linked', len(pushed) == 1 and 'not linked' in pushed[0][0])
    check('as information, not as a warning', pushed[0][1] is False)

    account.log_in('500999999')
    session.run_later()
    check('once a session, not once per account switch', len(pushed) == 1)

    places.remember('Battle-Conquest', ['random'], 'e' * 64)
    check('a linked game is never reminded', notices.remind() is False and len(pushed) == 1)
    session.real.close()
    check('stopping gives the client its handler back', _Handlers.__dict__['handleAction'] is ORIGINAL_HANDLE)


def check_notices_click():
    notices, session, account, site, places, pushed = _notices()
    handlers = _Handlers()
    from battle_conquest.notices import ACTION

    check('another action still reaches the client',
          handlers.handleAction(None, 1, 2, 'openShop') == 'the client handled openShop')
    check('the link action is the mod\'s alone', handlers.handleAction(None, 1, 2, ACTION) is None)
    check('and it starts the linking', site.started == 1)
    check('the action is found however it is passed',
          handlers.handleAction(None, 1, 2, actionName=ACTION) is None and site.started == 2)

    site.end(None)
    check('a linking that gave up is said, as a warning', pushed[-1][1] is True and 'did not complete' in pushed[-1][0])

    class _Destination(object):
        modes = ['onslaught']

    site.end(_Destination())
    check('a link made is said too', pushed[-1][1] is False and 'linked' in pushed[-1][0])
    check('success is announced once despite change and done both firing', len(pushed) == 2)

    places.remember('Battle-Conquest', ['random'], 'f' * 64)
    started = site.started
    notices.clicked()
    check('a click once linked starts nothing', site.started == started)
    check('and explains why the old link no longer starts linking',
          'already linked' in pushed[-1][0] and pushed[-1][1] is False)
    before = len(pushed)
    site.changed()
    check('verification of an unchanged link does not repeat success', len(pushed) == before)
    places.forget()
    site.changed()
    check('unlinking does not announce a browser timeout', len(pushed) == before)
    places.remember('Battle-Conquest', ['onslaught'], 'e' * 64)
    site.changed()
    check('a link from the settings page is also announced once',
          len(pushed) == before + 1 and 'onslaught battles' in pushed[-1][0])
    session.real.close()

    refused, session, _, site, _, pushed = _notices(can_start=False)
    refused.clicked()
    check('a click that cannot start says why', pushed and pushed[-1][1] is True and 'garage' in pushed[-1][0])
    session.real.close()


def check_notices_without_handler():
    notices, session, account, site, places, pushed = _notices(handlers=False, page=True)
    check('a client with no actions handler is left alone', not notices.clickable
          and _Handlers.__dict__['handleAction'] is ORIGINAL_HANDLE)
    account.log_in()
    session.run_later()
    check('and its notice carries no dead link', len(pushed) == 1 and 'href' not in pushed[0][0])
    check('but sends the player to the page', 'mods list' in pushed[0][0])
    session.real.close()


def check_notices_revoked_link():
    from battle_conquest.notices import ACTION

    for when in ('before login', 'before reminder', 'after reminder'):
        places = _places()
        places.remember('Battle-Conquest', ['random'], 'e' * 64)
        notices, session, account, site, _, pushed = _notices(places=places)
        try:
            if when != 'before login':
                account.log_in()
            if when == 'after reminder':
                session.run_later()
                check('a still-linked startup stays quiet', pushed == [])
            places.forget()
            site.changed()
            site.changed()
            check('revocation does not push into a garage still loading', pushed == [])
            if when == 'before login':
                check('a revoked link waits for login before scheduling a notice', session.later == [])
                account.log_in()
            session.run_later()
            check('a revoked link offers to link again once, including a slow response',
                  len(pushed) == 1 and 'not linked' in pushed[0][0]
                  and 'event:%s' % ACTION in pushed[0][0])
            notices.clicked()
            check('the reminder starts a new linking attempt', site.started == 1)
        finally:
            session.real.close()


def check_notices_dismiss_reminders():
    from battle_conquest.notices import dismiss_reminders, not_linked_text
    _with_handlers(True)

    class _Item(object):
        def __init__(self, key, text):
            self.key = key
            self.text = text

        def getListVO(self):
            return {'message': {'message': self.text}}

        def getType(self):
            return 1

        def getID(self):
            return self.key

    class _Model(object):
        def __init__(self):
            self.items = [_Item(1, not_linked_text(True, False)), _Item(2, 'Game reward'),
                          _Item(3, 'Another mod: not linked'), _Item(4, not_linked_text(False, True))]
            self.collection = self
            self.removed = []

        def getListIterator(self, typesRange):
            check('only system-message notifications are examined', typesRange == (1,))
            return iter(self.items)

        def removeNotification(self, kind, key):
            self.removed.append((kind, key))
            self.items[:] = [item for item in self.items if item.key != key]

    mvc = types.ModuleType('notification.NotificationMVC')
    settings = types.ModuleType('notification.settings')
    model = _Model()
    mvc.g_instance = type('MVC', (object,), {'getModel': lambda self: model})()
    settings.NOTIFICATION_TYPE = type('Types', (object,), {'MESSAGE': 1})
    sys.modules['notification.NotificationMVC'] = mvc
    sys.modules['notification.settings'] = settings
    try:
        dismiss_reminders()
        check('all obsolete mod reminders are removed and other history stays',
              model.removed == [(1, 1), (1, 4)] and [item.key for item in model.items] == [2, 3])
        mvc.g_instance.getModel = lambda: None
        check('a notification centre not yet created is harmless', dismiss_reminders() is None)
    finally:
        del sys.modules['notification.NotificationMVC']
        del sys.modules['notification.settings']
    check('a client without removal support is harmless too', dismiss_reminders() is None)
