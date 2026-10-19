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
    """The one destination, read from disk and written back.

    Shaped as a collection all the same: the capture and the sender ask it
    which destinations want a mode, and an answer that is a list keeps them
    from having to know there is only ever one.
    """

    def __init__(self, known_modes, store=STORE, url=None):
        self._store = store
        self._known = tuple(known_modes)
        self.url = url or battles_url()
        self._destination = self._read()

    def _read(self):
        try:
            with open(self._store, 'rb') as handle:
                payload = json.load(handle)
        except (IOError, OSError) as problem:
            if getattr(problem, 'errno', None) == errno.ENOENT:
                _logger.info('no link file at %s: not linked yet. Link the site from the mod\'s '
                             'settings page', self._store)
            else:
                _logger.warning('could not open %s (%s); not linked', self._store, problem)
            return None
        except ValueError:
            _logger.warning('%s is not readable JSON; not linked. The file is left as it is '
                            'rather than overwritten, so a hand edit can be undone', self._store)
            return None
        return read(payload, self._known, self.url)

    @property
    def current(self):
        return self._destination

    @property
    def linked(self):
        """Whether battles can be proven to the site: a secret it accepted."""
        return self._destination is not None and bool(self._destination.secret)

    @property
    def enabled(self):
        return self.linked and self._destination.enabled

    def all(self):
        return [self._destination] if self._destination is not None else []

    def wanting(self, mode):
        """The destinations owed a battle of this mode: the site, or nothing."""
        return [destination for destination in self.all() if destination.wants(mode)]

    def modes(self):
        """Every mode the site is owed while sending is on.

        What the capture consults to know whether a battle is worth keeping at
        all: a mode nothing is waiting for is a report nobody will ever read.
        """
        if not self.enabled:
            return []
        return list(self._destination.modes)

    def remember(self, label, modes, secret, enabled=True):
        """Write down the link the player has just made, and return it.

        Replacing the one there rather than keeping both: a second linking
        must not leave a credential nobody will ever present again.
        """
        self._destination = Destination(url=self.url, label=label, enabled=enabled,
                                        modes=clean_modes(modes, self._known), secret=secret)
        self.save()
        return self._destination

    def set_enabled(self, enabled):
        """Pause or resume sending, the link itself left alone."""
        if self._destination is None or self._destination.enabled == bool(enabled):
            return False
        self._destination.enabled = bool(enabled)
        self.save()
        return True

    def forget(self):
        """Drop the link here. The site keeps its copy until it is revoked there."""
        if self._destination is None:
            return False
        self._destination = None
        try:
            os.remove(self._store)
        except (IOError, OSError):
            _logger.debug('could not remove the link file', exc_info=True)
        return True

    def save(self):
        if self._destination is None:
            return
        try:
            directory = os.path.dirname(self._store)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)
            with open(self._store, 'wb') as handle:
                json.dump(self._destination.as_dict(), handle)
        except (IOError, OSError):
            _logger.debug('could not write the link down', exc_info=True)


def install(session, known_modes, store=None):
    # `store` is here so a check can watch what this says about a file it wrote
    # itself. Reassigning the module's STORE would not do: it is a default
    # argument, bound once when the class is defined.
    destinations = (Destinations(known_modes) if store is None
                    else Destinations(known_modes, store=store))
    current = destinations.current
    if current is not None and current.enabled:
        _logger.info('sending battles to %s (%s), for %s', current.label, current.url,
                     ', '.join(current.modes) or 'nothing')
    elif current is not None:
        # Not a failure, and worth a line: a player who sees nothing arrive has
        # no other way of learning that sending is paused.
        _logger.info('linked to %s, but sending is paused', current.label)
    return destinations
