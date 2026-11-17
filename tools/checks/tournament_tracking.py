"""Server tournament data stays distinct from targets and follows account lifetime."""
import copy

from checks.common import check
from checks.quest_garage import _Response, _Session


def check_tournament_tracking():
    from battle_conquest import i18n, tournament_tracking as tracking
    from battle_conquest.destinations import Destination, battles_url
    from battle_conquest.quest_garage import Garage, is_snapshot
    from battle_conquest.quest_garage_text import status_line

    class View(object):
        def reset(self):
            pass
        def visible(self, shown, preserve_draft=False):
            pass
        def render(self, garage):
            pass

    session = _Session()
    account = type('Account', (object,), {'account': '123'})()
    places = type('Places', (object,), {'current': Destination(battles_url(), enabled=True, secret='a' * 64)})()
    garage = Garage(session, account, places, View(), garage=lambda: True, ready=lambda: True, platoon=lambda: [], now=lambda: 100.0)
    choices = [{'key': kind + ':1', 'title': kind, 'kind': kind, 'status': 'active'}
               for kind in ('tile', 'event', 'session', 'individual', 'bffa')]
    snapshot = {'schema': 1, 'config': {'version': 2, 'selection': 'event:1', 'mode': 'manual', 'manual_ids': [2]},
                'choices': choices, 'selected': choices[1], 'players': [], 'criteria': [],
                'tracking': {'kind': 'event', 'state': 'match', 'score': 0, 'rank': None,
                             'opponent': '<rival>', 'opponent_score': 100, 'updated_at': '1970-01-01 00:01:00'}}
    check('tournament summaries extend schema 1', is_snapshot(snapshot))
    legacy = dict(snapshot)
    del legacy['tracking']
    check('old garage servers remain compatible', is_snapshot(legacy))
    for key, value in [('score', '0'), ('rank', True), ('state', []), ('tile', {'col': [], 'row': 1}), ('updated_at', [])]:
        damaged = copy.deepcopy(snapshot)
        damaged['tracking'][key] = value
        check('malformed tournament %s is rejected' % key, not is_snapshot(damaged))
    scope, language, identity = i18n._scope, i18n._language, i18n._identity
    try:
        i18n._identity, i18n._scope = None, None
        for locale in ('en', 'fr'):
            i18n._language = locale
            rendered = tracking.lines(snapshot['tracking'])
            check('zero cap means unlimited in ' + locale,
                  any(row.endswith(i18n.tr(u'Unlimited')) for row in tracking.lines(dict(snapshot['tracking'], battle_cap=0))))
            check('zero score remains a real result in ' + locale, u'Score: 0' in rendered)
            check('unknown rank stays unavailable in ' + locale,
                  any(row.startswith(i18n.tr(u'Rank') + ': ') and row.endswith(i18n.tr(u'Unavailable')) for row in rendered))
            check('opponent text is not interpreted as markup', any('<rival>' in row for row in rendered))
        garage.data = snapshot
        garage.key = garage.identity()
        check('tournament snapshot contributes its real data age', status_line(garage).endswith('00:00:40'))
        check('category order is stable', [row['kind'] for row in tracking.ordered(choices)] == ['individual', 'session', 'bffa', 'event', 'tile'])
        garage.next_quest()
        sent = session.sent.pop(0)
        check('native next objective reaches the map category and keeps manual players',
              sent['body']['selection'] == 'tile:1' and sent['body']['manual_ids'] == [2])
        account.account = '456'
        garage.tick()
        sent['answer'](_Response(200, snapshot))
        check('a late tournament save cannot cross an account change', garage.data is None)
    finally:
        i18n._scope, i18n._language, i18n._identity = scope, language, identity
