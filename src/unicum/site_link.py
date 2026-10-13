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

from unicum import config
from unicum.destinations import LABEL, new_secret, secret_hash

_logger = logging.getLogger('unicum.site_link')

LINK_PATH = '%s/mod/link?key=%s&account=%s'
ME_PATH = '%s/api/mod/me'
PAGE_PATH = '%s/my-mod'

# The player is in a browser, and three seconds is slow enough to be free and
# quick enough not to be noticed.
_POLL_SECONDS = 3.0

# How long an attempt waits for the player before giving up. A browser left
# open on a sign-in page must not leave a poll running for the session.
_GIVE_UP_SECONDS = 600.0

# How soon after the client starts, and how often after that, a link is
# checked with the site. Nothing here is urgent: a revoked link only costs a
# refused batch, which the sender already backs off from.
_VERIFY_DELAY = 30.0
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


def open_url(url):
    """A page in the player's own browser."""
    import BigWorld

    _logger.info('opening %s', url)
    BigWorld.wg_openWebBrowser(url)


class Attempt(object):
    """One linking attempt: a secret drawn, a browser opened, and a poll."""

    def __init__(self, session, destinations, account, site=None, on_done=None):
        self._session = session
        self._destinations = destinations
        self._account = account
        self._site = (site or config.SITE).rstrip('/')
        self._on_done = on_done
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
                            headers={'X-Mod-Secret': self._secret},
                            timeout=config.API_TIMEOUT)

    def _answered(self, response):
        if self._over:
            return
        me = read_me(response)
        if me is None:
            return
        label, modes = me
        self._finish(self._destinations.remember(label, modes, self._secret))

    def _finish(self, destination):
        self._over = True
        if destination is not None:
            _logger.info('linking to %s: done, owed %s',
                         self._site, ', '.join(destination.modes) or 'nothing')
        if self._on_done is not None:
            self._on_done(destination)


class SiteLink(object):
    """The link as the settings page sees it: linked, being linked, or linkable."""

    def __init__(self, session, destinations, account, site=None):
        self._session = session
        self._destinations = destinations
        self._account = account
        self._site = (site or config.SITE).rstrip('/')
        self._attempt = None
        self._listeners = []

    def on_change(self, callback):
        self._listeners.append(callback)

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
        self._session.callback(_VERIFY_DELAY, self.verify)
        self._session.repeat(_VERIFY_SECONDS, self.verify)

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
                                site=self._site, on_done=self._done)
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
        if forgot:
            _logger.info('unlinked from %s; revoke the key on %s too', self._site, self.page)
        self._changed()
        return forgot

    def verify(self):
        """Ask the site who our secret is, and follow what it answers."""
        destination = self._destinations.current
        if destination is None or not destination.secret or self._attempt is not None:
            return
        secret = destination.secret

        def answered(response):
            current = self._destinations.current
            if current is None or current.secret != secret:
                # Linked again or unlinked while the question was out.
                return
            code = getattr(response, 'responseCode', None)
            if code == 401:
                _logger.info('%s no longer knows this link (revoked on the site?); forgetting it',
                             self._site)
                self._destinations.forget()
                self._changed()
                return
            me = read_me(response)
            if me is None:
                # Down, or answering something we cannot read: say nothing
                # about the link either way, and ask again next time.
                return
            label, modes = me
            if sorted(modes) != sorted(current.modes) or label != current.label:
                _logger.info('%s now scores %s', self._site, ', '.join(modes))
                self._destinations.remember(label, modes, secret, enabled=current.enabled)
                self._changed()

        self._session.fetch(ME_PATH % self._site, answered,
                            headers={'X-Mod-Secret': secret}, timeout=config.API_TIMEOUT)

    def _done(self, destination):
        self._attempt = None
        self._changed()

    def _changed(self):
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                _logger.exception('a link listener failed')


def install(session, destinations, account, site=None):
    sites = SiteLink(session, destinations, account, site=site)
    sites.install()
    _logger.info('%s is %s', sites._site, 'linked' if sites.linked else 'not linked yet')
    return sites
