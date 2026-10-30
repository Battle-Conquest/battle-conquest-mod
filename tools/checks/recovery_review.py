"""Review regressions at persistence and client lifecycle boundaries."""
import json
import os
import tempfile

from checks.common import check
from checks.results_request import _Clock, _Cache, _Session


def fixture(context=None, captured=None):
    from battle_conquest.recovery_journal import Journal
    from battle_conquest.results_request import Requests
    path = os.path.join(tempfile.mkdtemp(), 'journal')
    clock, cache, session = _Clock(), _Cache(), _Session()
    identity = context if context is not None else {'id': '123', 'region': 'eu'}
    requests = Requests(session, lambda *args: None, context=lambda: identity,
                        now=clock, cache=lambda: cache, garage=lambda: True,
                        journal=Journal(path), captured=captured)
    return requests, clock, cache, identity, path


def check_recovery_review_atomic_capacity():
    from battle_conquest.recovery_journal import Journal
    from battle_conquest import recovery_journal as module
    requests, clock, cache, identity, path = fixture()
    requests.remember(999, origin={'region': 'eu', 'id': '456'})
    for arena in range(1, 51):
        requests.remember(arena)
    # Inspect every snapshot that could become the sole surviving disk copy.
    snapshots, original = [], module.save_json
    def observe(path, payload):
        snapshots.append(json.loads(json.dumps(payload)))
        original(path, payload)
    module.save_json = observe
    try:
        requests.remember(51)
    finally:
        module.save_json = original
    check('saturation never persists an unloadable owner count',
          all(sum(1 for row in snapshot['arenas'] if row['account'] == '123') <= 50
              for snapshot in snapshots))
    for snapshot in snapshots:
        original(path, snapshot)
        restored = Journal(path)
        check('every interrupted saturation snapshot preserves other owners and remains loadable',
              restored.writable and ('eu', '456', 999) in restored.entries)


def check_recovery_review_posted():
    from battle_conquest.battle_reports import BattleReports
    original = BattleReports.__dict__['_service']
    BattleReports._service = staticmethod(lambda: type('Posted', (), {'areResultsPosted': lambda self, arena: True})())
    try:
        for repair in (False, True):
            requests, clock, cache, identity, path = fixture()
            requests.remember(91, repair=repair)
            requests.drain()
            for unused in range(5):
                clock.now += 5
                requests.drain()
            check('posted UI flag never blocks unsaved recovery or quest repair forever: %s' % repair,
                  cache.asked == [91])
    finally:
        BattleReports._service = original


def check_recovery_review_idle_account():
    import BigWorld
    requests, clock, cache, identity, path = fixture()
    requests.drain()
    identity['id'] = '456'
    # No pending work, and no account event on this client: the fallback tick
    # is the only observation before the next avatar hides databaseID.
    requests.drain()
    identity['id'] = None
    player = BigWorld.player
    try:
        BigWorld.player = lambda: type('Avatar', (), {'arenaUniqueID': 91})()
        requests._entered_battle()
    finally:
        BigWorld.player = player
    check('idle fallback observes new login before the avatar hides its ID',
          ('eu', '456', 91) in requests._journal.entries
          and ('eu', '123', 91) not in requests._journal.entries)


def check_recovery_review_announcement():
    from battle_conquest.results_request import arrival_types
    from checks.results_request import _Message
    requests, clock, cache, identity, path = fixture()
    requests.remember(91)
    requests.drain()
    clock.now += 5
    requests.drain()
    cache.answer_now(91, -1)
    clock.now += 30
    requests._announced(1, _Message(sorted(arrival_types())[0], {'arenaUniqueID': 91}))
    clock.now += 5
    requests.drain()
    check('public completion announcement expedites a fifteen-minute unavailable retry',
          cache.asked == [91, 91] and requests._journal.entries[('eu', '123', 91)]['attempts'] == 2)


def check_recovery_review_http_generations():
    from checks.report_sender import _queue, _sender, _Response
    queue = _queue(count=2)
    session, sender = _sender(queue)
    timers = []
    session.callback = lambda delay, func: timers.append(func)
    sender.drain()
    old = session.sent.pop()['answer']
    partial = {'results': [{'index': 0, 'arena_unique_id': '1', 'status': 'accepted'}]}
    old(_Response(200, partial))
    sender._waiting.clear()
    sender.drain()
    current = session.sent.pop()['answer']
    timers[0]()
    old(_Response(401))
    check('old timeout and repeated HTTP response cannot release or revoke a newer operation',
          sender._busy and not sender._stopped and not sender._waiting
          and [r['arena_unique_id'] for r in queue.all()] == ['2'])
    current(_Response(200, {'results': [{'index': 0, 'arena_unique_id': '2', 'status': 'rejected'}]}))
    timers[-1]()
    check('current definitive rejection settles once despite obsolete timeouts',
          not queue.all() and not sender._busy and not sender._waiting)


def check_recovery_review_late_cache():
    requests, clock, cache, identity, path = fixture()
    requests.remember(91, announced=True)
    requests.drain()
    clock.now += 5
    requests.drain()
    late = cache._pending[91]
    clock.now += 61
    requests.drain()
    clock.now += 20
    requests.drain()
    # An old successful cache answer still cannot be persisted (disk error,
    # ownership mismatch, etc.). Its replacement request is already active.
    late(1, {'common': {}})
    check('unpersisted late result cannot requeue the arena already in flight',
          requests._asking == ('eu', '123', 91) and requests.waiting() == [])
    cache.answer_now(91, -1)
    check('permanent refusal after late answer leaves no orphan pending arena',
          not requests.waiting() and not requests._journal.entries)
    requests.remember(92, announced=True)
    clock.now += 5
    requests.drain()
    check('cache scheduler remains usable after late result and replacement refusal', cache.asked == [91, 91, 92])


def check_recovery_review_temporary_copy():
    from battle_conquest.recovery_journal import Journal
    from battle_conquest import recovery_journal as module
    path = os.path.join(tempfile.mkdtemp(), 'journal')
    payload = {'schema': 1, 'arenas': [dict(region='eu', account='123', arena='91',
                                         observed=1000, due=1060, attempts=2)]}
    with open(path + '.tmp', 'wb') as handle:
        json.dump(payload, handle)
    recovered = Journal(path)
    original = module.save_json
    def disk_full(path, payload):
        # Real save_json opens this scratch path before touching the main copy.
        with open(path + '.tmp', 'wb') as handle:
            handle.write('{')
        raise IOError('disk full while writing the next snapshot')
    module.save_json = disk_full
    try:
        recovered.save()
    finally:
        module.save_json = original
    restored = Journal(path)
    check('second interrupted write preserves the complete adopted temporary copy',
          restored.writable and ('eu', '123', 91) in restored.entries
          and restored.entries[('eu', '123', 91)]['attempts'] == 2)
