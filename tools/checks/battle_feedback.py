"""Provisional capture, immediate delivery and authoritative receipt races."""
import copy

from checks.common import check
from checks.report_sender import _Session, _Response, _places, _destination, _queue
from checks.battle_fixtures import ACCOUNT, Player, results, Bonus


class Timers(_Session):
    def __init__(self):
        _Session.__init__(self)
        self.callbacks = []

    def callback(self, delay, func):
        self.callbacks.append(func)

    def flush(self):
        for unused in range(10):
            callbacks, self.callbacks = self.callbacks, []
            if not callbacks:
                return
            for func in callbacks:
                func()
        raise AssertionError('callbacks did not settle')

    def on_close(self, func):
        pass


class View(object):
    def visible(self, value, preserve_draft=False):
        pass
    def render(self, garage):
        self.data = garage.display_data()
    def reset(self):
        pass
    def close(self):
        pass


def fixture():
    from battle_conquest.destinations import battles_url
    from battle_conquest.battle_feedback import Feedback
    from battle_conquest.battle_reports import BattleReports
    from battle_conquest.report_sender import Sender
    from battle_conquest.quest_garage import Garage
    session, queue, player = Timers(), _queue(count=0), Player()
    player.on_change = lambda callback: None
    place = _destination(url=battles_url(), modes=['other'])
    places = _places(place)
    places.current = place
    places.wanting = lambda mode: [place.url] if mode in place.modes else []
    garage = Garage(session, player, places, View(), garage=lambda: True, ready=lambda: True, platoon=lambda: [], now=lambda: 100.0)
    garage.key, garage.last_poll = garage.identity(), 100.0
    garage.data = {'schema': 1, 'config': {'version': 1, 'selection': 'session:1', 'mode': 'manual', 'manual_ids': []},
                   'choices': [], 'selected': {'title': 'Damage', 'status': 'running'},
                   'criteria': [{'criterion_type': 'damage_dealt', 'target_value': 20000}],
                   'players': [{'username': 'Self', 'participant': True, 'official': {
                       'available': True, 'battles': 0, 'totals': {'damage_dealt': 0}}}]}
    reports = BattleReports(session, queue=queue, destinations=places, account=player)
    sender = Sender(session, player, queue=queue, destinations=places, garage=lambda: True)
    requests = type('Requests', (object,), {'busy': lambda self: False})()
    feedback = Feedback(session, garage, reports, sender, requests)
    garage.install(sender)
    return session, queue, player, place, garage, reports, sender, feedback


def check_battle_feedback():
    session, queue, player, place, garage, reports, sender, feedback = fixture()
    battle = results(common={'bonusType': 160}, vehicle={'damageDealt': 28806})
    check('the Other battle is captured', reports.capture(battle, constants=Bonus))
    check('capture only schedules work; no HTTP runs inside the result hook', not session.sent)
    pending = garage.display_data()['battle_feedback']
    check('28806 damage is immediately available as provisional local data',
          pending['totals']['damage_dealt'] == 28806 and pending['source'] == 'local')
    check('local measurements never overwrite or add to official totals', garage.data['players'][0]['official']['totals']['damage_dealt'] == 0)
    # A read started before delivery must not confirm this battle even if it
    # finishes after the site's POST answer.
    garage.poll(force=True)
    stale = session.sent.pop()['answer']
    session.flush()
    check('the captured battle sends on the next frame without a five-second tick', len(session.sent) == 1 and session.sent[0]['method'] == 'POST')
    check('the provisional card follows the active sending state', feedback.snapshot()['stage'] == 'sending')
    post = session.sent.pop()
    post['answer'](_Response(200, {'accepted': 1, 'duplicates': 0, 'rejected': 0, 'results': [{'index': 0, 'status': 'accepted'}]}))
    check('HTTP acceptance alone does not replace local values with a guessed score', feedback.snapshot()['stage'] == 'confirming' and feedback.receipt is None)
    stale(_Response(200, copy.deepcopy(garage.data)))
    session.flush()
    check('delivery behind an in-flight read schedules a fresh snapshot immediately', len(session.sent) == 1 and 'receipt_arena=' in session.sent[0]['url'])
    confirmed = copy.deepcopy(garage.data)
    confirmed['receipt'] = {'arena_unique_id': str(battle['arenaUniqueID']), 'status': 'accepted', 'mode': 'other', 'totals': {'damage_dealt': 28000}}
    confirmed['players'][0]['official']['totals']['damage_dealt'] = 27000
    session.sent.pop()['answer'](_Response(200, confirmed))
    shown = garage.display_data()['battle_feedback']
    check('the site receipt replaces local numbers even when they differ', shown['source'] == 'site' and shown['totals']['damage_dealt'] == 28000 and shown['stage'] == 'received')
    check('the official score is exactly the server score, never a sum with local damage', garage.data['players'][0]['official']['totals']['damage_dealt'] == 27000)
    check('settled queue ownership is unchanged by the display', not queue.all())
    feedback.captured({'account': ACCOUNT, 'arena_unique_id': '1', 'finished_at': '2000-01-01T00:00:00Z', 'mode': 'other', 'metrics': {}})
    check('opening an older result cannot replace the last battle card', feedback.arena() == str(battle['arenaUniqueID']))
    feedback.accept(dict(confirmed, receipt={'arena_unique_id': feedback.arena(), 'status': 'accepted', 'mode': 'other', 'totals': []}))
    check('malformed receipt cannot erase the last valid server values', feedback.snapshot()['totals']['damage_dealt'] == 28000)
    place.secret = 'b' * 64
    check('relinking clears all provisional and confirmed battle data', feedback.snapshot() is None)
    player.account = '500999999'
    feedback.captured(dict(queue.all()[0] if queue.all() else {}, account=ACCOUNT))
    check('another account cannot populate the current battle card', feedback.snapshot() is None)

    session, queue, player, place, garage, reports, sender, feedback = fixture()
    reports.capture(battle, constants=Bonus)
    session.flush()
    session.sent.pop()['answer'](_Response(503))
    session.flush()
    check('network refusal retains the visible local result and the durable queue', feedback.snapshot()['stage'] == 'waiting' and feedback.snapshot()['totals']['damage_dealt'] == 28806 and len(queue.all()) == 1)
    sender.drain()
    check('immediate delivery never bypasses network backoff', not session.sent)
    sender._waiting.clear()
    sender.drain()
    session.sent.pop()['answer'](_Response(200, {'rejected': 1, 'results': [{'index': 0, 'status': 'rejected'}]}))
    session.flush()
    check('a final rejection is displayed without granting success or retrying', feedback.snapshot()['stage'] == 'rejected' and not queue.all())
    if session.sent:
        session.sent.pop()['answer'](_Response(503))
    player.account = '500999999'
    session.flush()
    check('late callbacks cannot restore a previous account battle', feedback.snapshot() is None)

    session, queue, player, place, garage, reports, sender, feedback = fixture()
    in_garage = [False]
    garage.garage = lambda: in_garage[0]
    feedback.snapshot()
    in_garage[0] = True
    check('return from battle shows retrieval instead of pretending the last result was zero', feedback.snapshot() == {'stage': 'retrieving'})

    from battle_conquest.results_request import Requests, _TICK_SECONDS
    from checks.results_request import _Cache
    cache = _Cache({91: (-3, None)})
    session = Timers()
    taken = []
    requests = Requests(session, lambda result, source: taken.append(result), garage=lambda: True, cache=lambda: cache)
    requests.remember(91)
    requests._became_player()
    cache._answers[91] = (1, battle)
    session.flush()
    check('cache readiness after the account event gets its next-frame retry rather than a full discovery tick', cache.asked == [91, 91] and taken == [battle])
    check('late-result discovery has a five-second fallback', _TICK_SECONDS == 5.0)
