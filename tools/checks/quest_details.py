"""Real observed correspondences; synthetic edge cases do not validate WoT economics."""
import copy
import json
import os
import tempfile

from checks.battle_fixtures import Bonus
from checks.common import REPO, check


def check_quest_details():
    from battle_conquest.quest_details import capabilities, details_of, fill, header, observations
    from battle_conquest.battle_report import report_of
    from battle_conquest.report_sender import wire
    from battle_conquest.report_queue import Queue

    with open(os.path.join(REPO, 'tools', 'checks', 'fixtures', 'mod_quest_observations.json')) as handle:
        fixtures = json.load(handle)
    for index, original in enumerate(fixtures):
        raw = copy.deepcopy(original)
        raw['arenaUniqueID'] = 18446744073709551000 + index
        details = details_of(raw, Bonus)
        check('observed battle %d: exact screen measurements' % (index + 1), details['metrics'] == raw['expected'])
        check('observed vehicle is retained', details['vehicles'] == [45057])
        report = report_of(raw, constants=Bonus)
        check('historical XP keeps its meaning', report['metrics']['xp'] == raw['expected']['xp_total'])
        check('extension travels without diagnostics or internal queue state',
              wire(report)['quest_details'] == details and 'diagnostic' not in json.dumps(wire(report)))
    raw = copy.deepcopy(fixtures[1])
    vehicle = raw['personal']['45057']
    vehicle['shots'] = None
    vehicle['directHits'] = 0
    vehicle['piercings'] = True
    vehicle['explosionHits'] = 1.0
    details = details_of(raw, Bonus)
    check('missing, zero, bool and float remain distinct',
          'shots' not in details['metrics'] and details['metrics']['hits'] == 0
          and 'piercings' not in details['metrics'] and 'explosion_hits' not in details['metrics'])
    del vehicle['autoLoadCost']
    check('a missing expense cannot become zero', 'credits_net' not in details_of(raw, Bonus)['metrics'])
    raw = copy.deepcopy(fixtures[0])
    raw['personal']['45057']['isPremium'] = True
    raw['personal']['45057']['appliedPremiumCreditsFactor100'] = 150
    raw['personal']['45057']['appliedPremiumXPFactor100'] = 150
    details = details_of(raw, Bonus)
    check('untested premium economics stay raw with no claimed measure',
          'credits_net' not in details['metrics'] and 'xp_base' not in details['metrics']
          and details['economy']['appliedPremiumCreditsFactor100'] == 150)
    raw = copy.deepcopy(fixtures[0])
    raw['personal']['45057']['autoRepairCost'] = 50000
    check('signed-net transport never clips a loss (synthetic input)', details_of(raw, Bonus)['metrics']['credits_net'] < 0)
    raw['personal']['45057']['boosterCredits'] = 100
    check('unverified bonuses omit net rather than guessing', 'credits_net' not in details_of(raw, Bonus)['metrics'])
    raw = copy.deepcopy(fixtures[0])
    del raw['common']['arenaCreateTime']
    check('no clock substitutes for an absent start', 'started_at' not in details_of(raw, Bonus))
    raw['personal']['1'] = dict(raw['personal']['45057'], typeCompDescr=1)
    details = details_of(raw, Bonus)
    check('all vehicles retained, unverified respawn totals omitted', details['vehicles'] == [1, 45057] and 'metrics' not in details)
    del raw['personal']['1']['typeCompDescr']
    check('an incomplete vehicle list is not presented as complete', 'vehicles' not in details_of(raw, Bonus))

    class Types(Bonus):
        TRAINING_COMP7 = 123
        EPIC_BATTLE_TRAINING = 124
        TOURNAMENT_COMP7 = 125
        CLAN = 126

    for bonus in [Types.TRAINING, Types.TRAINING_COMP7, Types.EPIC_BATTLE_TRAINING, Types.TOURNAMENT_COMP7, Types.CLAN, 999, True]:
        raw['common']['bonusType'] = bonus
        check('training/unknown variants provide no challenge eligibility: %s' % bonus, details_of(raw, Types) is None)
    for bonus, mode in [(Bonus.REGULAR, 'random'), (Bonus.RANKED, 'ranked'), (Bonus.COMP7, 'onslaught'),
                        (Bonus.SORTIE_2, 'stronghold'), (Bonus.EPIC_BATTLE, 'frontline')]:
        raw['common']['bonusType'] = bonus
        check('explicit identified mode: %s' % mode, details_of(raw, Types)['mode'] == mode)
    merged = fill({'metrics': {'shots': 0}, 'vehicles': [1]}, {'metrics': {'shots': 9, 'hits': 4}, 'vehicles': [2]})
    check('enrichment never overwrites known zeroes or lists', merged == {'metrics': {'shots': 0, 'hits': 4}, 'vehicles': [1]})
    check('capabilities available with no battles, validation scope explicit',
          json.loads(header()) == capabilities() and 'premium' not in capabilities()['verified_scenarios'])
    queue = Queue(store=os.path.join(tempfile.mkdtemp(), 'q.json'))
    first = {'arena_unique_id': '1', 'account': '1', 'metrics': {'xp': 10}, 'quest_details': {'metrics': {'shots': 0}}}
    queue.add(first)
    queue.add(dict(first, metrics={'xp': 999}, quest_details={'metrics': {'shots': 9, 'hits': 4}}))
    stored = Queue(store=queue._store).all()[0]
    check('richer arrivals persist only missing details, historical counters intact',
          stored['metrics']['xp'] == 10 and stored['quest_details']['metrics'] == {'shots': 0, 'hits': 4})

    import battle_conquest.battle_report as reader
    original_reader = reader.details_of
    try:
        def broken(*args):
            raise ValueError('client shape changed')
        reader.details_of = broken
        raw = copy.deepcopy(fixtures[0])
        raw['arenaUniqueID'] = 123
        check('an optional-reader failure never loses the historical report',
              reader.report_of(raw, constants=Bonus)['metrics']['xp'] == 374)
    finally:
        reader.details_of = original_reader

    from checks.report_sender import _queue, _sender, _answer, _took
    queue = _queue(count=50)
    for report in queue._reports:
        report['quest_details'] = {'vehicle_observations': [{'fields': observations(fixtures[0]['personal']['45057'])}] * 64}
    session, sender = _sender(queue)
    sender.drain()
    sizes, counts = [], []
    while session.sent:
        count = len(session.sent[0]['body']['battles'])
        counts.append(count)
        sizes.append(len(json.dumps(session.sent[0]['body'])))
        _answer(session, 200, _took(count))
    check('wide reports are split below the body limit without losing any battle',
          sum(counts) == 50 and len(counts) > 1 and max(sizes) <= 240000 and queue.all() == [])

    queue = _queue(count=1)
    session, sender = _sender(queue)
    sender.drain()
    queue.add(dict(queue.all()[0], quest_details={'metrics': {'hits': 4}}))
    _answer(session, 200, {'accepted': 1, 'duplicates': 0, 'rejected': 0,
                          'results': [{'index': 0, 'status': 'accepted'}]})
    check('details arriving during a request stay queued after acceptance', len(queue.all()) == 1)
    sender.drain()
    check('the next request supplies the late details', session.sent[0]['body']['battles'][0]['quest_details']['metrics']['hits'] == 4)
    _answer(session, 200, {'results': [{'index': 0, 'status': 'duplicate'}]})
    check('the enriched duplicate settles once its fields were sent', queue.all() == [])
    queue = _queue(count=1)
    session, sender = _sender(queue)
    sender.drain()
    queue.add(dict(queue.all()[0], quest_details={'metrics': {'hits': 4}}))
    _answer(session, 200, {'results': [{'index': 0, 'status': 'rejected'}]})
    check('late details never retry a rejected report', queue.all() == [])
    queue = _queue(count=1)
    from checks.report_sender import OTHER_ACCOUNT, HERE
    queue.add(dict(queue.all()[0], account=OTHER_ACCOUNT))
    session, sender = _sender(queue)
    sender.drain()
    _answer(session, 200, _took(1))
    check('the same arena on a second account is not acknowledged for the first',
          len(queue.all()) == 1 and queue.all()[0]['account'] == OTHER_ACCOUNT)

    queue = _queue(count=1)
    session, sender = _sender(queue)
    sender.drain()
    _answer(session, 200, {'results': 1})
    check('an unreadable verdict list still settles the final HTTP 200', queue.all() == [])
