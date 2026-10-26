"""Measured quest cards; display alone never changes scores or participation."""
import json
import math

from battle_conquest.quest_garage_text import clean, metric_value
from battle_conquest.i18n import locale, tr
from battle_conquest.quest_garage_widgets import label, place, surface, wrapped

NAMES = {'damage': 'Damage', 'damage_dealt': 'Damage dealt', 'kills': 'Kills',
         'xp': 'Experience', 'wins': 'Wins', 'frags': 'Tanks destroyed', 'spotted': 'Tanks spotted',
         'battles': 'Battles', 'shots': 'Shots', 'hits': 'Hits', 'piercings': 'Penetrations',
         'explosion_hits': 'Explosion hits', 'xp_base': 'Base XP', 'xp_total': 'Total XP',
         'credits_net': 'Net credits', 'credits_gross': 'Gross credits'}


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
        self.width, self.y, self.index = width, 8, 0
        self.x, self.text_width = 12, width - 24
        if accent:
            self.edge = surface(self.node, 'edge', accent)
            self.edge.width = 3
        else:
            self.edge = None

    def text(self, value, color='text', translate=True):
        node = label(self.node, 'text%s' % self.index, color=color)
        self.index += 1
        width, height = wrapped(node, [tr(value) if translate else value], self.text_width)
        place(node, self.x, self.y)
        self.y += height + 2
        return node

    def progress(self, value, target, color):
        ratio = progress_ratio(value, target)
        if ratio is None:
            return
        track = surface(self.node, 'track%s' % self.index, 'track')
        track.width, track.height = self.text_width, 3
        place(track, self.x, self.y)
        if ratio:
            fill = surface(track, 'fill', color)
            fill.width, fill.height = track.width * ratio, 3
        self.index += 1
        self.y += 7

    def source(self, title, score, criteria, color, localized=True):
        if score is None:
            return
        self.text(title, color)
        if not score.get('available'):
            self.text(u'No data for this period.', 'muted')
        elif score.get('comparable') is False:
            self.text(u'Not comparable with this quest.', 'muted')
        else:
            for criterion in criteria:
                metric, target = criterion['criterion_type'], criterion['target_value']
                name = (criterion.get('label') if localized else None) or tr(NAMES.get(metric, metric.replace('_', ' ').capitalize()))
                self.text(u'%s:  %s / %s' % (name, number(metric_value(score, metric)), number(target)))
                self.progress(score.get('totals', {}).get(metric), target, color)
            if not criteria:
                self.text(u'No objectives to display.', 'muted')
        if score.get('battles') is not None:
            self.text(tr(u'%s battles') % score['battles'], 'muted', translate=False)
        if score.get('incomplete'):
            self.text(u'Incomplete data (?)', 'muted')

    def finish(self):
        self.node.height = self.y + 6
        if self.edge is not None:
            self.edge.height = self.node.height
        return self.node.height + 8


STAGES = {'retrieving': u'Waiting for the WoT result...', 'queued': u'Waiting to send...',
          'sending': u'Sending to Battle-Conquest...', 'waiting': u'Delivery pending - result retained',
          'confirming': u'Awaiting Battle-Conquest confirmation...', 'rejected': u'Battle rejected by Battle-Conquest',
          'received': u'Received by Battle-Conquest - official progress below'}


def battle_card(parent, width, y, data):
    feedback = data.get('battle_feedback')
    if not feedback:
        return 0
    card = Card(parent, 'last_battle', width, y, 'estimate')
    card.text(u'LAST BATTLE - Battle-Conquest' if feedback.get('source') == 'site' else u'LAST BATTLE - provisional', 'accent')
    card.text(STAGES.get(feedback.get('stage'), STAGES['confirming']), 'muted')
    if 'mode' in feedback:
        card.text(tr(feedback['mode']), 'muted', translate=False)
    metrics = [c['criterion_type'] for c in data.get('criteria', [])] or ['damage_dealt', 'frags']
    for metric in dict.fromkeys(metrics):
        if 'totals' in feedback:
            card.text(u'%s: %s' % (tr(NAMES.get(metric, metric)), number(feedback['totals'].get(metric, u'?'))), translate=False)
    if feedback.get('source') != 'site' and 'totals' in feedback:
        card.text(u'Eligibility and rewards are confirmed by the site.', 'muted')
    return card.finish()


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
        shown = dict((name, (data or {}).get(name)) for name in ('selected', 'criteria', 'players', 'language', 'battle_feedback'))
        key = (json.dumps(shown, sort_keys=True), width, locale())
        if key == self.key:
            return False
        self.clear()
        self.node = surface(self.parent, 'snapshot')
        self.node.width = width
        y = 0
        card = Card(self.node, 'quest', width, y, 'accent')
        selected = data.get('selected') if data else None
        card.text(clean(selected['title']) if selected else tr(u'No quest selected'), 'accent', translate=False)
        if selected and selected.get('status'):
            status = selected['status']
            status = {'receiving': u'Closed - receiving final results', 'settled': u'Closed - final results', 'cancelled': u'Cancelled'}.get(status, status)
            card.text(status, 'muted')
        if not selected:
            card.text(u'Click Change quest, or choose one on the website.', 'muted')
        y += card.finish()
        y += battle_card(self.node, width, y, data or {})
        if data:
            for index, player in enumerate(data.get('players', [])[:5]):
                card = Card(self.node, 'player%s' % index, width, y)
                card.text(clean(player['username'], 30), translate=False)
                if not player['participant']:
                    card.text(u'Followed only - no rewards', 'muted')
                localized = data.get('language', 'en') == locale()
                sources = [(title, player.get(source_key), color) for title, source_key, color in
                           ((u'OFFICIAL', 'official', 'official'), (u'MOD ESTIMATE', 'estimate', 'estimate'))
                           if player.get(source_key) is not None]
                top, bottoms = card.y, [card.y]
                column = (width - 36) / 2 if len(sources) == 2 else width - 24
                for source_index, (title, score, color) in enumerate(sources):
                    card.x, card.text_width, card.y = 12 + source_index * (column + 12), column, top
                    card.source(title, score, data.get('criteria', []), color, localized)
                    bottoms.append(card.y)
                card.x, card.text_width, card.y = 12, width - 24, max(bottoms)
                if player.get('official') is None and player.get('estimate') is None:
                    card.text(u'No results for this period.', 'muted')
                y += card.finish()
        self.height = max(0, y - 8)
        self.node.height = self.height
        self.key = key
        return True
