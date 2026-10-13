"""Checks for where battles are sent: one site, and never anything unasked."""

import json
import logging
import os
import tempfile

from checks.common import check

MODES = ('random', 'ranked', 'onslaught', 'stronghold', 'frontline', 'training', 'other')

SECRET = 'a' * 64

URL = 'https://battle-conquest.test/api/mod/battles'

GOOD = {'schema': 1, 'url': URL, 'label': 'Battle-Conquest', 'enabled': True,
        'modes': ['ranked'], 'secret': SECRET}


def _file(payload):
    path = os.path.join(tempfile.mkdtemp(), 'link.json')
    with open(path, 'wb') as handle:
        json.dump(payload, handle)
    return path


def _places(store):
    from battle_conquest.destinations import Destinations

    return Destinations(MODES, store=store, url=URL)


def check_destination_urls():
    from battle_conquest.destinations import battles_url, valid_url

    check('an https URL is accepted', valid_url('https://battle-conquest.eu/api/mod/battles'))
    # Refused rather than upgraded or sent anyway: a report names a Wargaming
    # account, and in the clear it is readable by anyone on the way.
    check('plain http is refused', not valid_url('http://battle-conquest.eu/api/mod/battles'))
    check('a bare host is refused', not valid_url('battle-conquest.eu'))
    check('an empty URL is refused', not valid_url(''))
    check('the scheme alone is refused', not valid_url('https://'))
    check('a URL with a space in it is refused', not valid_url('https://foo bar/x'))
    check('something that is not a string is refused', not valid_url(None))
    check('the battles endpoint hangs off the site',
          battles_url('https://battle-conquest.test/') == URL)


def check_destination_modes():
    from battle_conquest.destinations import clean_modes

    check('a mode the mod knows is kept', clean_modes(['ranked'], MODES) == ['ranked'])
    # An unknown mode is dropped rather than carried: the capture never produces
    # it, so asking for it would wait forever and never be told.
    check('a mode the mod does not know is dropped', clean_modes(['rankedd'], MODES) == [])
    check('the same mode twice is kept once', clean_modes(['ranked', 'ranked'], MODES) == ['ranked'])
    check('nothing asked for is nothing kept', clean_modes(None, MODES) == [])


def check_destination_reading():
    from battle_conquest.destinations import read

    place = read(GOOD, MODES, URL)
    check('a well-formed link is read', place is not None)
    check('and it is asked for the mode it wants', place.wants('ranked'))
    check('but never for a mode it did not ask for', not place.wants('random'))

    check('a payload of another schema is ignored', read(dict(GOOD, schema=99), MODES, URL) is None)
    check('something that is not a payload is ignored', read(None, MODES, URL) is None)
    # A secret made for one site is never presented to another: a dev build
    # pointed at a local server must not send it the player's real secret.
    check('a link made for another site is ignored',
          read(dict(GOOD, url='https://elsewhere.test/api/mod/battles'), MODES, URL) is None)
    check('a link to a plain http site is ignored',
          read(dict(GOOD, url='http://battle-conquest.test/api/mod/battles'), MODES,
               'http://battle-conquest.test/api/mod/battles') is None)

    # Without a secret there is nothing to prove the account with, so there is
    # nothing to send: a report signed by nobody could name anybody.
    check('a link with no secret is not sent to', not read(dict(GOOD, secret=None), MODES, URL).wants('ranked'))
    check('a secret of the wrong length is no secret', not read(dict(GOOD, secret='abc'), MODES, URL).wants('ranked'))
    check('a link that says nothing about being enabled is paused',
          not read(dict(GOOD, enabled=None), MODES, URL).wants('ranked'))

    places = _places(_file(GOOD))
    check('the file is read from disk', places.linked and len(places.all()) == 1)
    check('the site is owed the modes it asked for', [d.url for d in places.wanting('ranked')] == [URL])
    check('and nothing else', places.wanting('random') == [])
    check('the modes waited for are the site\'s', places.modes() == ['ranked'])

    nothing = _places(os.path.join(tempfile.mkdtemp(), 'link.json'))
    check('without a file nothing is linked', not nothing.linked and nothing.all() == [])
    check('and nothing is owed', nothing.modes() == [] and nothing.wanting('ranked') == [])


def check_destination_secrets():
    from battle_conquest.destinations import new_secret, secret_hash

    store = os.path.join(tempfile.mkdtemp(), 'nested', 'link.json')
    places = _places(store)
    secret = new_secret()
    check('a secret is 64 hex characters', len(secret) == 64)
    check('and never the same twice', new_secret() != secret)
    linked = places.remember('Battle-Conquest', ['ranked', 'rankedd'], secret)
    # Only the hash ever leaves the machine.
    check('what travels is the hash, not the secret',
          linked.hash() == secret_hash(secret) and linked.hash() != secret)
    check('a link remembered is enabled: the player went through the site to make it', linked.enabled)
    check('only modes the mod knows are written down', linked.modes == ['ranked'])
    check('the secret is kept, so the link survives a restart', _places(store).current.secret == secret)

    # A second linking replaces the first, rather than leaving a credential
    # nobody will ever present again.
    again = new_secret()
    places.remember('Battle-Conquest', ['ranked'], again)
    check('linking again replaces the secret', _places(store).current.secret == again)


def check_destination_pause_and_forget():
    store = _file(GOOD)
    places = _places(store)
    check('pausing changes something', places.set_enabled(False) is True)
    check('a paused site is owed nothing', places.modes() == [] and places.wanting('ranked') == [])
    check('but stays linked', places.linked)
    check('and the pause survives a restart', not _places(store).enabled)
    check('pausing again changes nothing', places.set_enabled(False) is False)
    places.set_enabled(True)
    check('resuming owes it its modes again', places.modes() == ['ranked'])

    check('forgetting drops the link', places.forget() is True and not places.linked)
    check('and the file with it', not os.path.exists(store))
    check('so a restart finds nothing linked', not _places(store).linked)
    check('forgetting twice changes nothing', places.forget() is False)
    check('and pausing what is not linked changes nothing', places.set_enabled(False) is False)


def check_destination_capture():
    from battle_conquest.battle_reports import BattleReports
    from battle_conquest.report_queue import Queue

    places = _places(_file(GOOD))

    def _reports(destinations):
        return BattleReports(None, queue=Queue(store=os.path.join(tempfile.mkdtemp(), 'q.json')),
                             destinations=destinations)

    # A site scoring ranked is not sent the player's random battles.
    check('the mode the site asked for is wanted', _reports(places).wanted('ranked'))
    check('a mode it did not ask for is not', not _reports(places).wanted('random'))
    check('with nothing to send to, no battle is kept', not _reports(None).wanted('ranked'))
    places.set_enabled(False)
    check('nor while sending is paused', not _reports(places).wanted('ranked'))


class _Capture(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())

    def said(self, fragment):
        return any(fragment in line for line in self.lines)


def _loading(store):
    """What destinations.install() says while it loads this store."""
    from battle_conquest import destinations as module

    captured = _Capture()
    logger = logging.getLogger('battle_conquest.destinations')
    logger.addHandler(captured)
    original = module.battles_url
    module.battles_url = lambda site=None: URL
    try:
        module.install(None, MODES, store=store)
    finally:
        module.battles_url = original
        logger.removeHandler(captured)
    return captured


def check_destination_silence():
    """Every way the loading comes back empty says which way it was.

    A player whose battles reach no site has nothing else to tell a file that
    was never written from a file written somewhere the mod does not look --
    and the two are fixed differently. The path is relative to wherever the
    client was started, so without it in the line those two cases read
    identically.
    """
    missing = os.path.join(tempfile.mkdtemp(), 'nowhere', 'link.json')
    said = _loading(missing)
    check('a link file that is not there is said to be missing', said.said('no link file'))
    check('and the path it looked at is named', said.said(missing))

    said = _loading(_file(dict(GOOD, schema=99)))
    check('a file of another schema says so', said.said('schema'))
    check('and says which one this mod reads', said.said('reads 1'))

    broken = os.path.join(tempfile.mkdtemp(), 'link.json')
    with open(broken, 'wb') as handle:
        handle.write('{not json')
    check('a file that does not parse says so', _loading(broken).said('not readable JSON'))

    said = _loading(_file(GOOD))
    check('the site sent to is named', said.said('Battle-Conquest'))
    check('with its URL', said.said(URL))
    check('and the modes it is owed', said.said('ranked'))

    check('a paused link is still reported', _loading(_file(dict(GOOD, enabled=False))).said('paused'))
    check('a secret of the wrong length is reported rather than dropped in silence',
          _loading(_file(dict(GOOD, secret='abc'))).said('no usable secret'))
    check('a link made for another site is reported',
          _loading(_file(dict(GOOD, url='https://elsewhere.test/api/mod/battles'))).said('elsewhere.test'))
