"""An old valid credential must not undo a newer explicit unlink."""
import json
import os
import tempfile

from checks.battle_fixtures import ACCOUNT, Player
from checks.common import check
from checks.owner_isolation import OTHER
from checks.report_sender import _Response
from checks.site_link import _Session


def pending_migration():
    from battle_conquest.destinations import Destinations, battles_url
    from battle_conquest.site_link import SiteLink
    path = os.path.join(tempfile.mkdtemp(), 'links')
    with open(path, 'wb') as handle:
        json.dump({'schema': 1, 'url': battles_url(), 'enabled': True,
                   'modes': ['ranked'], 'secret': 'a' * 64}, handle)
    player, session = Player(), _Session()
    places = Destinations(('ranked',), store=path, account=player)
    site = SiteLink(session, places, player)
    site.verify()
    delayed = session.sent.pop()['answer']
    # Linking creates another active server credential; the previous one can
    # remain valid and its /me answer can arrive after this newer link is gone.
    places.remember('BC', ['ranked'], 'b' * 64)
    site.unlink()
    return player, places, site, session, delayed


def response(account=ACCOUNT, region='eu'):
    return _Response(200, {'account_id': account, 'region': region, 'modes': ['ranked']})


def check_legacy_unlink_race():
    player, places, site, session, delayed = pending_migration()
    check('the newer link was explicitly removed', not places.linked)
    delayed(response())
    check('a late successful legacy verification cannot relink that owner',
          not places.linked and places.legacy is None and places.current is None)
    places.remember('BC', ['ranked'], 'c' * 64)
    check('an explicit relink remains possible after suppression', places.current.secret == 'c' * 64)

    player, places, site, session, delayed = pending_migration()
    places.remember('BC', ['ranked'], 'c' * 64)
    delayed(response())
    check('an old verification cannot replace a newer explicitly renewed key',
          places.linked and places.current.secret == 'c' * 64 and places.legacy is None)


def check_legacy_unlink_restart():
    from battle_conquest.destinations import Destinations
    from battle_conquest.site_link import SiteLink
    player, places, site, session, delayed = pending_migration()
    restored = Destinations(('ranked',), store=places._store, account=player)
    transport = _Session()
    restarted = SiteLink(transport, restored, player)
    restarted.verify()
    transport.sent.pop()['answer'](response())
    check('explicit unlink also defeats legacy migration after restart',
          not restored.linked and restored.legacy is None)
    # Persisting the migration decision cannot revive it on the next load.
    reloaded = Destinations(('ranked',), store=places._store, account=player)
    check('the discarded old key stays discarded on disk',
          not reloaded.linked and reloaded.legacy is None)


def check_legacy_unlink_owner_scope():
    player, places, site, session, delayed = pending_migration()
    delayed(response(OTHER))
    check('unlinking A does not discard a legacy key actually owned by B',
          places.for_owner(('eu', OTHER)).secret == 'a' * 64 and not places.linked)
    player.account = OTHER
    check('the other owner can still use its migrated key', places.linked)
    check('unlink suppression is also scoped to the site URL',
          places.legacy_unlinked(('eu', ACCOUNT)))
    places.url = 'https://another.test/api/mod/battles'
    check('a different site cannot inherit this site unlink decision',
          not places.legacy_unlinked(('eu', ACCOUNT)))

    player, places, site, session, delayed = pending_migration()
    delayed(response(ACCOUNT, 'na'))
    check('unlinking EU cannot discard a legacy key for another region',
          places.for_owner(('na', ACCOUNT)).secret == 'a' * 64 and not places.linked)
