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
