"""Atomic, owner-scoped recovery metadata; never battle results or secrets."""
import json
import logging
import math
import os

from battle_conquest import config
from battle_conquest.local_store import load_json, save_json

_logger = logging.getLogger('battle_conquest.recovery_journal')
STORE = os.path.join(config.CONFIG_DIR, 'battle-recovery.json')
RETENTION = 7 * 86400


class Journal(object):
    def __init__(self, store=STORE):
        self.store = store
        self.writable = True
        self.entries = {}
        try:
            if not os.path.exists(store) and os.path.exists(store + '.tmp'):
                with open(store + '.tmp', 'rb') as handle:
                    data = json.load(handle)
                _logger.warning('recovering interrupted journal replacement from complete temporary copy')
            else:
                data = load_json(store)
            if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('arenas'), list):
                raise ValueError('invalid journal')
            for row in data['arenas']:
                region, account, arena = row['region'], row['account'], row['arena']
                if (region not in (None, 'eu', 'na', 'asia')
                        or account is not None and (not isinstance(account, basestring) or not account.isdigit())
                        or not isinstance(arena, basestring) or not arena.isdigit()
                        or not 0 < long(arena) <= 18446744073709551615):
                    raise ValueError('invalid identity')
                for field in ('observed', 'due', 'attempts'):
                    if isinstance(row[field], bool) or not isinstance(row[field], (int, long, float)):
                        raise ValueError('invalid metadata')
                if (any(math.isnan(row[f]) or math.isinf(row[f]) for f in ('observed', 'due'))
                        or not isinstance(row['attempts'], (int, long))):
                    raise ValueError('invalid counters')
                if not 0 <= row['attempts'] <= 5 or row['observed'] < 0 or row['due'] < 0:
                    raise ValueError('invalid bounds')
                key = (region, account, long(arena))
                if key in self.entries or sum(1 for k in self.entries if k[:2] == key[:2]) >= 50:
                    raise ValueError('duplicate or saturated owner')
                self.entries[key] = row
        except (IOError, OSError) as error:
            if getattr(error, 'errno', None) != 2:
                self.writable = False
                _logger.error('recovery journal unavailable; preserved, recovery suspended')
        except (ValueError, KeyError, TypeError, OverflowError):
            self.entries = {}
            self.writable = False
            _logger.error('recovery journal corrupt; copies preserved, recovery suspended')

    def save(self):
        if not self.writable:
            return False
        try:
            save_json(self.store, {'schema': 1, 'arenas': list(self.entries.values())})
            return True
        except (IOError, OSError):
            _logger.error('could not persist recovery journal; check disk space and permissions')
            return False

    def add(self, key, now, due):
        if key in self.entries or not self.writable:
            return False
        self.entries[key] = dict(region=key[0], account=key[1], arena=str(key[2]),
                                 observed=now, due=due, attempts=0)
        self.save()
        return True

    def remove(self, key, reason):
        if key in self.entries:
            del self.entries[key]
            _logger.info('recovery %s: %s', reason, key)
            self.save()
