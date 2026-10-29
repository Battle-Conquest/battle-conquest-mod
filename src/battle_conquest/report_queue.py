"""The captured battles waiting on disk, until a destination takes them.

A battle that fails to send cannot be played again. The client can be closed
between two battles, or be offline for a whole session, and a season's standing
is computed from counters that must have no holes. So a capture lands here
first, and sending reads from here.

Held in memory as well as on disk: a capture happens on the frame the results
arrive on, and reading a file there is work the player would feel.
"""
import copy
import logging
import os

from battle_conquest import config
from battle_conquest.battle_owner import account_id, report_owner
from battle_conquest.local_store import load_json, save_json
from battle_conquest.quest_details import fill

_logger = logging.getLogger('battle_conquest.report_queue')

# Beside the other things the mod keeps per installation rather than in the
# resource tree: plain data, plain file I/O.
STORE = os.path.join(config.CONFIG_DIR, 'battle-reports.json')

# The contract version the reports are written in. It travels with them on
# disk, so a queue written by an older mod is recognised rather than guessed at.
SCHEMA = 2

# How many captures the queue holds. A ranked evening is a few dozen battles,
# so this covers a player offline for days. Past it the OLDEST go: a destination
# scoring this week's tournament wants this week's battles, and a queue that
# refused new ones would silently stop capturing instead.
LIMIT = 500


def report_key(report):
    arena = report.get('arena_unique_id')
    # Malformed legacy JSON is isolated too; structured IDs cannot be dict keys.
    if not isinstance(arena, (basestring, int, long)):
        arena = id(report)
    return (report_owner(report), bool(report.get('quarantine')),
            account_id(report.get('account')), str(arena))


def trim(reports, limit=LIMIT):
    """The queue, oldest dropped first, down to the limit."""
    counts = {}
    kept = []
    for report in reversed(reports):
        identity = report_owner(report) or ('quarantine', account_id(report.get('account')))
        counts[identity] = counts.get(identity, 0) + 1
        if counts[identity] <= limit:
            kept.append(report)
    return list(reversed(kept))


def deduplicate(reports):
    """One report per owner, region and arena, with isolated history separate.

    A battle can reach the capture twice -- the client posts a battle's results
    again when an older one is opened from the notification centre -- and a
    counter that added it twice would credit score nobody earned. Destinations
    dedupe as well, by (player, arena); this only keeps the queue from carrying
    work already known to be redundant.
    """
    seen = {}
    out = []
    for report in reports:
        arena_id = report.get('arena_unique_id')
        identity = report_key(report)
        if identity in seen:
            first = seen[identity]
            if isinstance(report.get('quest_details'), dict):
                known = first.get('quest_details', {})
                enriched = fill(known, report['quest_details'])
                if enriched != known:
                    # A repair can land after this arena was acknowledged but
                    # before the sender finishes its other batches. Only a
                    # proven acceptance can be rearmed; rejections stay final.
                    accepted = first.get('accepted_by') or []
                    first['sent'] = [key for key in (first.get('sent') or []) if key not in accepted]
                first['quest_details'] = enriched
            continue
        seen[identity] = report
        out.append(report)
    return out


class Queue(object):

    def __init__(self, store=STORE):
        self._store = store
        self._writable = True
        self._reports = self._read()

    def _read(self):
        try:
            payload = load_json(self._store)
        except (IOError, OSError) as problem:
            if getattr(problem, 'errno', None) != 2:
                self._writable = False
            return []
        except ValueError:
            # Preserve corruption for recovery instead of overwriting history.
            self._writable = False
            _logger.warning('the battle report queue was unreadable; preserved, capture suspended')
            return []
        if not isinstance(payload, dict) or payload.get('schema') not in (1, SCHEMA):
            self._writable = False
            return []
        reports = payload.get('reports')
        if not isinstance(reports, list):
            self._writable = False
            return []
        reports = [report for report in reports if isinstance(report, dict)]
        for report in reports:
            if payload['schema'] == 1 or report_owner(report) is None:
                report['quarantine'] = report.get('quarantine') or 'legacy owner is unverified'
        if any(report.get('quarantine') for report in reports):
            _logger.warning('unverified battle owners are isolated in the local queue')
        return trim(deduplicate(reports))

    def all(self):
        return list(self._reports)

    def add(self, report):
        """Queue one report, and say whether it was new."""
        if not self._writable:
            _logger.error('capture suspended: restore the unreadable queue first')
            return False
        if report_owner(report) is None:
            report['quarantine'] = report.get('quarantine') or 'owner is unverified'
        key = report_key(report)
        known = any(report_key(r) == key for r in self._reports)
        previous = copy.deepcopy(self._reports)
        self._reports = trim(deduplicate(self._reports + [report]))
        if not self.save():
            self._reports = previous
            return False
        return not known

    def isolated(self):
        return sum(1 for report in self._reports if report_owner(report) is None)

    def pending(self, key, modes):
        """The reports this destination wants and has not been given yet."""
        wanted = set(modes)
        return [report for report in self._reports
                if report_owner(report) is not None and report.get('mode') in wanted
                and key not in (report.get('sent') or [])]

    def mark(self, key, arena_ids, account=None, snapshots=None, region=None):
        """Remember that a destination has taken these, whatever its verdict.

        Accepted, duplicate and rejected are all final answers, so all three
        mean the same thing here: this destination is done with the report.
        Retrying a rejection would only ask the same question again.
        """
        taken = set(arena_ids)
        identity = (region or config.REGION, str(account))
        if not taken:
            return
        for report in self._reports:
            arena = report.get('arena_unique_id')
            if arena not in taken or report_owner(report) != identity:
                continue
            # This acknowledgement may wait behind other batches. Preserve
            # only a known acceptance as permission to send new fields later.
            accepted = report.get('accepted_by')
            if not isinstance(accepted, list):
                accepted = []
            if snapshots is not None and arena in snapshots:
                if key not in accepted:
                    accepted.append(key)
            elif key in accepted:
                accepted.remove(key)
            report['accepted_by'] = accepted
            # An accepted report enriched while its request was in flight still
            # owes those newly observed fields. Rejections never get this path.
            if snapshots is not None and arena in snapshots and report.get('quest_details') != snapshots[arena]:
                continue
            sent = report.get('sent')
            if not isinstance(sent, list):
                sent = report['sent'] = []
            if key not in sent:
                sent.append(key)
        self.save()

    def settle(self, owed, account=None, region=None):
        """Settle only this owner's acknowledgements; a pause preserves backlog."""
        identity = (region or config.REGION, str(account))
        kept = []
        for report in self._reports:
            waiting = set(owed(report.get('mode'))) if report_owner(report) == identity else set()
            if not waiting or waiting - set(report.get('sent') or []):
                kept.append(report)
        dropped = len(self._reports) - len(kept)
        if dropped:
            self._reports = kept
            self.save()
        return dropped

    def drop(self, arena_ids, account=None, region=None):
        """Explicit removal is scoped to the owner as well as the arena."""
        taken = set(arena_ids)
        identity = (region or config.REGION, str(account))
        self._reports = [r for r in self._reports
                         if r.get('arena_unique_id') not in taken or report_owner(r) != identity]
        self.save()

    def save(self):
        if not self._writable:
            return False
        try:
            save_json(self._store, {'schema': SCHEMA, 'reports': self._reports})
            return True
        except (IOError, OSError):
            _logger.error('could not persist the battle queue; check disk space and permissions')
            return False
