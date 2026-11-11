"""Local display switches, independent of sending and scoped to game accounts."""
import logging
import os

from battle_conquest import config
from battle_conquest.local_store import load_json, save_json

_logger = logging.getLogger('battle_conquest.display_preferences')
STORE = os.path.join(config.CONFIG_DIR, 'garage-displays.json')


class Preferences(object):
    def __init__(self, store=STORE):
        self.store, self.accounts = store, {}
        try:
            data = load_json(store)
            if isinstance(data, dict) and data.get('schema') == 1 and isinstance(data.get('accounts'), dict):
                self.accounts = data['accounts']
        except (IOError, OSError, ValueError, TypeError):
            pass

    def key(self, account):
        return '%s|%s|%s' % (config.SITE.rstrip('/'), config.REGION, account)

    def get(self, account):
        row = self.accounts.get(self.key(account), {})
        if not isinstance(row, dict):
            row = {}
        return dict((key, row[key] if isinstance(row.get(key), bool) else default)
                    for key, default in (('widget', True), ('details', False)))

    def set(self, account, name, value):
        if not account or name not in ('widget', 'details', 'fallback_dismissed') or not isinstance(value, bool):
            return
        row = self.get(account)
        row['fallback_dismissed'] = self.fallback_dismissed(account)
        row[name] = value
        self.accounts[self.key(account)] = row
        try:
            save_json(self.store, {'schema': 1, 'accounts': self.accounts})
        except (IOError, OSError):
            _logger.exception('could not save display preferences')

    def fallback_dismissed(self, account):
        row = self.accounts.get(self.key(account), {})
        return isinstance(row, dict) and row.get('fallback_dismissed') is True
