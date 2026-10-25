"""Measured quest cards; display alone never changes scores or participation."""
import json
import math

from battle_conquest.quest_garage_text import clean, metric_value
from battle_conquest.quest_garage_widgets import label, place, surface, wrapped

NAMES = {'damage': 'Damage', 'kills': 'Kills', 'xp': 'XP', 'xp_base': 'Base XP',
         'xp_total': 'Total XP', 'credits_net': 'Net credits', 'credits_gross': 'Gross credits'}


def number(value):
    return u'{:,}'.format(value).replace(',', ' ') if isinstance(value, (int, long, float)) else unicode(value)


def progress_ratio(value, target):
    try:
        current, goal = float(value), float(target)
    except (TypeError, ValueError, OverflowError):
        return None
    if goal <= 0 or any(math.isnan(v) or math.isinf(v) for v in (current, goal)):
        return None
    return max(0.0, min(1.0, current / goal))


class Card(object):
    def __init__(self, parent, name, width, y, accent=None):
        self.node = surface(parent, name, 'card')
        self.node.width = width
        place(self.node, 0, y)
        self.width, self.y, self.index = width, 12, 0
        if accent:
            self.edge = surface(self.node, 'edge', accent)
            self.edge.width = 3
        else:
            self.edge = None

    def text(self, value, color='text'):
        node = label(self.node, 'text%s' % self.index, color=color)
        self.index += 1
        width, height = wrapped(node, [value], self.width - 32)
        place(node, 16, self.y)
        self.y += height + 6
        return node

    def progress(self, value, target, color):
        ratio = progress_ratio(value, target)
        if ratio is None:
            return
        track = surface(self.node, 'track%s' % self.index, 'track')
        track.width, track.height = self.width - 32, 4
        place(track, 16, self.y)
        if ratio:
            fill = surface(track, 'fill', color)
            fill.width, fill.height = track.width * ratio, 4
        self.index += 1
        self.y += 14

    def source(self, title, score, criteria, color):
        if score is None:
            return
        self.y += 6
        count = score.get('battles')
        self.text(u'%s  |  %s battles' % (title, count) if count is not None else title, color)
        if not score.get('available'):
            self.text(u'No data for this period.', 'muted')
        elif score.get('comparable') is False:
            self.text(u'Not comparable with this quest.', 'muted')
        else:
            for criterion in criteria:
                metric, target = criterion['criterion_type'], criterion['target_value']
                name = NAMES.get(metric, metric.replace('_', ' ').capitalize())
                self.text(u'%s:  %s / %s' % (name, number(metric_value(score, metric)), number(target)))
                self.progress(score.get('totals', {}).get(metric), target, color)
            if not criteria:
                self.text(u'No objectives to display.', 'muted')
        if score.get('incomplete'):
            self.text(u'Incomplete data - unknown values stay marked ?.', 'muted')

    def finish(self):
        self.node.height = self.y + 6
        if self.edge is not None:
            self.edge.height = self.node.height
        return self.node.height + 12


class Content(object):
    def __init__(self, parent):
        self.parent = parent
        self.node = None
        self.key = None
        self.height = 0

    def clear(self):
        if self.node is not None:
            self.parent.delChild('snapshot')
        self.node = self.key = None
        self.height = 0

    def show(self, visible):
        if self.node is not None:
            self.node.visible = visible

    def render(self, data, width):
        key = (json.dumps(data, sort_keys=True), width)
        if key == self.key:
            return False
        self.clear()
        self.node = surface(self.parent, 'snapshot')
        self.node.width = width
        y = 0
        card = Card(self.node, 'quest', width, y, 'accent')
        card.text(u'TRACKED QUEST', 'muted')
        selected = data.get('selected') if data else None
        card.text(clean(selected['title']) if selected else u'No quest selected', 'accent')
        if not selected:
            card.text(u'Click Change quest, or choose one on the website.', 'muted')
        period = data.get('period') if data else None
        if period:
            card.text(u'Period (UTC): %s / %s' % (period['start'], period['end']), 'muted')
        y += card.finish()
        if data:
            for index, player in enumerate(data.get('players', [])[:5]):
                card = Card(self.node, 'player%s' % index, width, y)
                card.text(clean(player['username'], 30))
                card.text(u'Participant' if player['participant'] else u'Followed only - no rewards', 'muted')
                card.source(u'OFFICIAL', player.get('official'), data.get('criteria', []), 'official')
                card.source(u'MOD ESTIMATE - indicative', player.get('estimate'), data.get('criteria', []), 'estimate')
                if player.get('official') is None and player.get('estimate') is None:
                    card.text(u'No results for this period.', 'muted')
                y += card.finish()
            choices = [choice for choice in data.get('choices', []) if choice.get('joined', True)]
            if choices:
                card = Card(self.node, 'choices', width, y)
                card.text(u'AVAILABLE QUESTS / JOINED SESSIONS', 'muted')
                for choice in choices[:5]:
                    card.text(u'%s  (%s)' % (clean(choice['title']), clean(choice['status'])))
                if len(choices) > 5:
                    card.text(u'+%s more on the website' % (len(choices) - 5), 'muted')
                y += card.finish()
        self.height = max(0, y - 12)
        self.node.height = self.height
        self.key = key
        return True
