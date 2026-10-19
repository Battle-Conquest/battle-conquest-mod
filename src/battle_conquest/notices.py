"""The garage's notifications: the way to link that needs no other mod.

The settings page lives in modsSettingsApi's window, and that mod is optional:
most modpacks carry it, a fresh client does not. Without it the page's Link
button does not exist, and a mod that cannot be linked sends nothing at all.
unicum.gg-mod never had that problem, because its own AS3 tab in the game's
settings window held the button; this mod has no AS3 any more.

So while the game is not linked, the garage says so once a session, in the
client's own notification centre, with a link that starts the linking: the
same one click through the player's browser as the page's button. Nothing
opens by itself -- the player clicks, or not.

The link is an `event:` anchor, which the notification centre hands to its
actions handler by name. That handler is patched to catch this mod's action
and pass every other one on. Where the client has no such handler, the notice
says what to do instead rather than show a link that does nothing.

How linking ended is said here too, since the browser is where the player last
looked and the garage is where they come back to.
"""
import logging

_logger = logging.getLogger('battle_conquest.notices')

ACTION = 'battle_conquest.link'

# After the garage first shows an account: the notification centre is built
# with the garage, and a message pushed in the same frame can be lost.
_DELAY = 5.0

PREFIX = u'Battle-Conquest: '

NOT_LINKED = u'this game is not linked to your account yet, so your battles are not sent.'


def link_anchor(text=u'Link my account'):
    return u'<a href="event:%s">%s</a>' % (ACTION, text)


def not_linked_text(clickable, page):
    """The notice for a game not linked, by what the player can do about it."""
    if clickable:
        return u'%s%s %s' % (PREFIX, NOT_LINKED, link_anchor())
    if page:
        return u'%s%s Open the mods list, choose Battle-Conquest and click Link.' % (PREFIX, NOT_LINKED)
    return (u'%s%s Install modsSettingsApi and modsListApi (see the mod\'s README), then link it '
            u'from the mods list.' % (PREFIX, NOT_LINKED))


def ended_text(destination, clickable):
    """How linking ended, for the notice that says so."""
    if destination is not None:
        return (u'%slinked. Your %s battles are sent from the garage shortly after they end.'
                % (PREFIX, u', '.join(destination.modes) or u'chosen'))
    again = u' %s' % link_anchor(u'Try again') if clickable else u''
    return u'%slinking did not complete: it was not confirmed in the browser in time.%s' % (PREFIX, again)


def push(text, warning=False):
    """A message in the garage's notification centre; False where there is none."""
    try:
        from gui import SystemMessages
        from gui.shared.notifications import NotificationPriorityLevel
        kind = SystemMessages.SM_TYPE.Warning if warning else SystemMessages.SM_TYPE.Information
        SystemMessages.pushMessage(text, type=kind, priority=NotificationPriorityLevel.MEDIUM)
        return True
    except Exception:
        _logger.debug('could not push a notification', exc_info=True)
        return False


def _actions_handlers():
    """The class the notification centre dispatches clicked actions through, or None."""
    try:
        from notification.actions_handlers import NotificationsActionsHandlers
    except Exception:
        _logger.debug('no notification actions handler in this client', exc_info=True)
        return None
    if not callable(getattr(NotificationsActionsHandlers, 'handleAction', None)):
        return None
    return NotificationsActionsHandlers


class Notices(object):

    def __init__(self, session, site, destinations, account, page=None, push=push):
        self._session = session
        self._site = site
        self._destinations = destinations
        self._account = account
        self._page = page
        self._push = push
        self.clickable = False
        self._said = False

    def install(self):
        holder = _actions_handlers()
        if holder is not None:
            self._session.patch(holder, 'handleAction', self._wrap)
            self.clickable = True
        _logger.info('notices %s', 'carry a link to start linking' if self.clickable
                     else 'cannot carry a link in this client; they say what to do instead')
        self._account.on_change(self._account_changed)
        self._site.on_done(self._ended)
        # A reload in the garage starts with the account already known.
        if getattr(self._account, 'account', None):
            self._account_changed()

    def _wrap(self, original):

        def handleAction(handlers, *args, **kwargs):
            # The action's name comes last, whatever comes before it on a given
            # client: (model, typeID, entityID, actionName) on the ones seen.
            name = kwargs.get('actionName', args[-1] if args else None)
            if name == ACTION:
                self.clicked()
                return None
            return original(handlers, *args, **kwargs)

        return handleAction

    def _account_changed(self):
        if self._said:
            return
        self._said = True
        self._session.callback(_DELAY, self.remind)

    def remind(self):
        """Say the game is not linked, if it still is not."""
        if self._destinations.linked or self._site.running:
            return False
        page = bool(self._page is not None and self._page.available)
        return self._push(not_linked_text(self.clickable, page))

    def clicked(self):
        if self._destinations.linked:
            return
        if not self._site.start() and not self._site.running:
            self._push(u'%sopen the garage with your account first, then try again.' % PREFIX, warning=True)

    def _ended(self, destination):
        self._push(ended_text(destination, self.clickable), warning=destination is None)


def install(session, site, destinations, account, page=None):
    notices = Notices(session, site, destinations, account, page)
    notices.install()
    return notices
