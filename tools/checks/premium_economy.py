"""Real #1052 economics, synthetic client envelopes and defensive variants."""
import copy
import json
import os
import tempfile

from checks.battle_fixtures import ACCOUNT, Bonus, Places, Player
from checks.common import REPO, check


def fixture():
    with open(os.path.join(REPO, 'tools', 'checks', 'fixtures', 'mod_premium_economy_observations.json')) as handle:
        return json.load(handle)


def client_results(index):
    # Numerical fields are real; identity and timing are a test envelope.
    observed = fixture()
    vehicle = dict(observed['common_fields'], **observed['cases'][index]['fields'])
    vehicle.update(typeCompDescr=529, accountDBID=int(ACCOUNT), team=1)
    return {'arenaUniqueID': 10520 + index, 'personal': {'529': vehicle},
            'common': {'bonusType': Bonus.REGULAR, 'arenaCreateTime': 1700000000,
                       'duration': 430, 'winnerTeam': 2}}


def check_premium_economy():
    from battle_conquest.quest_details import details_of, capabilities
    from battle_conquest.battle_reports import BattleReports
    from battle_conquest.report_queue import Queue
    from battle_conquest.report_sender import wire
    from battle_conquest.results_diagnostic import Diagnostic
    from battle_conquest.quest_repairs import Repairs
    from battle_conquest.destinations import Destination, battles_url
    from checks.report_sender import _Session, _Response

    queue = Queue(store=os.path.join(tempfile.mkdtemp(), 'q.json'))
    diagnostic = Diagnostic(settings=os.path.join(tempfile.mkdtemp(), 'absent.json'))
    capture = BattleReports(None, queue=queue, destinations=Places(), account=Player(), diagnostic=diagnostic)
    for index, case in enumerate(fixture()['cases']):
        raw = client_results(index)
        metrics = details_of(raw, Bonus)['metrics']
        check('premium %s: base stays without premium' % index, metrics['xp_base'] == case['fields']['originalXP'])
        check('premium %s: total retains reserves' % index, metrics['xp_total'] == case['fields']['xp'])
        check('premium %s: WG comparison excludes reserves' % index,
              metrics['xp_wg'] == case['wg_tank_after']['xp'] - case['wg_tank_before']['xp'])
        check('event credits remain unverified' if index == 1 else 'observed premium expenses remain signed',
              'credits_net' not in metrics if index == 1 else metrics['credits_net'] == case['calculated_net'])
        check('normal capture without diagnostics accepts premium result', capture.capture(raw, constants=Bonus))
        sent = wire(queue.all()[-1])
        check('normal queue transports distinct XP units and raw observations',
              sent['quest_details']['metrics'] == metrics and sent['metrics']['xp'] == case['fields']['xp']
              and sent['quest_details']['economy']['subtotalXP'] == metrics['xp_wg'])
    raw = client_results(2)
    for key in ('subtotalXP', 'dailyXPFactor10', 'appliedPremiumXPFactor100', 'isPremium',
                'originalXP', 'xp', 'boosterXP', 'additionalXPFactor10', 'igrXPFactor10',
                'achievementXP', 'squadXP', 'eventXP', 'premiumVehicleXP'):
        for value in (None, True, 1.5, '150'):
            changed = copy.deepcopy(raw)
            changed['personal']['529'][key] = value
            # True is the valid observed isPremium flag.
            if key == 'isPremium' and value is True:
                continue
            check('missing/malformed premium XP omitted: %s %r' % (key, value),
                  'xp_wg' not in details_of(changed, Bonus).get('metrics', {}))
    for key, value in [('dailyXPFactor10', 20), ('eventXP', 100), ('boosterXPFactor100', 100),
                       ('premiumVehicleXP', 100), ('xp', 999)]:
        changed = copy.deepcopy(raw)
        changed['personal']['529'][key] = value
        check('unobserved premium XP modifier omitted: %s' % key,
              'xp_wg' not in details_of(changed, Bonus).get('metrics', {}))
    for key in ('autoLoadCost', 'autoRepairCost', 'autoEquipCost', 'autoEquipBoostersCost'):
        changed = copy.deepcopy(raw)
        del changed['personal']['529'][key]
        metrics = details_of(changed, Bonus)['metrics']
        check('absent expense is unknown, XP independent: %s' % key,
              'credits_net' not in metrics and metrics['xp_wg'] == 729)
    for bonus in (Bonus.RANKED, Bonus.COMP7, Bonus.EPIC_BATTLE):
        changed = copy.deepcopy(raw)
        changed['common']['bonusType'] = bonus
        check('premium observation never extends to another mode',
              'xp_wg' not in details_of(changed, Bonus).get('metrics', {})
              and 'credits_net' not in details_of(changed, Bonus).get('metrics', {}))
    changed = copy.deepcopy(raw)
    changed['personal']['530'] = dict(changed['personal']['529'], typeCompDescr=530)
    check('premium respawn totals are unknown', not details_of(changed, Bonus).get('metrics'))
    check('capability names precise premium scope', 'random_single_premium_150' in capabilities()['verified_scenarios'])

    # Cursor phase 0 uses the existing repair transport and owner-bound cache.
    queue.mark(battles_url(), [str(10520 + i) for i in range(3)], account=ACCOUNT)
    queue.settle(lambda mode: [battles_url()], account=ACCOUNT)
    session, asked = _Session(), []
    destination = Destination(battles_url(), enabled=True, modes=['random'], secret='a' * 64)
    places = type('Places', (object,), {'current': destination})()

    class Cache(object):
        def get(self, arena, callback):
            asked.append((arena, callback))

    repairs = Repairs(session, Player(), places, lambda result, source: capture.capture(result, constants=Bonus),
                      garage=lambda: True, cache=lambda: Cache())
    repairs.poll()
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [
        {'arena_unique_id': '10522', 'fields': ['xp_wg'], 'cursor': '0:22'}], 'next_cursor': '0:22'}))
    check('individual premium repair requests original arena', asked[0][0] == 10522)
    asked.pop(0)[1](0, raw)
    check('premium cache result rearms delivered report without changing XP units',
          wire(queue.all()[0])['quest_details']['metrics']['xp_wg'] == 729)

    import battle_conquest.quest_garage_content as content
    original = content.Card
    lines = []

    class Card(object):
        def __init__(self, *args):
            pass

        def text(self, value, *args, **kwargs):
            lines.append(value)

        def finish(self):
            return 1

    try:
        content.Card = Card
        data = {'selected': {'kind': 'individual'}, 'criteria': [{'criterion_type': 'xp'}],
                'battle_feedback': {'totals': {'xp': 809, 'xp_wg': 539}, 'source': 'site'}}
        content.battle_card(None, 400, 0, data)
        check('individual last battle shows WG XP rather than total with reserves',
              any(line.endswith(': 539') for line in lines))
        lines[:] = []
        del data['battle_feedback']['totals']['xp_wg']
        content.battle_card(None, 400, 0, data)
        check('individual last battle leaves unknown WG XP unknown', any(line.endswith(': ?') for line in lines))
        lines[:] = []
        data['selected']['kind'] = 'session'
        data['criteria'][0]['criterion_type'] = 'xp_base'
        data['battle_feedback']['totals']['xp_base'] = 359
        content.battle_card(None, 400, 0, data)
        check('challenge last battle retains base without premium', any(line.endswith(': 359') for line in lines))
    finally:
        content.Card = original
