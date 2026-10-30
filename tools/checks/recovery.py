"""Crash recovery and HTTP acknowledgement fault injection, without a client."""
import json
import os
import tempfile

from checks.common import check
from checks.results_request import _Cache, _Clock, _Session
from checks.report_sender import _queue, _sender, _Response


def check_recovery():
    from battle_conquest.recovery_journal import Journal, RETENTION
    from battle_conquest.results_request import Requests
    clock, cache = _Clock(), _Cache()
    path = os.path.join(tempfile.mkdtemp(), 'recovery.json')
    context = {'region': 'eu', 'id': '123'}
    enabled, saved = [True], set()
    def build():
        return Requests(_Session(), lambda *args: None, context=lambda: context,
                        garage=lambda: True, cache=lambda: cache, now=clock,
                        journal=Journal(path), captured=lambda key: key in saved,
                        taking=lambda: enabled[0])
    requests = build()
    requests.remember(18446744073709551615)
    requests.drain()
    check('recovery waits five seconds after garage readiness', not cache.asked)
    clock.now += 5
    requests.drain()
    check('uint64 arena is a string on disk with its real attempt recorded',
          json.load(open(path))['arenas'][0]['arena'] == '18446744073709551615'
          and json.load(open(path))['arenas'][0]['attempts'] == 1)
    requests = build()
    clock.now += 61
    requests.drain()
    clock.now += 5
    requests.drain()
    check('interrupted recovery resumes without resetting attempts',
          requests._journal.entries[('eu', '123', 18446744073709551615L)]['attempts'] == 2)
    context['id'] = '456'
    requests.remember(22)
    enabled[0] = False
    clock.now += 100
    requests.drain()
    check('pause preserves journal and makes no new requests', len(cache.asked) == 2)
    enabled[0] = True
    context['id'] = None
    requests.remember(33)
    context['id'] = '789'
    requests.drain()
    check('other and unknown owners are never adopted by the active login', len(cache.asked) == 2)
    saved.add(('eu', '456', 22))
    requests.drain()
    check('durably captured hook results remove recovery work', ('eu', '456', 22) not in requests._journal.entries)
    before = os.stat(path).st_mtime
    requests.drain()
    check('idle recovery tick leaves the journal untouched', os.stat(path).st_mtime == before)
    clock.now += RETENTION
    requests.drain()
    check('seven-day retention expires isolated and unavailable arenas', not requests._journal.entries)
    context['id'] = '123'
    for arena in range(60):
        requests.remember(arena + 1)
    check('journal is bounded to fifty arenas per owner', len(requests._journal.entries) == 50)
    # Corruption must never be replaced with an empty journal.
    with open(path, 'wb') as handle:
        handle.write('broken')
    corrupt = Journal(path)
    check('corrupt journal is preserved and recovery suspended',
          not corrupt.writable and not corrupt.save() and open(path).read() == 'broken')

    # A completed temporary copy is newer than the backup between renames.
    os.rename(path, path + '.corrupt')
    row = dict(region='eu', account='123', arena='99', observed=clock.now, due=clock.now, attempts=4)
    with open(path + '.tmp', 'wb') as handle:
        json.dump({'schema': 1, 'arenas': [row]}, handle)
    restored = Journal(path)
    check('interrupted rename recovers the newer complete attempt counter',
          restored.entries[('eu', '123', 99)]['attempts'] == 4)
    requests = build()
    requests.drain()
    clock.now += 5
    requests.drain()
    check('fifth persisted attempt is the last actual request', cache.asked[-1] == 99)
    clock.now += 61
    requests.drain()
    check('no sixth attempt after timeout and repeated restart', Journal(path).entries[('eu', '123', 99)].get('abandoned') and cache.asked.count(99) == 1)
    # Disk failure must stop the request before the cache is touched.
    requests = build()
    requests.remember(100)
    writes = []
    requests._journal.save = lambda: writes.append(True) or False
    before = len(cache.asked)
    requests.drain()
    clock.now += 5
    requests.drain()
    check('unpersisted attempts cannot reach cache on disk failure', len(cache.asked) == before and writes)
    # Entering battle retains the authenticated garage snapshot, never a new login.
    import BigWorld
    previous = BigWorld.player
    requests = build()
    try:
        BigWorld.player = lambda: type('Avatar', (), {'arenaUniqueID': 101})()
        context['id'] = None
        requests._entered_battle()
        check('battle entry journals pre-avatar login without storing battle data',
              ('eu', '123', 101) in requests._journal.entries)
        requests._session.alive = False
        requests._entered_battle()
        check('closed session cannot record new recovery work', sum(not row.get('abandoned') for row in requests._journal.entries.values()) == 2)
    finally:
        BigWorld.player = previous


def check_receipts():
    from battle_conquest.report_wire import verdicts
    batch = [{'arena_unique_id': '1'}, {'arena_unique_id': '2'}]
    good = {'index': 0, 'arena_unique_id': '1', 'status': 'accepted'}
    for malformed in (None, {}, {'results': 'html'}, {'results': [{'index': 0, 'status': 'accepted'}]}, {'results': [dict(good, index=True)]},
                      {'results': [dict(good, arena_unique_id='2')]},
                      {'results': [good, dict(good, status='rejected')]},
                      {'results': [dict(good, status='unknown')]}):
        check('malformed or contradictory verdicts confirm nothing: %r' % malformed,
              not verdicts(malformed, batch))
    partial = {'results': [good, {'index': 1, 'status': 'accepted', 'arena_unique_id': 'bad'}]}
    check('independent valid verdict survives malformed neighbouring verdict', verdicts(partial, batch) == [good])
    null = {'index': 1, 'status': 'rejected', 'arena_unique_id': None, 'reason': 'payload:finished_at'}
    check('null arena is valid only for a payload validation rejection', verdicts({'results': [null]}, batch) == [null]
          and not verdicts({'results': [dict(null, reason='account_mismatch')]}, batch))
    queue = _queue(count=2)
    session, sender = _sender(queue)
    timers = []
    session.callback = lambda delay, func: timers.append((delay, func))
    sender.drain()
    response = session.sent.pop()['answer']
    response(_Response(200, partial))
    check('partial HTTP 200 settles only confirmed reports and backs off',
          [r['arena_unique_id'] for r in queue.all()] == ['2'] and sender._waiting and not sender._busy)
    sender._waiting.clear()
    sender.drain()
    late = session.sent.pop()['answer']
    timers[-1][1]()
    check('missing callback expires and releases sender without losing reports',
          len(queue.all()) == 1 and not sender._busy and bool(sender._waiting))
    late(_Response(200, {'results': [{'index': 0, 'status': 'accepted', 'arena_unique_id': '2'}]}))
    check('response after HTTP expiration cannot acknowledge a report', len(queue.all()) == 1)

    # The scheduler handed to #956 must remain occupied by a live capture ask.
    from battle_conquest.results_request import Requests
    from battle_conquest.recovery_journal import Journal
    from battle_conquest.quest_repairs import Repairs
    from checks.battle_fixtures import Player
    from checks.report_sender import _places, _destination
    from battle_conquest.destinations import battles_url
    clock, cache, session = _Clock(), _Cache(), _Session()
    shared = Requests(session, lambda *args: None, context=lambda: {'id': '123', 'region': 'eu'},
                      garage=lambda: True, cache=lambda: cache, now=clock,
                      journal=Journal(os.path.join(tempfile.mkdtemp(), 'journal')))
    places = _places(_destination(url=battles_url(), account='123'))
    places.current = places.all()[0]
    repairs = Repairs(session, Player('123'), places, lambda *args: None, requests=shared,
                      garage=lambda: True, cache=lambda: cache, now=clock)
    shared.remember(201)
    shared.drain()
    clock.now += 5
    shared.drain()
    shared.remember(202, repair=True)
    repairs._key = repairs.identity()
    repairs.drain()
    check('quest repair and live capture share a single in-flight cache operation',
          repairs._requests is shared and cache.asked == [201])

    cache.answer_now(201, -1)
    check('unannounced unavailable result retains arena for a post-battle retry',
          shared._journal.entries[('eu', '123', 201)]['due'] == clock.now + 900)
