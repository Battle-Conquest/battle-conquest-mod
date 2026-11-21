"""#1143: real observations plus explicitly synthetic reserve/late variants."""
import copy
import json
import os

from checks.common import REPO, check
from checks.battle_fixtures import ACCOUNT, Bonus


def check_premium_scoring():
    from battle_conquest.quest_details import details_of, capabilities
    from battle_conquest.quest_economy_v2 import metrics
    from battle_conquest.battle_report import report_of

    with open(os.path.join(REPO, 'tools/checks/fixtures/mod_premium_1143.json')) as handle:
        fixture = json.load(handle)
    for index, case in enumerate(fixture['cases']):
        fields = dict(case['fields'])
        check('1143 observed economics %d' % index, metrics(fields, 'random') == case['expected'])
        fields.update(accountDBID=int(ACCOUNT), team=1)
        result = {'arenaUniqueID': 11430 + index, 'personal': {'529': fields},
                  'common': {'bonusType': Bonus.REGULAR, 'arenaCreateTime': 1700000000,
                             'duration': 430, 'winnerTeam': 1}}
        details = details_of(result, Bonus)
        check('1143 transport explicit free XP and premium identity',
              details['economy_version'] == 2 and details['economy']['isPremium'] is True
              and details['economy']['freeXP'] == case['expected']['free_xp_total'])
        # Synthetic field mutation: only the on-screen post-x3 totals are real.
        fields['xp'] = case['user_observed_totals_after_deferred_x3']['xp']
        fields['freeXP'] = case['user_observed_totals_after_deferred_x3']['free_xp']
        fields['factualXP'] = fields['xp'] - fields['eventXP']
        fields['factualFreeXP'] = fields['freeXP']
        check('1143 first late capture excludes deferred reward', metrics(fields, 'random') == case['expected'])
        late = report_of(result, constants=Bonus)
        check('1143 historical XP in new reports also excludes deferred reward', late['metrics']['xp'] == case['expected']['xp_total'])
        for key in ('originalXP', 'subtotalXP', 'eventXP', 'additionalXPFactor10'):
            changed = dict(fields)
            del changed[key]
            check('1143 missing XP does not become zero: ' + key, 'xp_total' not in metrics(changed, 'random'))
        fields['boosterFreeXP'] = None
        check('1143 absent reserve stays unknown', 'free_xp_total' not in metrics(fields, 'random'))
        for key in ('dailyXPFactor10', 'igrXPFactor10'):
            changed = dict(fields)
            changed[key] = 10.0
            check('1143 integer factors stay strict: ' + key, 'xp_total' not in metrics(changed, 'random'))
    synthetic = copy.deepcopy(fixture['cases'][2]['fields'])
    synthetic.update(boosterCreditsFactor100=50, boosterCredits=25280,
                     boosterFreeXPFactor100=200, boosterFreeXP=162)
    for key in ('credits', 'factualCredits'):
        synthetic[key] += 25280
    for key in ('freeXP', 'factualFreeXP'):
        synthetic[key] += 162
    values = metrics(synthetic, 'random')
    check('1143 assumed reserves use explicit gains, retain base and expenses',
          values['credits_net'] == 14287 and values['free_xp_total'] == 243
          and values['free_xp_premium'] == 81 and values['credits_gross'] == 33706)
    check('1143 assumptions are declared separately', capabilities()['assumed_scenarios'] == fixture['assumptions_not_observed'])
