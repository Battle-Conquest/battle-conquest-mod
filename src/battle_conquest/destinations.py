"""Where a captured battle is sent: Battle-Conquest, and nowhere else.

One destination, at a fixed address. The mod this one grew out of let the
player name further sites and type their URLs; that is gone on purpose. A
player who has to find and type an address makes a mistake no error message
can explain, and the one thing worth optimising on this path is that nothing
is typed at all. Linking (site_link.py) writes the destination down.

Why a file of its own
---------------------
Because it carries a secret. Nothing else of the mod reads it, and no other
mod's settings window mirrors it.

Why the secret is drawn here and never received
-----------------------------------------------
A secret is a proof of identity, not a password. It is drawn in the client and
only its SHA-256 ever leaves the machine, so a site that is breached leaks
nothing that can report battles under somebody else's name -- and the whole
worth of a reported battle is that nobody can invent one.

Why the site says which modes it wants
--------------------------------------
Nothing is gained by sending a site a battle of a mode it does not score, and
a copy of somebody's play history sitting where it serves no purpose is a cost
with no upside. The site declares what it scores when the link is made, and is
sent that alone.
"""
import binascii
import errno
import hashlib
import json
import logging
import os

from battle_conquest import config

_logger = logging.getLogger('battle_conquest.destinations')

STORE = os.path.join(config.CONFIG_DIR, 'link.json')

SCHEMA = 1

LABEL = 'Battle-Conquest'

BATTLES_PATH = '/api/mod/battles'

# Reports identify a Wargaming account. In the clear they are readable by
# anyone on the way, so a destination that is not https is refused rather than
# downgraded -- silently sending them anyway would be the worst of the three.
_REQUIRED_SCHEME = 'https://'


def new_secret():
    return binascii.hexlify(os.urandom(32))


def secret_hash(secret):
    return hashlib.sha256(secret).hexdigest()


def battles_url(site=None):
    """Where the site takes battles."""
    return (site or config.SITE).rstrip('/') + BATTLES_PATH


def valid_url(url):
    """Whether a destination's URL is one we will post to."""
    if not isinstance(url, basestring):
        return False
    url = url.strip()
    if not url.startswith(_REQUIRED_SCHEME):
        return False
    # Something has to follow the scheme, and a space in a URL means it was
    # hand-typed into the wrong field.
    rest = url[len(_REQUIRED_SCHEME):]
    return bool(rest) and ' ' not in rest


def clean_modes(raw, known):
    """The modes the site asked for, keeping only those this mod knows.

    An unknown mode is dropped rather than passed on: it would be a mode the
    capture never produces, so asking for it would wait forever and never be
    told why.
    """
    if not isinstance(raw, (list, tuple)):
        return []
    out = []
    for mode in raw:
        if mode in known and mode not in out:
            out.append(mode)
    return out


class Destination(object):
    """The place battles are sent, and what it is allowed to receive."""

    def __init__(self, url, label='', enabled=False, modes=(), secret=None):
        self.url = url.strip() if isinstance(url, basestring) else ''
        self.label = label or LABEL
        self.enabled = bool(enabled)
        self.modes = list(modes)
        self.secret = secret
        self.owner = None
        self.blocked = None

    def wants(self, mode):
        """Whether the destination is owed a battle of this mode."""
        return self.enabled and bool(self.secret) and mode in self.modes

    def hash(self):
        """What the player carries to the site: never the secret itself."""
        return secret_hash(self.secret) if self.secret else None

    def as_dict(self):
        return {'schema': SCHEMA, 'url': self.url, 'label': self.label, 'enabled': self.enabled,
                'modes': list(self.modes), 'secret': self.secret}

    def __repr__(self):
        return '<Destination %s %s>' % (self.label, 'on' if self.enabled else 'off')


def read(payload, known_modes, url):
    """The destination a stored payload describes, or None when it is unusable.

    Said in the log either way: a player whose battles reach no site has no
    other way of telling a file that was never written from one this cannot
    use.
    """
    if not isinstance(payload, dict):
        _logger.warning('the link file holds %s rather than an object; link the site again',
                        type(payload).__name__)
        return None
    if payload.get('schema') != SCHEMA:
        _logger.warning('the link file declares schema %r, and this mod reads %d; link the site again',
                        payload.get('schema'), SCHEMA)
        return None
    stored = payload.get('url')
    if not valid_url(stored) or stored.strip() != url:
        # A secret made for one site is never presented to another. The case
        # this is written for is a dev build pointed at a local server: the
        # player's real secret must not leave for it.
        _logger.warning('the link file is for %r, not %s; link the site again', stored, url)
        return None
    secret = payload.get('secret')
    if not (isinstance(secret, basestring) and len(secret) == 64):
        _logger.warning('the link file holds no usable secret; link the site again')
        secret = None
    return Destination(url=url,
                       label=payload.get('label') or LABEL,
                       enabled=payload.get('enabled'),
                       modes=clean_modes(payload.get('modes'), known_modes),
                       secret=secret)


class Destinations(object):
    """Links keyed by site, region and WG account. Legacy keys await /me."""

    def __init__(self, known_modes, store=STORE, url=None, account=None):
        from battle_conquest.account import current_account_id
        self._store = store
        self._known = tuple(known_modes)
        self.url = url or battles_url()
        self._account = account if account is not None else current_account_id
        self._links = {}
        self._suspensions = []
        self._foreign = []
        self._foreign_legacy = []
        self.legacy = None
        self._writable = True
        self._read()

    def identity(self):
        from battle_conquest.battle_owner import account_id
        value = self._account() if callable(self._account) else getattr(self._account, 'account', None)
        identity = account_id(value)
        return (config.REGION, identity) if identity else None

    def _read(self):
        from battle_conquest.local_store import load_json
        try:
            payload = load_json(self._store)
        except (IOError, OSError) as problem:
            if getattr(problem, 'errno', None) == errno.ENOENT:
                _logger.info('no link file at %s: not linked yet', self._store)
            else:
                self._writable = False
                _logger.warning('could not open link file; not linked')
            return
        except ValueError:
            self._writable = False
            _logger.warning('link file is not readable JSON; preserved, not linked')
            return
        if not isinstance(payload, dict) or payload.get('schema') not in (1, 2):
            self._writable = False
            _logger.warning('unsupported link schema; this mod reads 1 and 2')
            return
        if payload['schema'] == 1:
            if payload.get('url') != self.url:
                self._foreign_legacy.append(payload)
            else:
                self.legacy = read(payload, self._known, self.url)
            return
        entries = payload.get('links')
        if not isinstance(entries, list):
            self._writable = False
            return
        # Keep entries for other sites too, but never expose their secret to
        # the active build. Switching a dev build must not erase production.
        self._foreign = [entry for entry in entries if isinstance(entry, dict)
                         and entry.get('url') != self.url]
        for entry in self._foreign:
            _logger.info('link for %s preserved; not used by this build', entry.get('url'))
        from battle_conquest.battle_owner import account_id, REGIONS
        for entry in entries:
            if not isinstance(entry, dict) or entry.get('url') != self.url:
                continue
            owner = entry.get('owner')
            identity = account_id(owner.get('id')) if isinstance(owner, dict) else None
            region = owner.get('region') if isinstance(owner, dict) else None
            if not identity or region not in REGIONS:
                self._writable = False
                continue
            destination = read(entry, self._known, self.url)
            if destination is not None:
                destination.owner = (region, identity)
                destination.blocked = entry.get('blocked')
                self._links[(region, identity)] = destination
        legacy_entries = payload.get('legacy_links', [])
        if not isinstance(legacy_entries, list):
            self._writable = False
            return
        legacy = payload.get('legacy')
        if isinstance(legacy, dict):
            legacy_entries = [legacy] + legacy_entries
        candidates = [entry for entry in legacy_entries
                      if isinstance(entry, dict) and entry.get('url') == self.url]
        selected = candidates[0] if candidates else None
        self._foreign_legacy = [entry for entry in legacy_entries
                                if isinstance(entry, dict) and entry is not selected]
        if selected is not None:
            self.legacy = read(selected, self._known, self.url)

    def for_owner(self, owner):
        return self._links.get(tuple(owner)) if owner else None

    @property
    def current(self):
        return self.for_owner(self.identity())

    @property
    def linked(self):
        current = self.current
        return current is not None and bool(current.secret) and not current.blocked

    @property
    def enabled(self):
        return self.linked and self.current.enabled

    def all(self):
        return [self.current] if self.current is not None else []

    def wanting(self, mode):
        return [d for d in self.all() if d.wants(mode)]

    def modes(self):
        current = self.current
        # A broken proof suspends delivery, not capture of this known owner.
        return list(current.modes) if current and current.enabled and current.secret else []

    def remember(self, label, modes, secret, enabled=True, owner=None):
        self._check_writable()
        identity = tuple(owner) if owner is not None else self.identity()
        from battle_conquest.battle_owner import account_id, REGIONS
        if (identity is None or len(identity) != 2 or identity[0] not in REGIONS
                or account_id(identity[1]) != identity[1]):
            raise ValueError('a verified owner is required to remember a link')
        destination = Destination(self.url, label, enabled,
                                  clean_modes(modes, self._known), secret)
        destination.owner = identity
        previous, legacy = self._links.get(identity), self.legacy
        self._links[identity] = destination
        if self.legacy is not None and self.legacy.secret == secret:
            self.legacy = None
        try:
            self.save()
        except (IOError, OSError):
            self.legacy = legacy
            if previous is None:
                self._links.pop(identity, None)
            else:
                self._links[identity] = previous
            raise
        return destination

    def set_enabled(self, enabled):
        self._check_writable()
        current = self.current
        if current is None or current.enabled == bool(enabled):
            return False
        current.enabled = bool(enabled)
        self.save()
        return True

    def on_suspend(self, callback):
        self._suspensions.append(callback)

    def block(self, owner, secret, reason):
        self._check_writable()
        current = self.for_owner(owner)
        if current is not None and current.secret == secret and current.blocked != reason:
            current.blocked = reason
            try:
                self.save()
            finally:
                for callback in list(self._suspensions):
                    try:
                        callback()
                    except Exception:
                        _logger.exception('a link suspension listener failed')

    def forget(self, owner=None):
        self._check_writable()
        identity = tuple(owner) if owner is not None else self.identity()
        if identity not in self._links:
            return False
        del self._links[identity]
        self.save()
        return True

    def _check_writable(self):
        if not self._writable:
            raise IOError('the unreadable link file is preserved; restore it before linking')

    def save(self):
        self._check_writable()
        from battle_conquest.local_store import save_json
        entries = list(getattr(self, '_foreign', []))
        for (region, identity), destination in sorted(self._links.items()):
            entry = destination.as_dict()
            entry['owner'] = {'id': int(identity), 'region': region}
            entry['blocked'] = destination.blocked
            entries.append(entry)
        save_json(self._store, {'schema': 2, 'links': entries,
                               'legacy': self.legacy.as_dict() if self.legacy else None,
                               'legacy_links': self._foreign_legacy})


def install(session, known_modes, store=None, account=None):
    destinations = Destinations(known_modes, store=store or STORE, account=account)
    if destinations.legacy is not None:
        _logger.info('legacy Battle-Conquest link awaits owner verification')
    current = destinations.current
    if current is not None:
        _logger.info('%s (%s): %s, for %s', current.label, current.url,
                     'sending' if current.enabled else 'paused', ', '.join(current.modes))
    return destinations
