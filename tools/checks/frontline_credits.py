"""Observed Frontline credits, with synthetic envelopes and defensive variants."""
import calendar
import copy
import json
import os
import tempfile
import time

from checks.battle_fixtures import ACCOUNT, Bonus, Places, Player
from checks.common import REPO, check


def fixture():
    with open(os.path.join(REPO, 'tools', 'checks', 'fixtures', 'mod_frontline_credits_1050.json')) as handle:
        return json.load(handle)


def client_results():
    """Only economics are real: reconstruct timing/identity for normal capture.

    The received report does not contain the original client envelope or each
    vehicle's capture points. Do not present this reconstruction as a capture.
    """
    report = fixture()['report']
    start = calendar.timegm(time.strptime(report['quest_details']['started_at'], '%Y-%m-%dT%H:%M:%SZ'))
    end = calendar.timegm(time.strptime(report['finished_at'], '%Y-%m-%dT%H:%M:%SZ'))
    personal = {'avatar': {'accountDBID': int(ACCOUNT), 'team': 1}}
    for observed in report['quest_details']['vehicle_observations']:
        personal[str(observed['tank_id'])] = dict(observed['fields'],
                                                 typeCompDescr=observed['tank_id'],
                                                 team=1, accountDBID=int(ACCOUNT))
    return {'arenaUniqueID': 1050, 'personal': personal,
            'common': {'bonusType': Bonus.EPIC_BATTLE, 'arenaCreateTime': start,
                       'duration': end - start, 'winnerTeam': 1}}


def measures(raw):
    from battle_conquest.quest_details import details_of
    return details_of(raw, Bonus).get('metrics', {})


def check_frontline_credits():
    from battle_conquest.battle_reports import BattleReports
    from battle_conquest.quest_details import capabilities, details_of, frontline_credits
    from battle_conquest.report_queue import Queue
    from battle_conquest.report_sender import wire
    from battle_conquest.results_diagnostic import Diagnostic

    raw = client_results()
    expected = fixture()['expected']
    check('real Frontline earnings match both displayed totals', measures(raw) == expected)
    check('real losing vehicle contributes its signed loss',
          frontline_credits([raw['personal']['23073']])['credits_net'] == -5624)
    check('no unobserved premium flag was added to the real economics',
          all('isPremium' not in v for k, v in raw['personal'].items() if k != 'avatar'))
    details = details_of(raw, Bonus)
    check('complete Frontline vehicle evidence remains available', details['vehicles'] == [23073, 45057, 51361])
    check('multi-vehicle support is scoped to the verified Frontline scenario',
          'frontline_multi_standard' in capabilities()['verified_scenarios']
          and 'multi_vehicle' not in capabilities()['verified_scenarios'])
    queue = Queue(store=os.path.join(tempfile.mkdtemp(), 'q.json'))
    diagnostic = Diagnostic(settings=os.path.join(tempfile.mkdtemp(), 'absent.json'))
    check('the Frontline regression explicitly disables diagnostics', not diagnostic.enabled())
    capture = BattleReports(None, queue=queue, destinations=Places(), account=Player(), diagnostic=diagnostic)
    check('normal capture works with diagnostics absent', capture.capture(raw, constants=Bonus))
    sent = wire(queue.all()[0])
    check('credit measurements travel through the real queue without diagnostics',
          sent['quest_details']['metrics'] == expected and 'diagnostic' not in json.dumps(sent))
    check('historical multi-vehicle XP and damage are unchanged',
          sent['metrics']['xp'] == 11415 and sent['metrics']['damage_dealt'] == 9560
          and 'xp_base' not in details['metrics'] and 'vehicle' not in sent)
    capture.capture(raw, constants=Bonus)
    check('reopening keeps a single queued battle with stable credits',
          len(queue.all()) == 1 and queue.all()[0]['quest_details']['metrics'] == expected)

    for key in ('autoRepairCost', 'autoLoadCost', 'autoEquipCost', 'autoEquipBoostersCost'):
        for value in (None, 'absent', True, -1, 1.5, [0], [False, 0]):
            changed = copy.deepcopy(raw)
            vehicle = changed['personal']['23073']
            if value == 'absent':
                del vehicle[key]
            else:
                vehicle[key] = value
            check('unknown/invalid cost omits only net: %s %r' % (key, value),
                  measures(changed) == {'credits_gross': expected['credits_gross']})
    changed = copy.deepcopy(raw)
    for key, vehicle in changed['personal'].items():
        if key != 'avatar':
            vehicle.update(autoRepairCost=0, autoLoadCost=[0, 999], autoEquipCost=[0, 999, 999],
                           autoEquipBoostersCost=[0, 999, 999], equipmentValue=99999, ammoValue=99999)
    check('known zero debits, inventory values and other currencies never charge credits',
          measures(changed) == {'credits_gross': 157530, 'credits_net': 157530})
    changed = copy.deepcopy(raw)
    changed['personal']['51361']['autoRepairCost'] = 200000
    check('a negative battle net remains signed', measures(changed)['credits_net'] == -89221)
    changed = copy.deepcopy(raw)
    changed['personal']['avatar'].update(changed['personal']['51361'])
    check('avatar earnings and expenses are never added to vehicle totals', measures(changed) == expected)

    for key in ('petSystemCredits', 'boosterCredits', 'orderCredits', 'eventCredits',
                'achievementCredits', 'premSquadCredits', 'referral20Credits',
                'wotPlusCredits', 'wotPlusProBoostCredits', 'appliedPremiumCreditsFactor100',
                'originalCredits', 'credits', 'factualCredits'):
        for value in (None, 'absent', True, 1.5, -1, 150):
            changed = copy.deepcopy(raw)
            if value == 'absent':
                del changed['personal']['51361'][key]
            else:
                changed['personal']['51361'][key] = value
            check('unsupported/incomplete economics stay raw: %s %r' % (key, value), not measures(changed))
    for premium in (True, 1, 'false'):
        changed = copy.deepcopy(raw)
        changed['personal']['51361']['isPremium'] = premium
        check('a premium or malformed explicit flag cannot claim standard economics: %r' % premium,
              not measures(changed))
    for key in ('missing', 'invalid', 'duplicate', 'extra', 'too_many'):
        changed = copy.deepcopy(raw)
        if key == 'missing':
            del changed['personal']['51361']['typeCompDescr']
        elif key == 'invalid':
            changed['personal']['51361']['typeCompDescr'] = True
        elif key == 'duplicate':
            changed['personal']['51361']['typeCompDescr'] = 23073
        elif key == 'extra':
            changed['personal']['unknown'] = None
        else:
            for tank in range(1, 65):
                changed['personal'][str(tank)] = dict(changed['personal']['51361'], typeCompDescr=tank)
        check('incomplete or ambiguous vehicles cannot prove totals: %s' % key, not measures(changed))
    changed = copy.deepcopy(raw)
    changed['common']['bonusType'] = Bonus.REGULAR
    check('other multi-vehicle modes remain unverified', not measures(changed))
    changed = copy.deepcopy(raw)
    changed['personal'] = {'51361': changed['personal']['51361']}
    check('the new Frontline case does not infer single-vehicle economics',
          'credits_gross' not in measures(changed))
    changed = copy.deepcopy(raw)
    for key, vehicle in changed['personal'].items():
        if key != 'avatar':
            vehicle.update(originalCredits=100000000, credits=100000000, factualCredits=100000000)
    check('aggregate credit overflow is not transported', not measures(changed))
    check_frontline_repair(raw, capture, queue)


def check_frontline_repair(raw, capture, queue):
    from battle_conquest.destinations import Destination, battles_url
    from battle_conquest.quest_repairs import Repairs
    from checks.report_sender import _Session, _Response

    # Once the old report was acknowledged, a real cache result can rearm it
    # as an enriched duplicate, using the same owner and delivery path.
    queue.mark(battles_url(), ['1050'], account=ACCOUNT)
    queue.settle(lambda mode: [battles_url()], account=ACCOUNT)
    check('the previously delivered Frontline battle has left the pending queue', not queue.all())
    session, asked = _Session(), []
    destination = Destination(battles_url(), enabled=True, modes=['frontline'], secret='a' * 64)
    places = type('Places', (object,), {'current': destination})()

    class Cache(object):
        def get(self, arena, callback):
            asked.append((arena, callback))

    def deliver(results, source):
        capture.capture(results, constants=Bonus)

    repairs = Repairs(session, Player(), places, deliver, garage=lambda: True, cache=lambda: Cache())
    repairs.poll()
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [
        {'arena_unique_id': '1050', 'fields': ['credits_gross', 'credits_net']}]}))
    check('targeted repair asks the cache for the original Frontline arena', asked[0][0] == 1050)
    asked.pop(0)[1](0, raw)
    check('recovered Frontline credits rearm the acknowledged battle for completion',
          len(queue.all()) == 1 and queue.all()[0]['quest_details']['metrics'] == fixture()['expected'])
    repairs.poll()
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [{'arena_unique_id': '1050'}]}))
    check('the same still-missing server request does not repeatedly reopen the cache', not asked)
