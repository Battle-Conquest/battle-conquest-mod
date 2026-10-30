"""End-to-end recovery limits across announcements and process restarts."""
from checks.common import check
from checks.recovery_review import fixture
from checks.results_request import _Message


def check_recovery_terminal_restart():
    from battle_conquest.recovery_journal import Journal
    from battle_conquest.results_request import Requests, arrival_types
    requests, clock, cache, identity, path = fixture()
    requests.remember(91, announced=True)
    requests.drain()
    clock.now += 5
    for attempt in range(5):
        requests.drain()
        cache.answer_now(91, -5)
        clock.now += 20
    check('five real refusals exhaust automatic recovery', len(cache.asked) == 5 and not requests.busy())
    # On a new connection the service channel can repeat a known announcement.
    restarted = Requests(requests._session, lambda *args: None, context=lambda: identity,
                         now=clock, cache=lambda: cache, garage=lambda: True, journal=Journal(path))
    restarted._announced(1, _Message(sorted(arrival_types())[0], {'arenaUniqueID': 91}))
    clock.now += 5
    restarted.drain()
    check('repeated announcement after restart cannot reset an exhausted arena budget', len(cache.asked) == 5)


def check_recovery_transition_sequences():
    from itertools import permutations
    from battle_conquest.recovery_journal import Journal
    from battle_conquest.results_request import Requests, arrival_types
    from checks.results_request import _Session
    for order in permutations(('late', 'refusal', 'restart', 'announcement')):
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
        refusal = cache._pending[91]
        for action in order:
            if action == 'late':
                late(1, {'common': {}})
            elif action == 'refusal':
                refusal(-1, None)
            elif action == 'restart':
                requests._session.alive = False
                requests = Requests(_Session(), lambda *args: None, context=lambda: identity,
                                    now=clock, cache=lambda: cache, garage=lambda: True,
                                    journal=Journal(path))
            else:
                requests._announced(1, _Message(sorted(arrival_types())[0], {'arenaUniqueID': 91}))
            clock.now += 5
            requests.drain()
            check('recovery state remains coherent after %s in %s' % (action, order),
                  all(key in requests._journal.entries for key in requests._pending)
                  and requests._asking not in requests._pending)
        # Exhaust whatever remains after the race, then replay notifications
        # and reload repeatedly. The budget is per owner/arena, not per load.
        for unused in range(10):
            if requests._asking is not None:
                cache._pending[91](-5, None)
            requests._session.alive = False
            requests = Requests(_Session(), lambda *args: None, context=lambda: identity,
                                now=clock, cache=lambda: cache, garage=lambda: True,
                                journal=Journal(path))
            requests._announced(1, _Message(sorted(arrival_types())[0], {'arenaUniqueID': 91}))
            clock.now += 65
            requests.drain()
            check('automatic request budget survives all callback orders and restarts: %s' % (order,),
                  len(cache.asked) <= 5)


def check_recovery_terminal_retention():
    from battle_conquest.recovery_journal import Journal, RETENTION
    from battle_conquest.results_request import Requests
    from checks.results_request import _Session
    requests, clock, cache, identity, path = fixture()
    requests.remember(91, announced=True)
    requests.drain()
    clock.now += 5
    requests.drain()
    answer = cache._pending[91]
    answer(-1, None)
    # A later unusable answer cannot undo a permanent cache refusal either.
    answer(1, {'common': {}})
    check('late unusable result never revives an abandoned recovery',
          not requests.busy() and requests._journal.entries[('eu', '123', 91)]['abandoned'])
    initial = dict(requests._journal.entries[('eu', '123', 91)])
    identity['id'] = '456'
    requests.remember(91, announced=True)
    check('terminal marker does not block another owner of the same arena',
          ('eu', '456', 91) in requests._journal.entries)
    # Idle terminal entries do not create writes or refresh their retention.
    writes = []
    save = requests._journal.save
    requests._journal.save = lambda: writes.append(True)
    identity['id'] = '123'
    requests.drain()
    check('idle abandoned entries preserve retention and cause no writes',
          not writes and requests._journal.entries[('eu', '123', 91)] == initial)
    requests._journal.save = save
    clock.now += RETENTION
    requests.drain()
    check('abandoned markers expire after the original seven-day horizon', not requests._journal.entries)
    restored = Requests(_Session(), lambda *args: None, context=lambda: identity, now=clock,
                        cache=lambda: cache, garage=lambda: True, journal=Journal(path))
    check('expiry also removes terminal markers from the persisted journal', not restored.busy())


def check_recovery_unwanted_mode():
    import sys
    from checks.owner_isolation import fixture as capture_fixture, raw
    from checks.battle_fixtures import ACCOUNT, Bonus
    previous = sys.modules.get('constants')
    sys.modules['constants'] = type('Constants', (), {'ARENA_BONUS_TYPE': Bonus})()
    try:
        player, places, queue, session, reports, sender = capture_fixture()
        places.current.modes = ['random']
        requests, clock, cache, identity, path = fixture(context={'id': ACCOUNT, 'region': 'eu'},
                                                        captured=queue.captured)
        requests._deliver = reports.arrived
        requests._taking = reports.anything_wanted
        requests.remember(91)
        requests.drain()
        clock.now += 5
        for unused in range(5):
            requests.drain()
            if requests._asking is not None:
                cache.answer_now(91, 1, raw())
            clock.now += 21
        check('valid result of an unwanted mode is retrieved once without queueing or retrying',
              cache.asked == [91] and not queue.all() and not requests.busy())
    finally:
        if previous is None:
            sys.modules.pop('constants', None)
        else:
            sys.modules['constants'] = previous


def check_recovery_capture_decisions():
    import json
    import os
    import sys
    from battle_conquest import report_queue as queue_module
    from battle_conquest.results_diagnostic import Diagnostic
    from checks.owner_isolation import fixture as capture_fixture, raw
    from checks.battle_fixtures import ACCOUNT, Bonus
    previous = sys.modules.get('constants')
    sys.modules['constants'] = type('Constants', (), {'ARENA_BONUS_TYPE': Bonus})()
    try:
        for scenario in ('disk', 'pause', 'wrong_arena', 'diagnostic', 'diagnostic_disk'):
            player, places, queue, session, reports, sender = capture_fixture()
            requests, clock, cache, identity, path = fixture(context={'id': ACCOUNT, 'region': 'eu'},
                                                            captured=queue.captured)
            requests._deliver = reports.arrived
            requests._taking = reports.anything_wanted
            places.current.modes = ['random'] if scenario == 'wrong_arena' else ['ranked']
            log = path + '.jsonl'
            if scenario.startswith('diagnostic'):
                with open(path + '.settings', 'wb') as handle:
                    json.dump({'enabled': True}, handle)
                reports._diagnostic = Diagnostic(settings=path + '.settings',
                        store=os.path.dirname(path) if scenario == 'diagnostic_disk' else log)
                places.forget()
            requests.remember(91)
            requests.drain()
            clock.now += 5
            requests.drain()
            if scenario == 'pause':
                places.current.enabled = False
            original = queue_module.save_json
            def disk_full(*args):
                raise IOError('disk full')
            if scenario == 'disk':
                queue_module.save_json = disk_full
            try:
                cache.answer_now(91, 1, raw(arena=92 if scenario == 'wrong_arena' else 91))
            finally:
                queue_module.save_json = original
            if scenario == 'diagnostic':
                for unused in range(5):
                    clock.now += 21
                    requests.drain()
                check('successfully stored standalone diagnostic never triggers five duplicate requests',
                      not requests.busy() and not queue.all() and len(open(log).readlines()) == 1
                      and cache.asked == [91])
            else:
                check('nonterminal capture decision preserves recovery: %s' % scenario,
                      requests.waiting() == [91]
                      and not requests._journal.entries[('eu', ACCOUNT, 91)].get('abandoned'))
                if scenario == 'pause':
                    requests.drain()
                    check('capture paused in flight causes no new automatic request', cache.asked == [91])
                    places.current.enabled = True
                if scenario in ('disk', 'pause'):
                    clock.now += 21
                    requests.drain()
                    cache.answer_now(91, 1, raw())
                    check('resumed capture settles only after durable queue save: %s' % scenario,
                          not requests.busy() and len(queue.all()) == 1
                          and ('eu', ACCOUNT, 91) not in requests._journal.entries)
    finally:
        if previous is None:
            sys.modules.pop('constants', None)
        else:
            sys.modules['constants'] = previous


def check_recovery_explicit_repair_budget():
    requests, clock, cache, identity, path = fixture()
    requests.remember(91, announced=True)
    requests.drain()
    clock.now += 5
    requests.drain()
    cache.answer_now(91, -1)
    check('ordinary notification cannot reopen an abandoned arena', not requests.remember(91, announced=True))
    check('explicit server repair can use remaining attempts after a policy change', requests.remember(91, repair=True))
    clock.now += 21
    requests.drain()
    check('explicit repair preserves the previous actual attempt counter',
          requests._journal.entries[('eu', '123', 91)]['attempts'] == 2)
    cache.answer_now(91, -1)
    # Exhaust the remaining explicit repair allowance without ever resetting it.
    for unused in range(3):
        requests.remember(91, repair=True)
        clock.now += 21
        requests.drain()
        cache.answer_now(91, -1)
    check('even explicit server repairs cannot exceed the five-attempt budget',
          not requests.remember(91, repair=True) and cache.asked == [91] * 5)
    saved = set()
    requests, clock, cache, identity, path = fixture(captured=lambda key: key in saved)
    requests.remember(92, announced=True)
    saved.add(('eu', '123', 92))
    # A repair poll can answer while a live announcement/hook fills the queue.
    requests.remember(92, repair=True)
    requests.drain()
    clock.now += 5
    requests.drain()
    check('repair arriving during live capture is not satisfied by an older durable report',
          cache.asked == [92] and requests._journal.entries[('eu', '123', 92)]['repair'])
