"""Tournament summaries are official server data, never local quest estimates."""
from battle_conquest.i18n import tr

CATEGORIES = (('individual', u'Quests'), ('session', u'Challenges'), ('bffa', u'Battle FFA'),
              ('event', u'Tournaments'), ('tile', u'Map'))
STATES = {'waiting': u'Waiting', 'active': u'In progress', 'qualification': u'Qualification',
          'match': u'Match', 'receiving': u'Awaiting final results', 'eliminated': u'Eliminated',
          'advanced': u'Qualified for the next round', 'bye': u'Bye', 'settled': u'Closed - final results'}
FIELDS = (('score', u'Score'), ('rank', u'Rank'), ('battles', u'Battles'),
          ('battle_min', u'Minimum battles'), ('battle_cap', u'Battle cap'),
          ('round', u'Round'), ('opponent', u'Opponent'), ('opponent_score', u'Opponent score'))


def category(choice):
    return choice.get('category') or choice.get('kind') or choice.get('key', '').split(':')[0]


def choice_status(choice):
    state = choice.get('status', '')
    title = {'upcoming': u'Waiting', 'scheduled': u'Scheduled', 'registration': u'Registration open',
             'qualification': u'Qualification', 'bracket': u'Matches', 'closing': u'Awaiting final results',
             'settled': u'Closed - final results'}.get(state, state)
    return tr(title)


def ordered(choices):
    """Keep older servers usable, while matching the visual category order."""
    order = dict((key, index) for index, (key, title) in enumerate(CATEGORIES))
    return sorted(choices, key=lambda row: order.get(category(row), len(order)))


def lines(tracking):
    if not tracking:
        return []
    result = [tr(u'OFFICIAL'), tr(STATES.get(tracking.get('state'), u'Unavailable'))]
    for key, title in FIELDS:
        if key not in tracking:
            continue
        value = tracking[key]
        if key in ('battle_min', 'battle_cap') and value is None:
            continue
        if key == 'battle_cap' and value == 0:
            value = tr(u'Unlimited')
        result.append(u'%s: %s' % (tr(title), unicode(value) if value is not None else tr(u'Unavailable')))
    if tracking.get('third_place'):
        result.append(tr(u'Third-place match'))
    if tracking.get('role'):
        result.append(tr(u'Attacker' if tracking['role'] == 'attacker' else u'Defender'))
    if tracking.get('tile'):
        result.append(tr(u'Tile: %s, %s') % (tracking['tile']['col'], tracking['tile']['row']))
    if tracking.get('sabotage_malus') is not None:
        result.append(tr(u'Sabotage: %s%%') % tracking['sabotage_malus'])
    return result


def valid(data):
    if data is None:
        return True
    if not isinstance(data, dict) or data.get('kind') not in ('bffa', 'event', 'tile') or not isinstance(data.get('state'), basestring) or data['state'] not in STATES:
        return False
    for key in ('score', 'rank', 'battles', 'battle_min', 'battle_cap', 'round', 'opponent_score', 'sabotage_malus'):
        value = data.get(key)
        if value is not None and (not isinstance(value, (int, long)) or isinstance(value, bool)):
            return False
    for key in ('updated_at', 'opponent'):
        if data.get(key) is not None and not isinstance(data[key], basestring):
            return False
    if data.get('role') is not None and data['role'] not in ('attacker', 'defender'):
        return False
    if 'third_place' in data and not isinstance(data['third_place'], bool):
        return False
    tile = data.get('tile')
    if tile is not None and (not isinstance(tile, dict) or not all(isinstance(tile.get(key), (int, long))
                            and not isinstance(tile[key], bool) for key in ('col', 'row'))):
        return False
    return True
