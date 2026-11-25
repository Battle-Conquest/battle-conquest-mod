"""Account snapshot text; official and indicative figures remain distinct."""
import calendar
import time
from battle_conquest.i18n import tr


def duration(seconds):
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    minutes, seconds = divmod(remainder, 60)
    return u'%02d:%02d:%02d' % (hours, minutes, seconds)


def status_line(garage):
    data = garage.data or {}
    criteria = data.get('criteria', [])
    timestamps = []
    for player in data.get('players', [])[:5]:
        for source in ('official', 'estimate'):
            if source == 'estimate' and criteria and not any(show_estimate(player, c['criterion_type']) for c in criteria):
                continue
            stamp = (player.get(source) or {}).get('updated_at')
            if stamp:
                try:
                    timestamps.append(calendar.timegm(time.strptime(stamp, '%Y-%m-%d %H:%M:%S')))
                except ValueError:
                    pass
    stamp = (data.get('tracking') or {}).get('updated_at')
    if stamp:
        try:
            timestamps.append(calendar.timegm(time.strptime(stamp, '%Y-%m-%d %H:%M:%S')))
        except ValueError:
            pass
    age = max(0, int(garage.now() - min(timestamps))) if timestamps else None
    return tr(u'%s | Data age: %s') % (tr(u'Offline' if garage.offline else u'Online'),
                                     duration(age) if age is not None else tr(u'unknown'))


def clean(value, limit=64):
    return u' '.join(unicode(value).split())[:limit]


def metric_value(score, metric):
    value = score['totals'].get(metric)
    if value is not None:
        return value
    known = score.get('known_totals', {}).get(metric)
    return u'%s + ?' % known if known else u'?'


def score_number(value):
    return isinstance(value, (int, long)) and not isinstance(value, bool)


def pending_values(data, tracking=False):
    pending = data.get('pending_progress')
    if not isinstance(pending, dict):
        return {}
    values = pending if tracking else pending.get('criteria')
    if not isinstance(values, dict):
        return {}
    return dict((key, value) for key, value in values.items()
                if isinstance(key, basestring) and (value is None or score_number(value)))


def full_metric(score, metric):
    return (score and score.get('available') and score.get('comparable') is not False
            and score_number(score.get('totals', {}).get(metric)))


def show_estimate(player, metric):
    return not player.get('participant') or not full_metric(player.get('official'), metric)


def progress_text(value, pending, key, format_number=unicode):
    text = format_number(value) if value is not None else tr(u'Unavailable')
    if key not in pending or pending[key] == 0:
        return text
    delta = pending[key]
    if delta is None or not score_number(value):
        if value in (None, u'?'):
            text = tr(u'Unavailable')
        return u'%s \u00b7 %s' % (text, tr(u'Calculation pending'))
    # The bundled native font covers ASCII signs.
    sign = u'+' if delta > 0 else u'-'
    return u'%s (%s%s)' % (text, sign, format_number(abs(delta)))


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
            label = u'Battle-Conquest' if source == 'official' else u'Mod estimate'
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

