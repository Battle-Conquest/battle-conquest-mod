"""Synthetic identity observations; no real WoT field correspondence claimed."""
import copy
from collections import OrderedDict
import json
import os
import shutil
import tempfile

from checks.common import check
from checks.battle_fixtures import results
from checks.results_request import _Cache, _Clock, _Session


def check_identity_projection():
    from battle_conquest.results_identity import observation
    raw = results()
    raw['personal'] = {8721: {'avatarID': 1234567, 'accountDBID': 500111111},
                       2049: {'avatarID': 1234567}, 'avatar': {'id': 1234567}}
    raw['players'] = {1234567: {'accountDBID': 500111111, 'name': 'PRIVATE_OWNER'},
                      7654321: {'accountDBID': 500999999, 'name': 'PRIVATE_ENEMY',
                                'secret': 'PRIVATE_SECRET', 'PRIVATE_NICK_KEY': 5}}
    raw['avatars'] = {1234567: {'accountDBID': 500111111}}
    before = copy.deepcopy(raw)
    origin = {'id': '500111111', 'region': 'eu'}
    current = {'id': '500222222', 'region': 'eu'}
    out = observation(raw, origin, current)
    text = json.dumps(out)
    check('identity observations are explicitly unverified', out['status'] == 'unverified')
    check('origin and receipt are separate contexts', out['contexts']['request']['id'] == '500111111'
          and out['contexts']['receipt']['id'] == '500222222')
    check('no participant scalar, unknown key or secret is serialized',
          all(value not in text for value in ('PRIVATE_OWNER', 'PRIVATE_ENEMY', 'PRIVATE_SECRET',
                                             'PRIVATE_NICK_KEY', '500999999', '1234567', '7654321')))
    personal = out['sections']['personal']['entries']
    players = out['sections']['players']['entries']
    avatar_refs = [field['value']['ref'] for entry in personal
                   for field in entry['value']['entries']
                   if field['key'].get('field') == 'avatarID']
    avatar_ref = avatar_refs[0]
    player = next(entry for entry in players if entry['key']['ref'] == avatar_ref)
    check('personal vehicle references join player mapping keys without selecting one',
          all(ref == avatar_ref for ref in avatar_refs)
          and len(personal) == 3 and len(players) == 2)
    check('context account has the same reference as a candidate result field',
          out['contexts']['request']['reference']['ref'] ==
          next(field['value']['ref'] for field in player['value']['entries']
               if field['key'].get('field') == 'accountDBID'))
    check('projection does not modify game results', raw == before)
    contradictory = observation({'personal': {1: {'accountDBID': 500111111},
                                               2: {'accountDBID': 500222222}}}, origin, current)
    refs = [entry['value']['entries'][0]['value']['ref']
            for entry in contradictory['sections']['personal']['entries']]
    check('contradictory multivehicle candidates remain distinct and unverified',
          len(set(refs)) == 2 and contradictory['status'] == 'unverified'
          and 'owner' not in contradictory)
    missing = observation({'personal': {}}, None, {'id': None, 'region': 'eu'})
    check('missing origin and receipt never infer an owner', missing['contexts']['request'] is None
          and missing['contexts']['receipt']['id'] is None)
    one = observation({'players': {99: {'id': 42}}}, None, None)
    two = observation({'players': {101: {'id': 43}}}, None, None)
    check('references start afresh in every observation', one == two)


def check_identity_limits():
    from battle_conquest.results_identity import observation
    class PrivateObject(object):
        def __repr__(self):
            raise AssertionError('must not stringify a client object')
    out = observation({'personal': {1: {'name': PrivateObject()}},
                       'players': dict((i, {'id': i}) for i in range(200)),
                       'avatars': {'x': [[[[[[[1]]]]]]]}}, None, None)
    text = json.dumps(out)
    check('identity shape collection, depth and unsupported values are bounded',
          'item limit' in text and 'depth limit' in text and 'unsupported' in text)
    crowded = OrderedDict(('metric%d' % i, i) for i in range(128))
    crowded['accountDBID'] = 500111111
    projected = observation({'personal': {1: crowded}}, None, None)
    check('identity candidates survive the field limit regardless of dictionary order',
          'accountDBID' in json.dumps(projected) and 'item limit' in json.dumps(projected))
    huge = observation({'players': dict((i, list(range(128))) for i in range(128))}, None, None)
    check('identity projection has a global visited-value budget', 'value limit' in json.dumps(huge))


def check_identity_storage():
    from battle_conquest.results_diagnostic import Diagnostic
    from battle_conquest import config
    folder = tempfile.mkdtemp()
    try:
        settings = os.path.join(folder, 'settings.json')
        store = os.path.join(folder, 'observations.jsonl')
        diagnostic = Diagnostic(settings=settings, store=store)
        raw = results()
        def options(identity):
            with open(settings, 'wb') as handle:
                json.dump({'enabled': True, 'identity_enabled': identity}, handle)
        for value in (False, 'true', 1, None):
            options(value)
            check('identity requires explicit boolean opt-in', diagnostic.capture(raw, 'hook', '500111111'))
        options(True)
        class Wrapped(object):
            personal = type('Personal', (object,), {'_PersonalInfo__personal': raw})()
        check('a wrapped stale repair result is observed like a normal arrival',
              diagnostic.capture(Wrapped(), 'stale repair', '500111111',
                                 {'id': '500111111', 'region': config.REGION}))
        check('identity observation survives an unknown account', diagnostic.capture(raw, 'cache', None,
              {'id': '500111111', 'region': config.REGION}))
        with open(store, 'rb') as handle:
            lines = [json.loads(line) for line in handle]
        check('no identity section without explicit opt-in', all('identity' not in line for line in lines[:-2]))
        check('unknown legacy tracker account remains null', lines[-1]['account'] is None
              and lines[-1]['identity']['contexts']['request']['id'] == '500111111')
        options(True)
        limited = Diagnostic(settings=settings, store=store, limit=128)
        check('identity uses the existing record limit', not limited.capture(raw, 'hook', '500111111'))
        broken = Diagnostic(settings=settings, store=folder)
        check('identity disk errors remain contained', not broken.capture(raw, 'hook', '500111111'))
        with open(settings, 'wb') as handle:
            json.dump({'enabled': False, 'identity_enabled': True}, handle)
        check('master switch disables identity capture', not diagnostic.capture(raw, 'hook', '500111111'))
    finally:
        shutil.rmtree(folder)


def check_identity_request_context():
    from battle_conquest.results_request import Requests
    account = {'id': '500111111', 'region': 'eu'}
    cache = _Cache()
    clock = _Clock()
    taken = []
    request = Requests(_Session(), lambda raw, source, origin: taken.append(origin),
                       garage=lambda: True, cache=lambda: cache, now=clock,
                       context=lambda: account)
    request.remember(101)
    request.remember(102)
    request.drain()
    late = cache._pending[101]
    account['id'] = '500222222'
    clock.now += 61
    request.drain()
    cache.answer_now(102, 1, results())
    late(1, results())
    check('late response keeps the snapshot from its own request after timeout and switch',
          taken == [{'id': '500222222', 'region': 'eu'}, {'id': '500111111', 'region': 'eu'}])
    def broken_context():
        raise ValueError('broken diagnostic context')
    delivered = []
    request = Requests(_Session(), lambda raw, source, origin: delivered.append(origin),
                       garage=lambda: True, cache=lambda: _Cache({103: (1, results())}),
                       context=broken_context)
    request.remember(103)
    request.drain()
    check('a failed context snapshot never blocks ordinary result delivery', delivered == [None])


def check_identity_capture_context():
    from battle_conquest.battle_reports import BattleReports
    class Observer(object):
        def capture(self, raw, source, account, origin=None):
            self.origin = origin
    observer = Observer()
    reports = BattleReports(_Session(), diagnostic=observer)
    reports.arrived(results(), 'cache', {'id': '500111111', 'region': 'eu'})
    check('requested capture passes origin to diagnostic without changing the report',
          observer.origin == {'id': '500111111', 'region': 'eu'})


def check_identity_repair_context():
    from battle_conquest.quest_repairs import Repairs
    from battle_conquest.destinations import Destination, battles_url
    from checks.report_sender import _Session as HttpSession, _Response
    session = HttpSession()
    account = type('Account', (object,), {'account': '500111111'})()
    places = type('Places', (object,), {'current': Destination(
        battles_url(), enabled=True, modes=['random'], secret='a' * 64)})()
    cache = _Cache()
    normal, stale = [], []
    repairs = Repairs(session, account, places, lambda *args: normal.append(args),
                      garage=lambda: True, cache=lambda: cache,
                      context=lambda: {'id': account.account, 'region': 'eu'},
                      observe_stale=lambda *args: stale.append(args))
    repairs.poll()
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [{'arena_unique_id': '123'}]}))
    account.account = '500222222'
    cache.answer_now(123, 1, results())
    check('stale repair is observed with original identity but never captured for the new account',
          not normal and len(stale) == 1
          and stale[0][2] == {'id': '500111111', 'region': 'eu'})
