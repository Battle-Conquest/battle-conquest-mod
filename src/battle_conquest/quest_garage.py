"""Account-bound garage snapshots and optimistic configuration writes."""
import json
import time
from urllib import quote

from battle_conquest import config, i18n
from battle_conquest.destinations import battles_url
from battle_conquest.garage_ready import garage_ready
from battle_conquest.report_sender import at_garage, account_number, answer


def platoon_accounts():
    """Only the current small squad, never the complete friends/unit roster."""
    try:
        from gui.prb_control.dispatcher import g_prbLoader
        entity = g_prbLoader.getDispatcher().getEntity()
        from constants import PREBATTLE_TYPE
        squad_types = [getattr(PREBATTLE_TYPE, name, None) for name in
                       ('SQUAD', 'EVENT_SQUAD', 'COMP7_SQUAD', 'EPIC_SQUAD', 'RANKED_SQUAD', 'MAPBOX_SQUAD')]
        if entity.getEntityType() not in [value for value in squad_types if value is not None]:
            return []
        return [str(db_id) for db_id in entity.getPlayers() if db_id][:5]
    except Exception:
        return []


def is_snapshot(data):
    if not isinstance(data, dict) or data.get('schema') != 1:
        return False
    settings = data.get('config')
    if (not isinstance(settings, dict) or not isinstance(settings.get('version'), (int, long))
            or isinstance(settings['version'], bool) or settings['version'] < 0
            or settings.get('mode') not in ('platoon', 'manual')
            or not isinstance(settings.get('selection'), basestring)
            or not isinstance(settings.get('manual_ids'), list)):
        return False
    choices, players = data.get('choices'), data.get('players')
    manual = data.get('manual_players', [])
    if (not isinstance(manual, list) or len(manual) > 4
            or not all(isinstance(row, dict) and isinstance(row.get('id'), (int, long))
                       and not isinstance(row['id'], bool) and row['id'] > 0
                       and isinstance(row.get('username'), basestring) for row in manual)):
        return False
    if (not isinstance(choices, list) or not isinstance(players, list) or len(players) > 5
            or not all(isinstance(choice, dict) and all(key in choice for key in ('key', 'title', 'status')) for choice in choices)
            or not all(isinstance(player, dict) and all(key in player for key in ('username', 'participant')) for player in players)):
        return False
    selected, period = data.get('selected'), data.get('period')
    if selected is not None and (not isinstance(selected, dict) or 'title' not in selected):
        return False
    if period is not None and (not isinstance(period, dict) or not all(key in period for key in ('start', 'end'))):
        return False
    criteria = data.get('criteria', [])
    if not isinstance(criteria, list) or not all(isinstance(c, dict) and isinstance(c.get('criterion_type'), basestring) and 'target_value' in c for c in criteria):
        return False
    for player in players:
        for source in ('official', 'estimate'):
            score = player.get(source)
            if score is None:
                continue
            if (not isinstance(score, dict) or not isinstance(score.get('known_totals', {}), dict)
                    or (score.get('updated_at') is not None and not isinstance(score['updated_at'], basestring))):
                return False
            if score.get('available') and score.get('comparable') is not False:
                if not isinstance(score.get('totals'), dict) or not isinstance(score.get('battles'), (int, long)):
                    return False
    return True


class Garage(object):

    def __init__(self, session, account, places, view, garage=at_garage,
                 platoon=platoon_accounts, now=time.time, ready=garage_ready):
        self.session = session
        self.account = account
        self.places = places
        self.view = view
        self.garage = garage
        self.ready = ready
        self.platoon = platoon
        self.now = now
        self.key = None
        self.data = None
        self.offline = False
        self.unavailable = False
        self.conflict = False
        self.error = None
        self.busy = None
        self.last_poll = 0
        self.last_received = None
        self.last_sent = None
        self.search_ticket = None

    def identity(self):
        current = self.places.current
        account = getattr(self.account, 'account', None)
        if (account_number(account) is None or current is None or not current.enabled
                or not current.secret or current.url != battles_url()):
            return None
        return (account, current.url, current.secret)

    def install(self, sender):
        self.session.repeat(1.0, self.tick)
        self.account.on_change(self.tick)
        self.session.on_close(self.view.close)
        if sender is not None:
            def sent():
                if sender.last_sent != self.last_sent:
                    self.last_sent = sender.last_sent
                    self.last_poll = 0
                    self.poll(force=True)
            sender.on_change(sent)
        self.tick()

    def tick(self):
        key = self.identity()
        if key != self.key:
            self.search_ticket = None
            self.key = key
            self.data = None
            self.busy = None
            self.conflict = False
            self.offline = False
            self.unavailable = False
            self.error = None
            self.last_received = None
            self.last_poll = 0
            self.view.reset()
        visible = self.garage() and key is not None
        self.view.visible(visible and self.ready() and not self.unavailable and (self.data is not None or self.offline))
        if visible:
            self.poll()
            self.view.render(self)

    def url(self):
        return (config.SITE.rstrip('/') + '/api/mod/quest-garage?account_id=%s&region=%s'
                % (account_number(self.key[0]), config.REGION))

    def poll(self, force=False):
        key = self.identity()
        if key is None or key != self.key or not self.garage() or self.busy is not None:
            return
        if not force and self.now() - self.last_poll < 15.0:
            return
        members = [str(value) for value in self.platoon()
                   if str(value).isdigit() and str(value) != str(key[0])][:4]
        url = self.url() + ('&platoon=' + ','.join(members) if members else '')
        self.request(url, key)

    def request(self, url, key, payload=None, on_saved=None):
        ticket = object()
        self.busy = ticket
        self.last_poll = self.now()

        def answered(response):
            if self.busy is not ticket or self.identity() != key or self.key != key:
                return
            self.busy = None
            code = getattr(response, 'responseCode', None)
            data = answer(response)
            if code == 200 and is_snapshot(data):
                i18n.accept(data, key[0], key[2])
            if code == 404:
                # The combined quest release is still gated server-side, or
                # this server predates it. Do not expose an unfinished panel.
                self.unavailable = True
                self.offline = False
                self.view.visible(False)
                return
            if code == 409:
                self.offline = False
                self.conflict = True
                self.error = 'Configuration changed elsewhere. Click Reload before editing.'
            elif code != 200 or not is_snapshot(data):
                self.offline = code != 422
                self.error = ('Invalid configuration or access denied.' if code == 422 else None)
            elif payload is not None and (data['config']['version'] != payload['version'] + 1
                                          or any(data['config'][key] != payload[key] for key in ('selection', 'mode', 'manual_ids'))):
                self.offline = False
                self.conflict = True
                self.error = 'Configuration changed again after saving. Click Reload before editing.'
            else:
                # A poll cannot silently resolve a write conflict. The explicit
                # Reload action is the only way to accept its newer version.
                if not self.conflict:
                    self.data = data
                    if payload is not None and on_saved is not None:
                        on_saved()
                self.last_received = self.now()
                self.unavailable = False
                self.offline = False
                self.error = None if not self.conflict else self.error
            if self.garage():
                self.view.render(self)

        try:
            self.session.fetch(url, answered, headers={'X-Mod-Secret': key[2], 'Content-Type': 'application/json'},
                               timeout=config.API_TIMEOUT, method='POST' if payload is not None else 'GET',
                               post_data=json.dumps(payload) if payload is not None else '')
        except Exception:
            # The engine can fail before it installs a response callback. A
            # dead ticket would otherwise block every subsequent garage poll.
            self.busy = None
            self.offline = True
            self.error = None
            return False
        return True

    def save(self, expected_version=None, on_saved=None, **changes):
        if self.data is None or self.conflict or self.busy is not None or not self.garage():
            return
        config_data = dict(self.data['config'])
        config_data.update(changes)
        if expected_version is not None:
            config_data['version'] = expected_version
        # identity() can change between input and request; never send one
        # account's draft with another account's secret.
        if self.identity() != self.key:
            self.tick()
            return
        return self.request(self.url(), self.key, config_data, on_saved)

    def search_players(self, query, completed):
        key = self.identity()
        if key is None or key != self.key or not self.garage():
            completed(None)
            return False
        ticket = object()
        self.search_ticket = ticket
        url = self.url().replace('/quest-garage?', '/quest-garage/players?') + '&q=' + quote(query.encode('utf-8'))
        def answered(response):
            if self.search_ticket is not ticket or self.identity() != key or not self.garage():
                return
            self.search_ticket = None
            data = answer(response)
            rows = data.get('results') if isinstance(data, dict) else None
            valid = (getattr(response, 'responseCode', None) == 200 and isinstance(rows, list)
                     and len(rows) <= 8 and all(isinstance(row, dict) and isinstance(row.get('id'), (int, long))
                     and not isinstance(row['id'], bool) and row['id'] > 0 and isinstance(row.get('username'), basestring)
                     and bool(row['username'].strip()) for row in rows))
            completed(rows if valid else None)
        try:
            self.session.fetch(url, answered, headers={'X-Mod-Secret': key[2]}, timeout=config.API_TIMEOUT)
        except Exception:
            if self.search_ticket is ticket:
                self.search_ticket = None
                completed(None)
            return False
        return True

    def reload(self):
        if self.busy is not None:
            return
        self.conflict = False
        self.error = None
        self.poll(force=True)

    def next_quest(self):
        if not self.data:
            return
        keys = [''] + [choice['key'] for choice in self.data['choices']]
        current = self.data['config']['selection']
        index = keys.index(current) if current in keys else 0
        self.save(selection=keys[(index + 1) % len(keys)])

    def toggle_mode(self):
        if self.data:
            self.save(mode='manual' if self.data['config']['mode'] == 'platoon' else 'platoon')
