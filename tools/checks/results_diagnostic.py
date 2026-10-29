"""Synthetic shape/error checks, not evidence of WoT economic semantics."""
import copy
import json
import os
import shutil
import sys
import tempfile
import types

from checks.battle_fixtures import ACCOUNT, Bonus, Places, Player, results
from checks.common import check


def _constants():
    module = types.ModuleType('constants')
    module.ARENA_BONUS_TYPE = Bonus
    sys.modules['constants'] = module


def _enable(path, value=True):
    with open(path, 'wb') as handle:
        json.dump({'enabled': value}, handle)


def _read(path):
    with open(path, 'rb') as handle:
        return [json.loads(line) for line in handle]


def check_diagnostic_projection():
    from battle_conquest.results_diagnostic import observation
    _constants()
    raw = results(vehicle={'credits': -1234, 'originalCredits': 0, 'originalXP': None,
                           'autoLoadCost': (42, 0), 'autoEquipCost': {'123': [7, 0]},
                           'premiumXPFactor10': 15, 'typeCompDescr': 8721,
                           'playerName': 'NEVER_STORE_PLAYER_NAME',
                           'accountDBID': 999999999, 'secret': 'NEVER_STORE_SECRET'})
    raw['personal']['avatar'].update({'credits': 22, 'xp': 0})
    raw['personal']['2049'] = {'team': 1, 'typeCompDescr': 2049, 'credits': 9}
    raw['players'] = {'ENEMY': {'credits': 66666666, 'name': 'NEVER_STORE_ENEMY'}}
    raw['vehicles'] = {'ENEMY': {'damageDealt': 66666666}}
    raw['common']['accountDBID'] = 66666666
    before = copy.deepcopy(raw)
    out = observation(raw, 'test', ACCOUNT, 'test-version', now=lambda: 0)
    first, second = out['vehicles']
    fields = second['fields']
    check('diagnostic keeps each personal vehicle separate',
          first['personal_key'] == '2049' and second['personal_key'] == '8721'
          and first['fields']['credits'] == 9)
    check('signed, zero, null and absent remain distinct',
          fields['credits'] == -1234 and fields['originalCredits'] == 0
          and fields['originalXP'] is None and 'creditsPenalty' not in fields)
    check('numeric cost structures and factors keep their raw values',
          fields['autoLoadCost'] == [42, 0] and fields['autoEquipCost'] == {'123': [7, 0]}
          and fields['premiumXPFactor10'] == 15)
    check('personal avatar totals are observed without adding them to vehicles',
          out['avatar']['fields']['credits'] == 22 and out['avatar']['fields']['xp'] == 0)
    check('raw timing is separate from UTC observation time, without a fabricated end',
          out['common']['arenaCreateTime'] == raw['common']['arenaCreateTime']
          and out['common']['duration'] == 600 and out['observed_at'] == '1970-01-01T00:00:00Z'
          and 'finished_at' not in out)
    check('arena ids keep all unsigned 64-bit digits and account is explicit',
          out['arena_unique_id'] == '12457893456789012345' and out['account'] == ACCOUNT)
    text = json.dumps(out)
    check('other players, secrets and unrelated personal values never enter the projection',
          'NEVER_STORE' not in text and '66666666' not in text and '999999999' not in text)
    check('unknown field names remain discoverable without their values',
          'playerName' in second['available_fields'] and 'playerName' not in fields)
    check('diagnostic does not mutate results shared with normal capture', raw == before)
    for kind, label in [(Bonus.REGULAR, 'random'), (Bonus.RANKED, 'ranked'),
                        (Bonus.COMP7, 'onslaught'), (Bonus.SORTIE_2, 'stronghold'),
                        (Bonus.EPIC_BATTLE, 'frontline'), (Bonus.TRAINING, 'training'),
                        (99999, 'other')]:
        probe = observation(results(common={'bonusType': kind}), 'test', ACCOUNT, 'test')
        check('diagnostic records raw type and current mapping for ' + label,
              probe['common']['bonusType'] == kind and probe['mode_as_current_mod'] == label)
    no_time = results()
    del no_time['common']['arenaCreateTime']
    del no_time['common']['duration']
    check('missing battle time is never replaced by observation time',
          'arenaCreateTime' not in observation(no_time, 'test', ACCOUNT, 'test')['common'])
    check('no account, arena or readable personal payload is never guessed',
          observation(raw, 'test', None, 'test') is None
          and observation(results(arenaUniqueID=None), 'test', ACCOUNT, 'test') is None
          and observation(dict(raw, personal=None), 'test', ACCOUNT, 'test') is None)


def check_diagnostic_bounded_values():
    from battle_conquest.results_diagnostic import observation
    _constants()

    class SecretObject(object):
        def __repr__(self):
            raise AssertionError('must never stringify client data')

    cycle = []
    cycle.append(cycle)
    raw = results(vehicle={'credits': SecretObject(), 'xp': float('nan'),
                           'autoLoadCost': cycle, 'autoEquipCost': list(range(129)),
                           'xpText': 'SECRET_TEXT', 'xpInfinity': float('inf')})
    out = observation(raw, 'test', ACCOUNT, 'test')
    encoded = json.dumps(out, allow_nan=False)
    fields = out['vehicles'][0]['fields']
    check('unsupported and non-finite values are explicit without repr or secret text',
          fields['credits'] == {'diagnostic_omitted': 'unsupported value'}
          and fields['xp'] == {'diagnostic_omitted': 'non-finite'}
          and 'SECRET_TEXT' not in encoded)
    check('cycles and excessive collections are bounded and explicitly marked',
          'depth limit' in encoded and fields['autoEquipCost']['diagnostic_omitted'] == 'item limit')
    shared = [list(range(128))] * 128
    large = observation(results(vehicle={'autoLoadCost': shared}), 'test', ACCOUNT, 'test')
    check('a shared large tree has a total work budget', 'value limit' in json.dumps(large))
    raw['personal']['8721'].update({'field%d' % i: i for i in range(300)})
    check('excessive field inventories disclose truncation',
          observation(raw, 'test', ACCOUNT, 'test')['vehicles'][0]['field_names_truncated'])


def check_diagnostic_storage():
    from battle_conquest.results_diagnostic import Diagnostic
    _constants()
    root = tempfile.mkdtemp()
    try:
        settings, store = os.path.join(root, 'diagnostics.json'), os.path.join(root, 'data.jsonl')
        diagnostic = Diagnostic(settings, store, version='test')
        check('missing settings disable capture without creating a file',
              not diagnostic.capture(results(), 'test', ACCOUNT) and not os.path.exists(store))
        for value in [False, 1, 'true', None]:
            _enable(settings, value)
            check('only the literal boolean true enables capture: %r' % value,
                  not diagnostic.enabled())
        with open(settings, 'wb') as handle:
            handle.write('{"enabled":')
        check('broken settings disable capture', not diagnostic.enabled())
        with open(settings, 'wb') as handle:
            handle.write('{"enabled":true}' + ' ' * 1024)
        check('oversized settings disable capture', not diagnostic.enabled())
        _enable(settings)
        check('explicit activation writes a JSONL observation',
              diagnostic.capture(results(), 'test', ACCOUNT) and len(_read(store)) == 1)
        # Keep repeated arrivals: later paths can carry additional fields. They
        # are observations, never reports that can be summed or sent.
        diagnostic.capture(results(vehicle={'credits': -1}), 'another hook', ACCOUNT)
        diagnostic.capture(results(), 'test', '500999999')
        records = _read(store)
        check('repeated arenas and account changes stay identifiable',
              len(records) == 3 and records[0]['arena_unique_id'] == records[1]['arena_unique_id']
              and records[1]['vehicles'][0]['fields']['credits'] == -1
              and records[2]['account'] == '500999999')
        _enable(settings, False)
        check('disabling immediately stops writes and preserves evidence',
              not diagnostic.capture(results(), 'test', ACCOUNT) and _read(store) == records)
        _enable(settings)
        with open(store, 'ab') as handle:
            handle.write('{"partial":')
        check('an interrupted final line does not corrupt the next observation',
              diagnostic.capture(results(arenaUniqueID=99), 'test', ACCOUNT)
              and _read_last(store)['arena_unique_id'] == '99')
        store2 = os.path.join(root, 'bounded.jsonl')
        small = Diagnostic(settings, store2, limit=1800)
        for i in range(6):
            check('bounded store accepts the next observation',
                  small.capture(results(arenaUniqueID=i + 1), 'test', ACCOUNT))
        check('rotation keeps only current and previous files under the bound',
              os.path.getsize(store2) <= 1800 and os.path.getsize(store2 + '.1') <= 1800
              and not os.path.exists(store2 + '.2')
              and _read(store2)[-1]['arena_unique_id'] == '6')
        restarted = Diagnostic(settings, store2, limit=1800)
        check('capture resumes after restart with the same size bound',
              restarted.capture(results(arenaUniqueID=8), 'test', ACCOUNT)
              and _read(store2)[-1]['arena_unique_id'] == '8')
        too_small = Diagnostic(settings, os.path.join(root, 'tiny'), limit=1)
        check('oversized observations are refused explicitly',
              not too_small.capture(results(), 'test', ACCOUNT) and not os.path.exists(too_small._store))
        broken_disk = Diagnostic(settings, root)
        check('disk failures do not escape the diagnostic',
              not broken_disk.capture(results(), 'test', ACCOUNT))
    finally:
        shutil.rmtree(root)


def _read_last(path):
    with open(path, 'rb') as handle:
        return json.loads(handle.readlines()[-1])


def check_diagnostic_capture_integration():
    from battle_conquest.battle_report import report_of
    from battle_conquest.battle_reports import BattleReports
    from battle_conquest.report_queue import Queue
    from battle_conquest.results_diagnostic import Diagnostic
    from checks.battle_report_hooks import _Both
    from battle_conquest.runtime.session import Session
    _constants()
    root = tempfile.mkdtemp()
    session = Session(0)
    try:
        settings, store = os.path.join(root, 'settings'), os.path.join(root, 'diagnostic')
        diagnostic = Diagnostic(settings, store)
        queue = Queue(store=os.path.join(root, 'queue'))
        player = Player()
        reports = BattleReports(session, queue=queue, destinations=Places(False),
                                account=player, diagnostic=diagnostic)
        check('disabled diagnostic does not ask for battles while sending is paused',
              not reports.anything_wanted())
        _enable(settings)
        check('opted-in diagnostic can fetch battles independently from site modes/pause',
              reports.anything_wanted())
        reports.arrived(results(common={'bonusType': Bonus.TRAINING}), 'cache answer')
        check('diagnostic sees excluded modes without putting them in the send queue',
              not queue.all() and _read(store)[0]['common']['bonusType'] == Bonus.TRAINING)
        reports._destinations = Places()
        reports._from_event(results())
        reports._from_account(True, results())
        service = _Both()
        reports._wrap_post(type(service).postResult)(service, results())
        expected = report_of(results(), constants=Bonus)
        expected['account'] = ACCOUNT
        expected['owner'] = {'id': int(ACCOUNT), 'region': 'eu'}
        check('all arrival paths observe results and historical reports remain identical',
              len(_read(store)) == 4 and queue.all() == [expected])
        check('diagnostic fields never enter persisted reports or the wire metrics',
              'diagnostic' not in json.dumps(queue.all()) and 'credits' not in json.dumps(queue.all()))
        player.account = None
        reports.arrived(results(arenaUniqueID=9))
        check('unknown login skips legacy diagnostic but preserves a result-owned report',
              len(_read(store)) == 4 and len(queue.all()) == 2 and queue.all()[-1]['account'] == ACCOUNT)

        class Broken(object):
            def capture(self, *args):
                raise IOError('secret must not be logged')

        player.account = ACCOUNT
        reports._diagnostic = Broken()
        reports.arrived(results(arenaUniqueID=10))
        check('even an unexpected diagnostic exception cannot block the normal capture',
              len(queue.all()) == 3 and queue.all()[-1]['arena_unique_id'] == '10')
    finally:
        session.close()
        shutil.rmtree(root)
