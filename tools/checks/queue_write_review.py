"""Temporary disk failures retain captures and owner-scoped enrichment."""
import copy

from checks.battle_fixtures import ACCOUNT, Bonus, owned
from checks.common import check
from checks.owner_isolation import fixture, raw, OTHER
from checks.report_sender import _answer


def check_owner_capture_write_failure():
    from battle_conquest import report_queue as module
    player, places, queue, session, reports, sender = fixture()
    # B is already durable; the next write fails while capturing A in the
    # same arena. Losing A cannot be repaired by rereading the old queue file.
    reports.capture(raw(OTHER), constants=Bonus)
    captured = []
    reports.on_capture(lambda report: captured.append(report['account']))
    save = module.save_json
    def unavailable(*args):
        raise IOError('temporary disk failure')
    module.save_json = unavailable
    try:
        check('a temporary write failure still retains the newly captured battle',
              reports.capture(raw(), constants=Bonus)
              and sorted(r['account'] for r in queue.all()) == sorted([ACCOUNT, OTHER]))
        check('retained capture can still wake the ordinary delivery path', captured == [ACCOUNT])
        check('the previous complete disk copy remains readable during failure',
              [r['account'] for r in module.Queue(store=queue._store).all()] == [OTHER])
    finally:
        module.save_json = save
    reports.capture(raw(arena=92), constants=Bonus)
    restored = module.Queue(store=queue._store)
    check('the next successful write includes the retained battle, not only the newest one',
          sorted((r['account'], r['arena_unique_id']) for r in restored.all()) ==
          sorted([(OTHER, '91'), (ACCOUNT, '91'), (ACCOUNT, '92')]))
    sender.drain()
    check('recovered captures leave only with their owner matching proof',
          session.sent[0]['body']['account']['id'] == int(ACCOUNT)
          and len(session.sent[0]['body']['battles']) == 2)
    _answer(session, 200, {'results': [{'index': 0, 'status': 'accepted'},
                                     {'index': 1, 'status': 'accepted'}]})
    check('recovering A does not settle B same-arena report',
          len(queue.all()) == 1 and queue.all()[0]['account'] == OTHER)


def check_owner_enrichment_write_failure():
    from battle_conquest import report_queue as module
    player, places, queue, session, reports, sender = fixture()
    report = owned({'arena_unique_id': '91', 'mode': 'ranked',
                    'metrics': {'xp': 10}, 'quest_details': {'metrics': {'shots': 1}}})
    queue.add(report)
    enriched = copy.deepcopy(report)
    enriched['quest_details']['metrics']['hits'] = 1
    save = module.save_json
    def unavailable(*args):
        raise IOError('temporary disk failure')
    module.save_json = unavailable
    try:
        check('a duplicate stays a duplicate when its enrichment cannot yet be persisted',
              not queue.add(enriched) and len(queue.all()) == 1)
        check('new optional evidence is retained in memory despite the disk failure',
              queue.all()[0]['quest_details']['metrics'] == {'shots': 1, 'hits': 1})
    finally:
        module.save_json = save
    queue.add(owned({'arena_unique_id': '92', 'mode': 'ranked'}))
    restored = module.Queue(store=queue._store)
    check('a later successful write persists the retained evidence without changing historical counters',
          restored.all()[0]['quest_details']['metrics'] == {'shots': 1, 'hits': 1}
          and restored.all()[0]['metrics'] == {'xp': 10})
