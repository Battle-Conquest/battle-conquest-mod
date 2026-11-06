"""Two presentations over one authenticated garage controller and one poller."""
import logging
import time
import uuid

from battle_conquest import config
from battle_conquest.display_preferences import Preferences
from battle_conquest.garage_ready import garage_ready
from battle_conquest.i18n import locale, tr
from battle_conquest.quest_garage_text import status_line, metric_value
from battle_conquest.report_sender import account_number, at_garage

_logger = logging.getLogger('battle_conquest.garage_display')
_active = None

LABELS = ('Link my account', 'Account: confirm in your browser', 'Cancel', 'Details',
          'Settings', 'Close', 'No active quest', 'Choose a quest', 'OFFICIAL', 'MOD ESTIMATE',
          'Unavailable', 'Reload', 'Sending: paused', 'Quest tracking unavailable',
          'Configuration conflict - Reload', 'Link suspended: link this account again. Reports retained.')


def on_item(payload):
    if _active is not None:
        _active.command(payload)


class Displays(object):
    renders_unlinked = True

    def __init__(self, session, account, places, site, panel, preferences=None, now=time.time):
        self.session, self.account, self.places, self.site, self.panel = session, account, places, site, panel
        self.preferences = preferences or Preferences()
        self.now = now
        self.bridge = None
        self.garage = None
        self.scope_key = None
        self.scope = None
        self.started = None
        self.allowed = False
        self.notified = set()
        self.restore_scopes = set()
        self.dismissed_fallbacks = set()
        self.panel.dismiss = self.dismiss_details

    def account_id(self):
        return account_number(getattr(self.account, 'account', None))

    @property
    def editing(self):
        return self.panel.editing

    def switches(self):
        return self.preferences.get(self.account_id())

    def switch(self, name, value):
        previous = self.switches().get(name)
        if name == 'details' and value is False and previous is True:
            self.dismissed_fallbacks.add(self.scope_key)
        elif name == 'widget' and value is True and previous is False:
            self.dismissed_fallbacks.discard(self.scope_key)
        self.preferences.set(self.account_id(), name, value)
        if self.garage is not None:
            self.garage.tick()

    def dismiss_details(self):
        self.dismissed_fallbacks.add(self.scope_key)
        self.switch('details', False)

    def visible(self, visible, preserve_draft=False):
        self.allowed = visible
        self.preserve_draft = preserve_draft

    def reset(self):
        self.panel.reset()
        self.scope_key = None

    def fallback(self, ready):
        if not ready or not self.switches()['widget'] or self.scope_key in self.dismissed_fallbacks:
            self.started = None
            return False
        if self.started is None:
            self.started = self.now()
        return (self.bridge is None or not self.bridge.installed
                or (self.now() - self.started > 8 and not self.bridge.healthy(self.scope)))

    def render(self, garage):
        self.garage = garage
        current = self.places.current
        key = (self.account_id(), current.secret if current else None)
        if key != self.scope_key:
            self.scope_key, self.scope = key, uuid.uuid4().hex
            self.started = None
        ready = at_garage() and garage_ready() and self.account_id() is not None
        if ready and self.account_id() not in self.restore_scopes:
            self.restore_scopes.add(self.account_id())
            self.restore_notice()
        fallback = self.fallback(ready)
        if fallback and key not in self.notified:
            self.notified.add(key)
            from battle_conquest.notices import push
            push(tr('Battle-Conquest: integrated card unavailable; using the detailed window.'), warning=True)
        self.panel.visible(self.allowed and (self.switches()['details'] or fallback),
                           preserve_draft=self.preserve_draft)
        self.panel.render(garage)
        if self.bridge is not None:
            self.bridge.publish(self.snapshot(ready))

    def snapshot(self, ready):
        garage = self.garage
        data = garage.data or {}
        # The server orders the authenticated viewer first. Never expose the
        # following players, link secrets or unrelated preferences to Gameface.
        player = (data.get('players') or [{}])[0]
        criteria = []
        for criterion in data.get('criteria', []):
            metric = criterion['criterion_type']
            values = {}
            for source in ('official', 'estimate'):
                score = player.get(source)
                valid = score and score.get('available') and score.get('comparable') is not False
                values[source] = unicode(metric_value(score, metric)) if valid else tr('Unavailable')
            criteria.append({'label': criterion.get('label', metric), 'target': criterion['target_value'], 'values': values})
        current = self.places.current
        linked = self.places.linked and current is not None and not current.blocked
        notice = (garage.error or ('Link suspended: link this account again. Reports retained.' if current and current.blocked else
                  'Account: not linked' if not linked else 'Sending: paused' if not current.enabled else
                  'Quest tracking unavailable' if garage.unavailable else
                  'Connecting...' if garage.data is None and not garage.offline else None))
        return {'scope': self.scope, 'language': locale(), 'shown': ready and self.switches()['widget'],
                'linked': linked, 'running': self.site.running, 'busy': garage.busy is not None,
                'labels': dict((label, tr(label)) for label in LABELS),
                'selected': data.get('selected'), 'choices': [dict(row, status=tr(row['status'])) for row in data.get('choices', [])],
                'automatic': data.get('automatic_selection') is not None,
                'criteria': criteria, 'status': tr(notice) if notice else status_line(garage),
                'blocked': garage.conflict, 'has_data': garage.data is not None,
                'incomplete': any((player.get(source) or {}).get('incomplete') for source in ('official', 'estimate')),
                'incomplete_label': tr('Incomplete data (?)')}

    def accepts(self, payload):
        return (self.session.alive and isinstance(payload, dict) and payload.get('scope') == self.scope
                and self.scope_key == (self.account_id(), self.places.current.secret if self.places.current else None)
                and at_garage() and garage_ready())

    def command(self, payload):
        if not self.accepts(payload):
            return
        action = payload.get('action')
        if action == 'ready' and self.bridge is not None:
            self.bridge.received(self.scope)
        elif action == 'close':
            self.switch('widget', False)
        elif action == 'details':
            self.switch('details', True)
        elif action == 'link':
            self.site.start()
        elif action == 'cancel':
            self.site.unlink()
        elif action == 'settings':
            from battle_conquest.mods_list import open_settings
            open_settings(session=self.session, on_unavailable=self.restore_notice,
                          can_open=lambda: self.accepts(payload))
        elif action == 'reload':
            self.garage.reload()
        elif action == 'select' and self.garage.data:
            selected = payload.get('selection')
            if selected in [row['key'] for row in self.garage.data['choices']] + ['']:
                self.garage.save(selection=selected)

    def restore_notice(self):
        from battle_conquest.notices import push
        text = u'Battle-Conquest: <a href="event:battle_conquest.show_widget">%s</a> | <a href="event:battle_conquest.show_details">%s</a>'
        push(text % (tr('Show garage card'), tr('Show detailed window')))

    def close(self):
        global _active
        if self.bridge is not None:
            self.bridge.close()
        self.panel.close()
        if _active is self:
            _active = None


def install(session, account, places, sender, site):
    global _active
    from battle_conquest.quest_garage import Garage
    from battle_conquest.quest_garage_view import Panel
    displays = Displays(session, account, places, site, Panel(session))
    _active = displays
    from battle_conquest.hangar_inject import Bridge
    displays.bridge = Bridge(session)
    displays.bridge.install()
    garage = Garage(session, account, places, displays)
    displays.panel.garage = garage
    garage.install(sender)
    session.repeat(2.0, displays.bridge.refresh)
    return garage
