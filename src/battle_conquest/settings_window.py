"""The mod's page in izeberg's modsSettingsApi window.

Everything the player can do with this mod is here: link it to their
Battle-Conquest account, see that battles are leaving, pause sending, or
unlink. There is nothing else to set -- what is sent is decided by the site,
which says which modes it scores when the link is made.

Optional, as both APIs are: they come with most modpacks and are not shipped
with this mod. Without them this does nothing, and the garage notice
(notices.py) is how the player links instead.

Two behaviours of the API (1.7) shape this:

  - The page is a template of labels and buttons. A label that names a varName
    gets a button, and the click comes back as that varName. Registering a new
    template changes future opens; Aslain's reloadModTemplate redraws it live.
  - Callbacks are added to an event and never removed by the API, so every
    reload of this package would stack one. The session removes its own on
    close, and a callback that outlives its session does nothing.
"""
import logging

from battle_conquest.i18n import tr, locale
import time

from battle_conquest import mod_updates

_logger = logging.getLogger('battle_conquest.settings_window')

LINKAGE = 'eu.battle-conquest'

NAME = 'Battle-Conquest'

# How often the page looks at the link and the sender for something new to say.
_CHECK_SECONDS = 2.0

_SPACER = 12

LINK_VAR = 'link'
UNLINK_VAR = 'unlink'
CANCEL_VAR = 'cancelLink'
PAGE_VAR = 'openPage'

_LINK_TOOLTIP = ('{HEADER}Link{/HEADER}{BODY}Opens your browser on Battle-Conquest, where you confirm with '
                 'your account: nothing to type, no file to create. Your Wargaming account has to be linked '
                 'on the site first.{/BODY}')

_UNLINK_TOOLTIP = ('{HEADER}Unlink{/HEADER}{BODY}This game stops sending your battles and forgets its key. '
                   'To revoke the key on the site as well, open your page there.{/BODY}')

def link_label(linked, running):
    """The link line: what it is, or where the linking is up to."""
    if linked:
        return tr(u'Account: linked')
    if running:
        return tr(u'Account: confirm in your browser')
    return tr(u'Account: not linked')


def modes_label(modes, enabled):
    if not enabled:
        return tr(u'Sending: paused')
    if not modes:
        return tr(u'Sending: nothing yet')
    return tr(u'Sending: %s battles') % u', '.join(tr(mode) for mode in modes)


def last_sent_label(last_sent, last_result):
    """What the last batch came to, in one line."""
    if last_sent is None or not last_result:
        return tr(u'Last sent: nothing this session')
    when = time.strftime('%H:%M', time.localtime(last_sent))
    code = last_result.get('code')
    if code != 200:
        return tr(u'Last sent: %s, not taken (HTTP %s), will try again') % (when, code or tr('no answer'))
    accepted = last_result.get('accepted')
    if accepted is None:
        return tr(u'Last sent: %s, %d battle(s)') % (when, last_result.get('battles') or 0)
    parts = [tr(u'%s accepted') % accepted]
    if last_result.get('duplicates'):
        parts.append(tr(u'%s already known') % last_result['duplicates'])
    if last_result.get('rejected'):
        parts.append(tr(u'%s rejected') % last_result['rejected'])
    return tr(u'Last sent: %s, %s') % (when, u', '.join(parts))


def waiting_label(count):
    if count == 1:
        return tr(u'Waiting to be sent: 1 battle')
    return tr(u'Waiting to be sent: %d battles') % count


def _heading(templates, text):
    return templates.createLabel(text.upper())


def _button_line(templates, text, var, button, tooltip=None):
    # A label with a button: the API draws one on any component that names a
    # varName, which is what the button's callback reports.
    return dict(templates.createLabel(text, tooltip=tooltip), varName=var,
                button=templates.createButton(width=90, height=24, text=button))


def link_line(templates, linked, running):
    text = link_label(linked, running)
    if linked:
        return _button_line(templates, text, UNLINK_VAR, tr('Unlink'), tr(_UNLINK_TOOLTIP))
    if running:
        return _button_line(templates, text, CANCEL_VAR, tr('Cancel'))
    return _button_line(templates, text, LINK_VAR, tr('Link'), tr(_LINK_TOOLTIP))


def template(state, templates=None):
    """The API's page for a State."""
    if templates is None:
        from gui.modsSettingsApi import templates
    account = [
        _heading(templates, tr('Account')),
        link_line(templates, state.linked, state.running),
        templates.createLabel(modes_label(state.modes, state.enabled)) if state.linked
        else templates.createEmpty(_SPACER),
        templates.createEmpty(_SPACER),
        _button_line(templates, tr(u'Your battles on the site'), PAGE_VAR, tr('Open')),
    ]
    sending = [
        _heading(templates, tr('Sending')),
        templates.createLabel(state.last),
        templates.createLabel(waiting_label(state.waiting)),
        templates.createLabel(tr('Reports isolated: %d. See game.log.') % state.isolated)
        if state.isolated else templates.createEmpty(0),
        templates.createEmpty(_SPACER),
        _heading(templates, tr('Mod updates')),
        templates.createLabel(state.update),
    ]
    return {'modDisplayName': NAME, 'enabled': state.enabled,
            'column1': account, 'column2': sending}


class State(object):
    """What the page shows, compared as a whole to know when to redraw it."""

    def __init__(self, linked=False, running=False, modes=(), enabled=True, last=u'', waiting=0, update=u'', isolated=0, scope=None):
        self.linked = linked
        self.running = running
        self.modes = tuple(modes)
        self.enabled = enabled
        self.last = last or last_sent_label(None, None)
        self.waiting = waiting
        self.isolated = isolated
        self.update = update
        self.language = locale()
        self.scope = scope

    def key(self):
        return (self.linked, self.running, self.modes, self.enabled, self.last, self.waiting, self.update, self.language, self.isolated, self.scope)

    def __eq__(self, other):
        return isinstance(other, State) and self.key() == other.key()

    def __ne__(self, other):
        return not self == other


class SettingsWindow(object):

    def __init__(self, session, site, destinations, sender=None):
        self._session = session
        self._site = site
        self._destinations = destinations
        self._sender = sender
        self._state = None
        self._alive = True
        self._api = None
        self._templates = None
        self._redraw_pending = False
        self._preview_enabled = None
        self._publishing = False
        self._live_api = None
        self._live_handler = None
        self._window_handler = self._button_handler = None
        self._scope_token = object()

    @property
    def available(self):
        """Whether the page exists, which is to say modsSettingsApi is installed."""
        return self._api is not None

    def install(self):
        try:
            from gui.aslainMenu import g_modsSettingsApi, templates
        except ImportError:
            try:
                from gui.modsSettingsApi import g_modsSettingsApi, templates
            except ImportError:
                _logger.info('modsSettingsApi not installed, so no settings page')
                return
        self._api = g_modsSettingsApi
        self._templates = templates
        self._state = self.state()
        self._register()
        self._session.on_close(self._remove)
        self._follow_live_settings()
        self._site.on_change(self._check_state)
        if self._sender is not None:
            self._sender.on_change(self._check_state)
        self._session.repeat(_CHECK_SECONDS, self._check_state)
        _logger.info('registered in modsSettingsApi as %s', LINKAGE)

    def _scope(self):
        current = self._destinations.current
        return (self._destinations.identity(), current.url if current else None,
                current.secret if current else None)

    def _scoped(self, callback):
        scope, token = self._state.scope, self._scope_token
        def active(*args, **kwargs):
            if (self._alive and token is self._scope_token
                    and self._scope() == scope):
                return callback(*args, **kwargs)
        return active

    def state(self):
        current = self._destinations.current
        linked = self._destinations.linked
        sender = self._sender
        blocked = current is not None and current.blocked
        return State(linked=linked, scope=self._scope(),
                     running=self._site.running,
                     modes=current.modes if current is not None else (),
                     # Ticked while unlinked: the box is about sending, and an
                     # unticked box on a page saying "not linked" reads as the
                     # reason nothing is sent.
                     enabled=self._destinations.enabled if linked else True,
                     last=(tr('Link suspended: link this account again. Reports retained.') if blocked
                           else last_sent_label(getattr(sender, 'last_sent', None),
                                                getattr(sender, 'last_result', None))),
                     isolated=sender._queue.isolated() if sender is not None and hasattr(sender, '_queue') else 0,
                     waiting=sender.waiting() if sender is not None else 0,
                     update=mod_updates.text(getattr(self._site, 'mod_update', None),
                                             getattr(self._site, 'version', '')))

    def _check_state(self):
        if not self._alive:
            return
        state = self.state()
        if state == self._state:
            return
        if self._state is not None and state.scope != self._state.scope:
            self._preview_enabled = None
            self._scope_token = object()
        self._state = state
        # A new template replaces the page; its callbacks are added again, so
        # the ones already on the API's events come off first.
        self._unregister()
        self._register()
        if not self._redraw_pending:
            self._redraw_pending = True
            # Never remove Flash controls while their click/Apply event is
            # still on the stack. Coalesce changes until the next game frame.
            self._session.callback(0.0, self._redraw)

    def _redraw(self):
        self._redraw_pending = False
        if not self._alive:
            return
        if self._state.scope != self._scope():
            self._check_state()
            return
        reload_template = getattr(self._instance(), 'reloadModTemplate', None)
        if callable(reload_template):
            page = template(self._state, self._templates)
            # A redraw must not undo a switch the player has changed but has
            # not yet committed with Apply. Stored settings still describe
            # the sender's actual state until then.
            if self._preview_enabled is not None:
                page['enabled'] = self._preview_enabled
            reload_template(LINKAGE, page)

    def _follow_live_settings(self):
        api = self._instance()
        closed = getattr(api, 'onWindowClosed', None)
        if not (callable(getattr(api, 'registerLiveSettingsChange', None))
                and callable(getattr(api, 'unregisterLiveSettingsChange', None))
                and hasattr(closed, '__iadd__')):
            return
        self._live_api = api
        self._register_live_settings()
        self._session.subscribe(closed, self._on_window_closed)

    def _register_live_settings(self):
        if self._live_api is None:
            return
        if self._live_handler is not None:
            self._live_api.unregisterLiveSettingsChange(LINKAGE, self._live_handler)
        self._live_handler = self._scoped(self._on_live_window)
        self._live_api.registerLiveSettingsChange(LINKAGE, self._live_handler)

    def _on_live_window(self, linkage, raw):
        if (self._alive and self._state.scope == self._scope()
                and linkage == LINKAGE and isinstance(raw, dict)):
            enabled = raw.get('enabled')
            if isinstance(enabled, bool):
                self._preview_enabled = enabled

    def _on_window_closed(self):
        self._preview_enabled = None

    def _register(self):
        self._window_handler = self._scoped(self._on_window)
        self._button_handler = self._scoped(self._on_button)
        self._api.setModTemplate(LINKAGE, template(self._state, self._templates),
                                 self._window_handler, self._button_handler)
        self._register_live_settings()
        # The API keeps its own copy of every value and sends it back as the
        # player's choice, so it is set to the truth first.
        self._publishing = True
        try:
            self._api.updateModSettings(LINKAGE, {'enabled': self._state.enabled})
        finally:
            self._publishing = False

    def _on_window(self, linkage, raw):
        if (self._publishing or not self._alive or linkage != LINKAGE or not isinstance(raw, dict)
                or self._state.scope != self._scope()):
            return
        enabled = raw.get('enabled')
        if isinstance(enabled, bool):
            self._preview_enabled = None
        if isinstance(enabled, bool) and self._destinations.set_enabled(enabled):
            _logger.info('sending battles %s', 'resumed' if enabled else 'paused')
            self._check_state()

    def _on_button(self, linkage, var_name, value=None):
        if not self._alive or linkage != LINKAGE or self._state.scope != self._scope():
            return
        if var_name == LINK_VAR:
            self._site.start()
        elif var_name in (UNLINK_VAR, CANCEL_VAR):
            self._site.unlink()
        elif var_name == PAGE_VAR:
            from battle_conquest.site_link import open_url
            open_url(self._site.page)
        else:
            return
        self._check_state()

    def _remove(self):
        self._alive = False
        if self._live_api is not None:
            try:
                self._live_api.unregisterLiveSettingsChange(LINKAGE, self._live_handler)
            except Exception:
                _logger.debug('could not unregister live settings', exc_info=True)
        self._unregister()

    def _unregister(self):
        instance = self._instance()
        for name, handler in (('onSettingsChanged', self._window_handler), ('onButtonClicked', self._button_handler)):
            event = getattr(instance, name, None)
            if handler is None:
                continue
            try:
                event -= handler
            except Exception:
                _logger.debug('could not unregister %s', name, exc_info=True)

    def _instance(self):
        # Recent builds expose the internal API directly; older ones wrap it.
        return getattr(self._api, '_ModsSettingsApi__instance', self._api)


def install(session, site, destinations, sender=None):
    window = SettingsWindow(session, site, destinations, sender)
    window.install()
    return window
