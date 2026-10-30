"""End-to-end owner boundaries, with diagnostics off and two synthetic logins.

The structural fixture mirrors the real EU observation supplied for #964:
accountDBID in personal.avatar and in its vehicle, plus players keyed by ID.
The second login and modes other than the observed event remain simulations.
"""
import copy
import json
import os
import tempfile

from checks.battle_fixtures import ACCOUNT, Bonus, Player, owned, results
from checks.common import check
from checks.report_sender import _Session, _Response, _answer

OTHER = '500999999'
SECRET_A, SECRET_B = 'a' * 64, 'b' * 64


def fixture():
    from battle_conquest.destinations import Destinations, battles_url
    from battle_conquest.report_queue import Queue
    from battle_conquest.report_sender import Sender
    from battle_conquest.battle_reports import BattleReports
    root = tempfile.mkdtemp()
    player = Player()
    places = Destinations(('ranked', 'random', 'other', 'frontline'),
                          store=os.path.join(root, 'links'), account=player)
    places.remember('BC', ['ranked', 'random', 'other', 'frontline'], SECRET_A)
    player.account = OTHER
    places.remember('BC', ['ranked', 'random'], SECRET_B)
    player.account = ACCOUNT
    queue = Queue(store=os.path.join(root, 'queue'))
    session = _Session()
    reports = BattleReports(session, queue=queue, destinations=places, account=player)
    sender = Sender(session, player, queue=queue, destinations=places, garage=lambda: True)
    return player, places, queue, session, reports, sender


def raw(account=ACCOUNT, arena=91):
    return results(arenaUniqueID=arena, vehicle={'accountDBID': int(account)},
                   personal={'avatar': {'team': 1, 'accountDBID': int(account)}},
                   players={int(account): {'name': 'Owner'}, int(OTHER if account == ACCOUNT else ACCOUNT): {'name': 'Other'}})


def check_owner_extraction():
    from battle_conquest.battle_owner import owner_of, owner_name, account_id
    expected = {'id': int(ACCOUNT), 'region': 'eu'}
    check('real observed avatar/vehicle/players mapping selects the owner',
          owner_of(raw()) == (expected, None) and owner_name(raw(), expected) == 'Owner')
    renamed = raw()
    renamed['players'][int(ACCOUNT)]['name'] = 'Renamed'
    check('a nickname change cannot alter ownership', owner_of(renamed)[0] == expected)
    for mode in (Bonus.REGULAR, Bonus.RANKED, Bonus.COMP7, Bonus.EPIC_BATTLE, 102):
        sample = raw()
        sample['common']['bonusType'] = mode
        sample['personal']['second'] = {'team': 1, 'accountDBID': int(ACCOUNT)}
        check('synthetic mode %s and multiple vehicles retain one owner' % mode,
              owner_of(sample)[0] == expected)
    for bad in (True, 0, -1, 1.5, '1.5', [], None):
        sample = raw()
        sample['personal']['avatar']['accountDBID'] = bad
        check('invalid avatar identity is refused: %r' % bad, owner_of(sample)[0] is None)
    conflict = raw()
    conflict['personal']['second'] = {'team': 1, 'accountDBID': int(OTHER)}
    check('contradictory multi-vehicle ownership is refused', owner_of(conflict)[0] is None)
    missing = raw()
    for record in missing['personal'].values():
        record.pop('accountDBID', None)
    check('players and the login never substitute for missing personal ownership', owner_of(missing)[0] is None)
    check('integer/string WG identities are canonical, booleans and floats rejected',
          account_id('000' + ACCOUNT) == ACCOUNT and account_id(int(ACCOUNT)) == ACCOUNT
          and account_id(True) is None and account_id(float(ACCOUNT)) is None)


def check_owner_lifecycle():
    from battle_conquest.destinations import Destinations
    from battle_conquest.report_queue import Queue
    from battle_conquest.report_wire import wire
    player, places, queue, session, reports, sender = fixture()
    player.account = OTHER
    check('a late A result received under B stays owned by A with diagnostics off',
          reports.capture(raw(), constants=Bonus, request_context={'id': ACCOUNT, 'region': 'eu'})
          and queue.all()[0]['account'] == ACCOUNT)
    check('only owner identity travels, not participant names or request bookkeeping',
          wire(queue.all()[0])['owner'] == {'id': int(ACCOUNT), 'region': 'eu'}
          and 'request_owner' not in wire(queue.all()[0]) and 'owner_name' not in wire(queue.all()[0]))
    sender.drain()
    check('A is never sent with B proof', not session.sent and len(queue.all()) == 1)
    check('the same arena for B is captured independently', reports.capture(raw(OTHER), constants=Bonus))
    sender.drain()
    request = session.sent[0]
    check('B batch and per-battle owner agree with B secret',
          request['headers']['X-Mod-Secret'] == SECRET_B
          and request['body']['account'] == {'id': int(OTHER), 'region': 'eu'}
          and request['body']['battles'][0]['owner'] == request['body']['account'])
    _answer(session, 200, {'results': [{'index': 0, 'status': 'accepted'}]})
    check('acknowledging B leaves A untouched', len(queue.all()) == 1 and queue.all()[0]['account'] == ACCOUNT)
    b_status = sender.last_result
    player.account = ACCOUNT
    reopened = Destinations(places._known, store=places._store, account=player)
    check('A link is restored after restart with its own secret', reopened.current.secret == SECRET_A)
    places.set_enabled(False)
    sender.drain()
    check('pausing A keeps its backlog', not session.sent and len(queue.all()) == 1)
    places.set_enabled(True)
    sender.drain()
    check('resuming A sends under A proof', session.sent[0]['headers']['X-Mod-Secret'] == SECRET_A)
    player.account = OTHER
    _answer(session, 200, {'results': [{'index': 0, 'status': 'duplicate'}]})
    check('an A acknowledgement arriving under B settles only A', queue.all() == [])
    check('late A receipts cannot replace B delivery status', sender.last_result == b_status)
    places.forget()
    check('unlinking B leaves the A key intact', places.for_owner(('eu', ACCOUNT)).secret == SECRET_A)
    player.account = '501111111'
    check('an unknown game account is neither linked nor given another key', not places.linked and places.current is None)
    player.account = ACCOUNT
    queue.add(owned({'arena_unique_id': '10', 'mode': 'ranked'}))
    queue.add(owned({'arena_unique_id': '10', 'mode': 'ranked'}, OTHER))
    queue.drop(['10'], account=OTHER)
    check('explicit removal is owner-scoped', len(queue.all()) == 1 and queue.all()[0]['account'] == ACCOUNT)
    restored = Queue(store=queue._store)
    check('owner identity survives queue restart', restored.all() == queue.all())


def check_owner_quarantine():
    from battle_conquest.report_queue import Queue, trim
    player, places, queue, session, reports, sender = fixture()
    check('conflicting request ownership isolates rather than reassigns',
          not reports.capture(raw(), constants=Bonus, request_context={'id': OTHER, 'region': 'eu'})
          and queue.isolated() == 1)
    missing = raw(arena=92)
    for record in missing['personal'].values():
        record.pop('accountDBID', None)
    reports.capture(missing, constants=Bonus)
    sender.drain()
    check('missing identity never leaves the isolated queue', queue.isolated() == 2 and not session.sent)
    check('a normal re-observation can be captured without rewriting isolated history',
          reports.capture(raw(arena=92), constants=Bonus) and queue.isolated() == 2)
    sender.drain()
    _answer(session, 200, {'results': [{'index': 0, 'status': 'accepted'}]})
    check('normal delivery cannot purge isolated reports', queue.isolated() == 2 and len(queue.all()) == 2)
    legacy = os.path.join(tempfile.mkdtemp(), 'old-queue')
    old = {'arena_unique_id': '1', 'account': ACCOUNT, 'mode': 'ranked'}
    with open(legacy, 'wb') as handle:
        json.dump({'schema': 1, 'reports': [old]}, handle)
    migrated = Queue(store=legacy)
    check('legacy account stamps are unverified and never sent automatically',
          migrated.isolated() == 1 and not migrated.pending(places.url, ['ranked'])
          and migrated.all()[0]['account'] == ACCOUNT)
    backlog = [owned({'arena_unique_id': '1'}, OTHER)] + [owned({'arena_unique_id': str(i)}) for i in range(5)]
    kept = trim(backlog, 2)
    check('one owner cannot evict another owner by filling the queue',
          len(kept) == 3 and kept[0]['account'] == OTHER)


def check_owner_refusals():
    player, places, queue, session, reports, sender = fixture()
    reports.capture(raw(), constants=Bonus)
    reports.capture(raw(arena=92), constants=Bonus)
    sender.drain()
    _answer(session, 200, {'accepted': 1, 'rejected': 1, 'results': [
        {'index': 0, 'status': 'rejected', 'reason': 'account_mismatch'},
        {'index': 1, 'status': 'accepted'}]})
    check('account_mismatch retains only the recoverable report and suspends the link',
          len(queue.all()) == 1 and places.current.blocked == 'account_mismatch' and not places.linked)
    for unused in range(3):
        sender.drain()
    check('a mismatched link does not retry in a loop', not session.sent)
    check('a suspended link still captures its owner for later recovery',
          reports.capture(raw(arena=93), constants=Bonus) and len(queue.all()) == 2)
    from battle_conquest.destinations import Destinations
    restored = Destinations(places._known, store=places._store, account=player)
    check('link suspension persists across restart', restored.current.blocked == 'account_mismatch')
    player.account = OTHER
    check('suspending A leaves B enabled', places.enabled and places.current.secret == SECRET_B)
    player.account = ACCOUNT
    places.remember('BC', ['ranked'], 'c' * 64)
    sender.drain()
    check('relinking resumes immediately under the repaired proof',
          len(session.sent) == 1 and session.sent[0]['headers']['X-Mod-Secret'] == 'c' * 64)
    _answer(session, 503)
    sender.drain()
    check('network refusal retains the report with backoff', len(queue.all()) == 2 and not session.sent)
    places.remember('BC', ['ranked'], 'd' * 64)
    sender.drain()
    _answer(session, 401)
    check('revocation suspends only its key and keeps reports', len(queue.all()) == 2 and places.current.blocked == 'revoked')


def check_owner_migration():
    from battle_conquest.destinations import Destinations, battles_url
    from battle_conquest.site_link import SiteLink, Attempt
    from checks.site_link import _Session as LinkSession
    root = tempfile.mkdtemp()
    path = os.path.join(root, 'legacy')
    legacy = {'schema': 1, 'url': battles_url(), 'label': 'BC', 'enabled': False,
              'modes': ['ranked'], 'secret': SECRET_A}
    with open(path, 'wb') as handle:
        json.dump(legacy, handle)
    player = Player(OTHER)
    places = Destinations(('ranked', 'random'), store=path, account=player)
    check('a legacy key is not linked until the server names its owner',
          not places.linked and places.legacy is not None)
    session = LinkSession()
    site = SiteLink(session, places, player)
    site.verify()
    check('the legacy key is sent only to its original /me endpoint',
          session.sent[-1]['url'] == 'https://battle-conquest.eu/api/mod/me'
          and session.sent[-1]['headers']['X-Mod-Secret'] == SECRET_A)
    session.sent.pop()['answer'](_Response(200, {'account_id': ACCOUNT, 'region': 'eu', 'modes': ['ranked']}))
    check('legacy A key is stored for A even when B is logged in',
          places.legacy is None and not places.linked
          and places.for_owner(('eu', ACCOUNT)).secret == SECRET_A)
    player.account = ACCOUNT
    check('migration preserves the player pause', places.linked and not places.enabled)
    reloaded = Destinations(('ranked', 'random'), store=path, account=player)
    check('verified migration persists as schema 2', reloaded.linked and json.load(open(path))['schema'] == 2)
    places.remember('BC', ['ranked'], SECRET_B)
    attempt = Attempt(session, places, ACCOUNT)
    attempt._answered(_Response(200, {'account_id': OTHER, 'region': 'eu', 'modes': ['ranked']}))
    check('wrong browser session cannot replace the saved key', places.current.secret == SECRET_B)
    attempt = Attempt(session, places, ACCOUNT)
    attempt._answered(_Response(200, {'account_id': ACCOUNT, 'region': 'na', 'modes': ['ranked']}))
    check('wrong region cannot replace the saved key', places.current.secret == SECRET_B)
    attempt = Attempt(session, places, ACCOUNT)
    attempt._answered(_Response(200, {'modes': ['ranked']}))
    check('a server without owner metadata cannot invent the link owner', places.current.secret == SECRET_B)
    attempt = Attempt(session, places, ACCOUNT)
    player.account = OTHER
    attempt._answered(_Response(200, {'account_id': ACCOUNT, 'region': 'eu', 'modes': ['ranked']}))
    check('a late linking confirmation cannot be saved under a new login',
          not places.linked and places.for_owner(('eu', ACCOUNT)).secret == SECRET_B)
    player.account = ACCOUNT
    site.verify()
    pending = session.sent.pop()['answer']
    player.account = OTHER
    places.remember('BC', ['ranked'], 'c' * 64)
    pending(_Response(401))
    check('late A revocation leaves B key untouched',
          places.current.secret == 'c' * 64 and places.for_owner(('eu', ACCOUNT)) is None)
    player.account = ACCOUNT
    places.remember('BC', ['ranked'], SECRET_A)
    site.verify()
    session.sent.pop()['answer'](_Response(200, {'account_id': OTHER, 'region': 'eu', 'modes': ['ranked']}))
    check('a stored key whose server owner differs is suspended rather than reassigned',
          places.current.blocked == 'account_mismatch' and not places.linked)
    foreign = Destinations(('ranked',), store=path, url='https://local.test/api/mod/battles', account=player)
    check('changing builds never exposes a foreign site key', not foreign.linked and foreign.legacy is None)
    foreign.remember('Local', ['ranked'], 'd' * 64)
    production = Destinations(('ranked',), store=path, account=player)
    check('writing a local link preserves all production accounts',
          production.current.secret == SECRET_A and production.for_owner(('eu', OTHER)).secret == 'c' * 64)


def check_owner_requests():
    from battle_conquest.results_request import Requests
    from checks.results_request import _Cache, _Clock, _Session as CacheSession
    context = {'id': ACCOUNT, 'region': 'eu'}
    clock, cache, delivered = _Clock(), _Cache(), []
    requests = Requests(CacheSession(), lambda result, source, origin: delivered.append(origin),
                        garage=lambda: True, cache=lambda: cache, now=clock,
                        context=lambda: context, limit=2)
    requests.remember(1)
    requests.remember(2)
    context['id'] = OTHER
    requests.remember(1)
    requests.remember(3)
    requests.remember(4)
    check('one login cannot evict another login pending result requests', requests.waiting() == [1, 2, 3, 4])
    context['id'] = ACCOUNT
    requests.drain()
    old = cache._pending[1]
    context['id'] = OTHER
    clock.now += 61
    requests.drain()
    check('switching logins fetches only that login pending requests', cache.asked == [1, 3])
    old(1, raw())
    check('late cache answers preserve A origin under B', delivered == [{'id': ACCOUNT, 'region': 'eu'}])
    cache.answer_now(3, 1, raw(OTHER))
    cache.answer_now(4, 1, raw(OTHER))
    check('B answers retain their own origin independently', delivered[-1] == {'id': OTHER, 'region': 'eu'})
    check('unserved A requests remain available after B drains', requests.waiting() == [2])
    context['id'] = ACCOUNT
    requests.drain()
    cache.answer_now(2, 1, raw())
    check('switching back resumes A requests', not requests.busy())


def check_owner_storage():
    from battle_conquest.destinations import Destinations
    from battle_conquest.report_queue import Queue
    from battle_conquest.local_store import save_json, load_json
    root = tempfile.mkdtemp()
    path = os.path.join(root, 'links')
    with open(path, 'wb') as handle:
        handle.write('{broken')
    places = Destinations(('ranked',), store=path, account=Player())
    try:
        places.remember('BC', ['ranked'], SECRET_A)
    except IOError:
        pass
    check('an unreadable links file is preserved for recovery', open(path).read() == '{broken')
    check('an unreadable links file cannot create an active in-memory key', not places.linked)
    malformed = os.path.join(root, 'malformed-queue')
    with open(malformed, 'wb') as handle:
        json.dump({'schema': 1, 'reports': [{'account': {}, 'arena_unique_id': []}]}, handle)
    check('structured legacy IDs are isolated without interrupting startup', Queue(store=malformed).isolated() == 1)
    queue_path = os.path.join(root, 'queue')
    with open(queue_path, 'wb') as handle:
        handle.write('{broken')
    queue = Queue(store=queue_path)
    check('an unreadable queue suspends capture without overwriting evidence',
          not queue.add(owned({'arena_unique_id': '1'})) and open(queue_path).read() == '{broken')
    saved = os.path.join(root, 'safe')
    save_json(saved, {'schema': 2, 'value': 1})
    save_json(saved, {'schema': 2, 'value': 2})
    check('local replacement keeps a complete previous copy', json.load(open(saved + '.bak'))['value'] == 1)
    os.rename(saved, saved + '.interrupted')
    check('startup recovers a previous complete copy after interrupted replacement', load_json(saved)['value'] == 1)
