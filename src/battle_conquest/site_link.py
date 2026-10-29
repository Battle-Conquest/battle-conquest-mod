"""One click, in the garage, to send battles to Battle-Conquest.

This draws the secret, opens the player's own browser on the site's linking
page carrying only its SHA-256, waits for the site to accept it, and writes the
destination down itself. Nothing is typed and nothing is copied.

The properties that matter:

  - the secret is drawn in the client and never travels. The site stores a
    hash, so a site that is breached leaks nothing that can report battles.
  - the player's own browser does the signing in. The game's built-in browser
    only opens the domains Wargaming lists and would refuse this one with a 418
    before a request left.
  - the Wargaming account is named in the URL so the site can refuse a link to
    the wrong account. Left unchecked, every report would be rejected later for
    an account mismatch, which is a silent failure rather than a readable one.

Once linked, the site is asked again now and then who this secret is. That is
how a link revoked on the site's own page stops being shown as linked here,
and how a mode the site starts scoring after the link was made reaches the
capture without the player linking again.
"""
import json
import logging

from battle_conquest import config, i18n, mod_updates
from battle_conquest.battle_owner import account_id, REGIONS
from battle_conquest.quest_details import header as capabilities_header
from battle_conquest.destinations import LABEL, new_secret, secret_hash, clean_modes

_logger = logging.getLogger('battle_conquest.site_link')

LINK_PATH = '%s/mod/link?key=%s&account=%s'
ME_PATH = '%s/api/mod/me'
PAGE_PATH = '%s/my-mod'

# The player is in a browser, and three seconds is slow enough to be free and
# quick enough not to be noticed.
_POLL_SECONDS = 3.0

# How long an attempt waits for the player before giving up. A browser left
# open on a sign-in page must not leave a poll running for the session.
_GIVE_UP_SECONDS = 600.0

# Check a stored link on the next frame, after the page and notices have
# subscribed. Waiting thirty seconds lets the garage's first reminder pass
# while a revoked key still looks linked.
_VERIFY_SECONDS = 1800.0


def read_me(response):
    """(label, modes) from GET /api/mod/me, or None while nothing is linked.

    401 is the ordinary waiting state, not an error: the player has not clicked
    yet. Anything unreadable is treated the same way, because a site answering
    something unexpected is a site we should keep waiting on rather than
    declare linked.
    """
    if getattr(response, 'responseCode', None) != 200:
        return None
    body = getattr(response, 'body', None)
    if not body:
        return None
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    modes = payload.get('modes')
    if not isinstance(modes, (list, tuple)) or not modes:
        # A site that wants nothing would be written down owed nothing, and the
        # capture would keep every battle for no one.
        return None
    label = payload.get('label')
    if not isinstance(label, basestring) or not label.strip():
        label = LABEL
    return label.strip(), list(modes)


def me_owner(response):
    try:
        payload = json.loads(response.body)
    except (ValueError, TypeError, AttributeError):
        return None
    if not isinstance(payload, dict):
        return None
    identity = account_id(payload.get('account_id'))
    region = payload.get('region')
    return (region, identity) if identity and region in REGIONS else None


def open_url(url):
    """A page in the player's own browser."""
    import BigWorld

    _logger.info('opening %s', url)
    BigWorld.wg_openWebBrowser(url)


class Attempt(object):
    """One linking attempt: a secret drawn, a browser opened, and a poll."""

    def __init__(self, session, destinations, account, site=None, on_done=None, version='', on_update=None):
        self._session = session
        self._destinations = destinations
        self._account = account
        self._site = (site or config.SITE).rstrip('/')
        self._on_done = on_done
        self._version = version
        self._on_update = on_update
        self._secret = new_secret()
        self._left = int(_GIVE_UP_SECONDS / _POLL_SECONDS)
        self._over = False

    def url(self):
        """Where the player's browser is sent."""
        return LINK_PATH % (self._site, secret_hash(self._secret), self._account)

    def start(self):
        open_url(self.url())
        self._session.repeat(_POLL_SECONDS, self._poll)
        _logger.info('linking to %s: opened in the browser', self._site)

    def cancel(self):
        self._over = True

    def _poll(self):
        if self._over:
            return
        self._left -= 1
        if self._left < 0:
            self._finish(None)
            _logger.warning('linking to %s: gave up waiting', self._site)
            return
        self._session.fetch(ME_PATH % self._site, self._answered,
                            headers={'X-Mod-Secret': self._secret, 'X-Mod-Version': self._version,
                                     'X-Mod-Capabilities': capabilities_header()},
                            timeout=config.API_TIMEOUT)

    def _answered(self, response):
        if self._over:
            return
        me = read_me(response)
        if me is None:
            return
        identity = me_owner(response)
        expected = (config.REGION, account_id(self._account))
        if identity != expected or self._destinations.identity() != expected:
            _logger.warning('link not saved: browser account or region differs from game account')
            self._finish(None)
            return
        label, modes = me
        destination = self._destinations.remember(label, modes, self._secret, owner=identity)
        if self._on_update is not None:
            self._on_update(response)
        self._finish(destination)

    def _finish(self, destination):
        self._over = True
        if destination is not None:
            _logger.info('linking to %s: done, owed %s',
                         self._site, ', '.join(destination.modes) or 'nothing')
        if self._on_done is not None:
            self._on_done(destination)


class SiteLink(object):
    """The link as the settings page sees it: linked, being linked, or linkable."""

    def __init__(self, session, destinations, account, site=None, version=''):
        self._session = session
        self._destinations = destinations
        self._account = account
        self._site = (site or config.SITE).rstrip('/')
        self._version = version
        self._attempt = None
        self._listeners = []
        self._endings = []
        self.mod_update = None
        self._destinations.on_suspend(self._changed)

    @property
    def version(self):
        return self._version

    def _read_update(self, response):
        try:
            payload = json.loads(response.body)
        except (ValueError, TypeError, AttributeError):
            payload = None
        destination = self._destinations.current
        language_changed = i18n.accept(payload, getattr(self._account, 'account', None),
                                       destination.secret if destination else None)
        update = mod_updates.read(response, self._version)
        if update != self.mod_update or language_changed:
            self.mod_update = update
            self._changed()

    def on_change(self, callback):
        self._listeners.append(callback)

    def on_done(self, callback):
        """Be told how an attempt ended: callback(destination), None when it gave up.

        Apart from `on_change`, which also fires on a click and an unlink: the
        player is owed a word on how linking ended, and on nothing else.
        """
        self._endings.append(callback)

    @property
    def page(self):
        """The site's page about the mod, where a link is revoked."""
        return PAGE_PATH % self._site

    @property
    def linked(self):
        return self._destinations.linked

    @property
    def running(self):
        return self._attempt is not None

    def install(self):
        self._session.callback(0.0, self.verify)
        self._session.repeat(_VERIFY_SECONDS, self.verify)
        on_change = getattr(self._account, 'on_change', None)
        if on_change is not None:
            on_change(self._account_changed)

    def _account_changed(self):
        if self._attempt is not None:
            self._attempt.cancel()
            self._attempt = None
        self.mod_update = None
        self._changed()
        self.verify()

    def start(self):
        """Begin a linking attempt, unless one is already waiting.

        Refuses without an account rather than guessing one: the site checks it
        against the player's own, and a link made for the wrong account would
        have every report refused afterwards.
        """
        if self._attempt is not None:
            return False
        account = getattr(self._account, 'account', None)
        if not account:
            _logger.warning('linking to %s: no Wargaming account logged in yet; '
                            'open the garage and try again', self._site)
            return False
        self._attempt = Attempt(self._session, self._destinations, account,
                                site=self._site, on_done=self._done, version=self._version,
                                on_update=self._read_update)
        self._attempt.start()
        self._changed()
        return True

    def unlink(self):
        """Forget the link here, and stop any attempt still waiting.

        The site cannot be told from here: its API takes battles and answers
        who a secret is, nothing more. The secret it holds proves nothing once
        this client has forgotten it, and the site's page revokes it.
        """
        if self._attempt is not None:
            self._attempt.cancel()
            self._attempt = None
        forgot = self._destinations.forget()
        self.mod_update = None
        if forgot:
            _logger.info('unlinked from %s; revoke the key on %s too', self._site, self.page)
        self._changed()
        return forgot

    def verify(self):
        """Verify an owned key, or migrate the legacy key using the site's owner."""
        legacy = self._destinations.legacy
        destination = legacy or self._destinations.current
        if destination is None or not destination.secret or self._attempt is not None:
            return
        secret, identity = destination.secret, destination.owner

        def answered(response):
            current = (self._destinations.legacy if legacy is not None
                       else self._destinations.for_owner(identity))
            if current is not destination or current.secret != secret:
                return
            code = getattr(response, 'responseCode', None)
            if code == 401:
                if legacy is not None:
                    self._destinations.legacy = None
                    self._destinations.save()
                else:
                    self._destinations.forget(owner=identity)
                self.mod_update = None
                self._changed()
                return
            me, owner = read_me(response), me_owner(response)
            if me is None or owner is None:
                return
            if identity is not None and owner != identity:
                self._destinations.block(identity, secret, 'account_mismatch')
                _logger.warning('stored link owner disagrees with /me; link again')
                self._changed()
                return
            label, modes = me
            if legacy is not None:
                existing = self._destinations.for_owner(owner)
                if existing is None:
                    self._destinations.remember(label, modes, secret,
                                                enabled=current.enabled, owner=owner)
                else:
                    # A newer explicit link always wins over a legacy key.
                    self._destinations.legacy = None
                    self._destinations.save()
                self._changed()
            elif sorted(modes) != sorted(current.modes) or label != current.label:
                current.label, current.modes = label, clean_modes(modes, self._destinations._known)
                self._destinations.save()
                self._changed()
            if self._destinations.identity() == owner:
                self._read_update(response)

        self._session.fetch(ME_PATH % self._site, answered,
                            headers={'X-Mod-Secret': secret, 'X-Mod-Version': self._version,
                                     'X-Mod-Capabilities': capabilities_header()},
                            timeout=config.API_TIMEOUT)

    def _done(self, destination):
        self._attempt = None
        self._changed()
        for callback in list(self._endings):
            try:
                callback(destination)
            except Exception:
                _logger.exception('a linking listener failed')

    def _changed(self):
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                _logger.exception('a link listener failed')


def install(session, destinations, account, site=None, version=''):
    sites = SiteLink(session, destinations, account, site=site, version=version)
    sites.install()
    _logger.info('%s is %s', sites._site, 'linked' if sites.linked else 'not linked yet')
    return sites
