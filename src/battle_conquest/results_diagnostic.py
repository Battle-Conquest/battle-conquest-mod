"""Opt-in, local observations of personal results; never a wire contract.

Names containing XP or credits are candidates, not proven economic measures.
Only numeric data in those fields and the explicit counters below survives.
In particular this never serializes the results dict, client objects or reprs.
"""
import json
import logging
import math
import os
import re
import time

from battle_conquest import config, modes
from battle_conquest.battle_report import METRICS, arena_id_of
from battle_conquest.results_dict import raw_results

_logger = logging.getLogger('battle_conquest.results_diagnostic')

SETTINGS = os.path.join(config.CONFIG_DIR, 'diagnostics.json')
STORE = os.path.join(config.CONFIG_DIR, 'results-diagnostic.jsonl')
MAX_BYTES = 2 * 1024 * 1024
MAX_RECORD_BYTES = 128 * 1024
_NAME = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,63}\Z')
_COMMON = ('arenaCreateTime', 'duration', 'bonusType', 'winnerTeam', 'arenaTypeID')
_COUNTERS = tuple(theirs for ours, theirs in METRICS) + (
    'typeCompDescr', 'team', 'deathReason', 'damageAssistedRadio',
    'damageAssistedTrack', 'damageAssistedStun', 'damageBlockedByArmor',
    'shots', 'hits', 'directHits', 'piercings', 'explosionHits', 'stunNum', 'stunDuration',
    'autoRepairCost', 'autoLoadCost', 'autoEquipCost', 'autoEquipBoostersCost',
    'repairCost', 'ammoCost', 'equipmentCost', 'repair', 'autoRepair',
    'autoLoad', 'autoEquip', 'autoEquipBoosters', 'premium', 'isPremium',
)


def _name(key):
    return isinstance(key, basestring) and _NAME.match(key) is not None


def _candidate(key):
    return _name(key) and (key in _COUNTERS or 'credits' in key.lower()
                           or 'xp' in key.lower())


def _omitted(reason):
    return {'diagnostic_omitted': reason}


def _numeric(value, budget, depth=0):
    """Retain numeric structures, distinguishing null and unsupported values."""
    if budget[0] <= 0:
        return _omitted('value limit')
    budget[0] -= 1
    if value is None or isinstance(value, (bool, int, long)):
        return value
    if isinstance(value, float):
        return value if not (math.isnan(value) or math.isinf(value)) else _omitted('non-finite')
    if depth >= 6:
        return _omitted('depth limit')
    if isinstance(value, (tuple, list, dict)):
        if len(value) > 128:
            return _omitted('item limit')
        if isinstance(value, dict):
            out = {}
            for key, item in value.items():
                # Item ids and technical names only, never arbitrary text keys.
                if (isinstance(key, (int, long)) or _name(key)
                        or (isinstance(key, basestring) and key.isdigit())):
                    out[str(key)] = _numeric(item, budget, depth + 1)
                else:
                    return _omitted('unsupported mapping key')
            return out
        return [_numeric(item, budget, depth + 1) for item in value]
    return _omitted('unsupported value')


def _personal(value, budget):
    if not isinstance(value, dict):
        return _omitted('not a personal result')
    names = sorted(key for key in value if _name(key))
    return {
        'available_fields': names[:256],
        'field_names_truncated': len(names) > 256,
        'fields': {key: _numeric(value[key], budget) for key in names[:256] if _candidate(key)},
    }


def observation(results, source, account, version, now=time.time, allow_unknown_account=False):
    """Project only common timing/mode and the player's personal measurements."""
    if not isinstance(results, dict):
        return None
    common = results.get('common')
    personal = results.get('personal')
    if not isinstance(common, dict) or not isinstance(personal, dict):
        return None
    arena = arena_id_of(results) or arena_id_of(common)
    if arena is None or (not allow_unknown_account and (not account or not str(account).isdigit())):
        return None
    budget = [4096]
    vehicles = []
    for key, value in personal.items():
        if key == 'avatar':
            continue
        item = _personal(value, budget)
        # The result key is normally the intCD, but do not guess a tank id
        # from it. Unknown string keys are never written as player data.
        item['personal_key'] = str(key) if str(key).isdigit() else None
        vehicles.append(item)
        if len(vehicles) > 64:
            return None
    return {
        'schema': 1,
        'mod_version': version,
        'observed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now())),
        'source': source,
        'account': str(account) if account else None,
        'region': config.REGION,
        'arena_unique_id': arena,
        'mode_as_current_mod': modes.mode_of(common.get('bonusType')),
        'common': {key: _numeric(common[key], budget) for key in _COMMON if key in common},
        'vehicles': sorted(vehicles, key=lambda item: item['personal_key'] or ''),
        'avatar': _personal(personal['avatar'], budget) if 'avatar' in personal else None,
    }


class Diagnostic(object):
    """Bounded JSONL observations independent from the queue and its verdicts."""

    def __init__(self, settings=SETTINGS, store=STORE, version='unknown', limit=MAX_BYTES):
        self._settings = settings
        self._store = store
        self._version = version
        self._limit = limit
        self._last_state = None

    def _options(self):
        try:
            with open(self._settings, 'rb') as handle:
                raw = handle.read(1025)
            value = json.loads(raw) if len(raw) <= 1024 else None
            return value if isinstance(value, dict) else {}
        except (IOError, OSError, ValueError):
            return {}

    def enabled(self):
        # Re-read so the player can disable it without a restart or menu API.
        enabled = self._options().get('enabled') is True
        if enabled != self._last_state:
            _logger.info('local results diagnostic %s', 'enabled' if enabled else 'disabled')
            self._last_state = enabled
        return enabled

    def capture(self, results, source, account, request_context=None):
        if not self.enabled():
            return False
        try:
            identity_enabled = self._options().get('identity_enabled') is True
            # Stale repair answers bypass BattleReports._on_posted's unwrap.
            results = raw_results(results)
            record = observation(results, source, account, self._version,
                                 allow_unknown_account=identity_enabled)
            if record is None:
                _logger.warning('diagnostic skipped: no readable personal results or account')
                return False
            if identity_enabled:
                from battle_conquest.results_identity import observation as identity_observation
                from battle_conquest.results_identity import request_context as current_context
                record['identity'] = identity_observation(results, request_context, current_context())
            line = json.dumps(record, sort_keys=True, allow_nan=False) + '\n'
            if len(line) > min(MAX_RECORD_BYTES, self._limit):
                _logger.warning('diagnostic skipped: observation exceeds size limit')
                return False
            directory = os.path.dirname(self._store)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)
            size = os.path.getsize(self._store) if os.path.exists(self._store) else 0
            separator = ''
            if size:
                with open(self._store, 'rb') as handle:
                    handle.seek(-1, os.SEEK_END)
                    if handle.read(1) != '\n':
                        separator = '\n'
            if size + len(separator) + len(line) > self._limit:
                previous = self._store + '.1'
                if os.path.exists(previous):
                    os.remove(previous)
                os.rename(self._store, previous)
                separator = ''
            with open(self._store, 'ab') as handle:
                # A killed client may leave a partial last line. Isolate it
                # so every later observation is still readable on its own.
                handle.write(separator + line)
            _logger.info('saved local diagnostic for battle %s', record['arena_unique_id'])
            return True
        except Exception:
            # A diagnostic failure must never cost the existing battle report.
            # Do not include exception text: client objects can contain secrets.
            _logger.warning('could not save local results diagnostic; normal capture continues')
            return False
