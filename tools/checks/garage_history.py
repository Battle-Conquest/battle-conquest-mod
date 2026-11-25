"""Both garage displays honor the same server expiry, including offline."""
import copy

from checks.common import check
from checks.report_sender import _Response, _Session


def check_garage_history():
    from battle_conquest.destinations import Destination, battles_url
    from battle_conquest.garage_display import Displays
    from battle_conquest.quest_garage import Garage

    class View(object):
        def reset(self):
            pass
        def visible(self, shown, preserve_draft=False):
            pass
        def render(self, garage):
            pass

    session = _Session()
    account = type('Account', (object,), {'account': '123'})()
    places = type('Places', (object,), {'linked': True,
        'current': Destination(battles_url(), enabled=True, secret='a' * 64)})()
    clock = [100.0]
    garage = Garage(session, account, places, View(), garage=lambda: True, ready=lambda: True,
                    platoon=lambda: [], now=lambda: clock[0])
    ended = {'key': 'event:1', 'title': 'A completed event', 'kind': 'event', 'status': 'settled',
             'expires_at': '2026-11-24 12:00:03'}
    active = {'key': 'individual:2', 'title': 'An active quest', 'status': 'active'}
    recent = {'key': 'session:3', 'title': 'A challenge', 'status': 'receiving',
              'expires_at': '2026-11-24 12:00:05'}
    data = {'schema': 1, 'server_time': '2026-11-24 12:00:00',
            'config': {'version': 1, 'selection': ended['key'], 'mode': 'platoon', 'manual_ids': []},
            'choices': [ended, active, recent], 'selected': ended, 'players': [{'username': 'Self', 'participant': True}],
            'tracking': {'kind': 'event', 'state': 'settled', 'score': 42}, 'criteria': [],
            'period': {'start': '2026-11-23 11:00:00', 'end': '2026-11-24 11:00:03'}}
    card = Displays(session, account, places, type('Site', (object,), {'running': False})(), View())
    card.garage = garage

    garage.tick()
    poll = session.sent.pop()
    check('garage requests recent history explicitly', '&history=recent' in poll['url'])
    poll['answer'](_Response(200, data))
    clock[0] = 102.99
    garage.tick()
    check('both displays retain a closed event up to its deadline',
          card.snapshot(True)['selected']['key'] == ended['key'] and garage.display_data()['tracking']['score'] == 42)
    garage.poll(force=True)
    session.sent.pop()['answer'](_Response(503))
    garage.poll(force=True)
    late = session.sent.pop()
    clock[0] = 103.0
    garage.tick()
    widget, native = card.snapshot(True), garage.display_data()
    check('both displays immediately remove an expired offline selection and its score',
          widget['selected'] is None and not widget['tracking'] and native['selected'] is None
          and native['tracking'] is None and not native['players'] and native['period'] is None
          and set(row['key'] for row in widget['choices']) == {active['key'], recent['key']})
    check('expiration itself never writes selection', garage.offline and native['selection_hidden']
          and native['config']['selection'] == ended['key'] and not session.sent)
    clock[0] = 104.0
    late['answer'](_Response(200, dict(data, server_time='2026-11-24 12:00:02')))
    check('a delayed successful response cannot revive a locally expired choice',
          garage.data['selected'] is None and garage.data['selection_hidden'] and garage.data['choices'] == [active, recent])
    check('an expired selection cannot be written by a delayed click', not garage.save(selection=ended['key']) and not session.sent)
    clock[0] = 105.0
    garage.tick()
    check('a delayed response does not defer the second deadline', garage.data['choices'] == [active])

    garage.poll(force=True)
    after_expiry = session.sent.pop()
    clock[0] = 106.0
    after_expiry['answer'](_Response(200, dict(data, choices=[active, recent], selected=recent,
                                            tracking=None, server_time='2026-11-24 12:00:04')))
    check('the clock still filters delayed replies after the last deadline has passed',
          garage.data['choices'] == [active] and garage.data['selected'] is None)

    garage.poll(force=True)
    fallback = dict(data, choices=[active], selected=active, tracking=None, players=[], period=None,
                    selection_hidden=True, server_time='2026-11-24 12:00:06')
    session.sent.pop()['answer'](_Response(200, fallback))
    check('both displays show the server fallback on reconnect',
          not garage.offline and card.snapshot(True)['selected'] == active and garage.display_data()['selected'] == active)
    garage.save(mode='manual')
    save = session.sent.pop()
    check('unrelated saves keep the shared choice', save['body']['selection'] == ended['key'])
    saved = copy.deepcopy(fallback)
    saved['config'].update(version=2, mode='manual')
    save['answer'](_Response(200, saved))
    garage.next_quest()
    check('native selection can explicitly replace the hidden choice', session.sent.pop()['body']['selection'] == '')

    account.account = '456'
    garage.tick()
    check('a new account clears the history and its clock', garage.history_clock is None and garage.data is None)
    legacy = dict(data, choices=[active], selected=active, tracking=None)
    del legacy['server_time']
    session.sent.pop()['answer'](_Response(200, legacy))
    check('snapshots from servers without the history contract are accepted', garage.data == legacy)
