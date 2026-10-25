"""Account snapshot text; official and indicative figures remain distinct."""
import calendar
import time
from battle_conquest.i18n import tr


def status_line(garage):
    timestamps = []
    for player in (garage.data or {}).get('players', [])[:5]:
        for source in ('official', 'estimate'):
            stamp = (player.get(source) or {}).get('updated_at')
            if stamp:
                try:
                    timestamps.append(calendar.timegm(time.strptime(stamp, '%Y-%m-%d %H:%M:%S')))
                except ValueError:
                    pass
    age = max(0, int(garage.now() - min(timestamps))) if timestamps else None
    return tr(u'%s | Data age: %s') % (tr(u'Offline' if garage.offline else u'Online'),
                                     u'%ss' % age if age is not None else tr(u'unknown'))


def clean(value, limit=64):
    return u' '.join(unicode(value).split())[:limit]


def metric_value(score, metric):
    value = score['totals'].get(metric)
    if value is not None:
        return value
    known = score.get('known_totals', {}).get(metric)
    return u'%s + ?' % known if known else u'?'


def lines(garage):
    data = garage.data
    if data is None:
        return [u'Waiting for quest data...' if not garage.offline else u'Offline - no data yet.']
    result = [u'Active quests / joined sessions:']
    active = [choice for choice in data.get('choices', []) if choice.get('joined', True)]
    for choice in active[:5]:
        result.append(u'  %s (%s)' % (clean(choice['title']), clean(choice['status'])))
    if len(active) > 5:
        result.append(u'  +%s more (see website)' % (len(active) - 5))
    selected = data.get('selected')
    result.append(u'Selected: %s' % (clean(selected['title']) if selected else u'none'))
    period = data.get('period')
    if period:
        result.append(u'UTC: %s / %s' % (period['start'], period['end']))
    for player in data.get('players', [])[:5]:
        result.append(u'%s%s' % (clean(player['username'], 30), u'' if player['participant'] else u' - indicative, no rewards'))
        if player.get('official') is None and player.get('estimate') is None:
            result.append(u'  no data')
        for source in ('official', 'estimate'):
            score = player.get(source)
            if score is None:
                continue
            label = u'Official' if source == 'official' else u'Mod estimate'
            if not score.get('available'):
                detail = u'no data'
            elif score.get('comparable') is False:
                detail = u'not comparable'
            else:
                detail = u', '.join(u'%s %s/%s' % (criterion['criterion_type'].replace('_', ' '),
                                                  metric_value(score, criterion['criterion_type']), criterion['target_value'])
                                    for criterion in data.get('criteria', []))
                detail += u' (%s battles)' % score['battles']
            if score.get('incomplete'):
                detail += u' - incomplete'
            result.append(u'  %s: %s' % (label, detail))
    result.append(status_line(garage))
    if garage.error:
        result.append(garage.error)
    return result

