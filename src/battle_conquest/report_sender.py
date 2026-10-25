"""Draining the queue: every battle to the site once, and nothing sent twice.

Capture and sending are deliberately far apart. A battle is captured on the
frame its results arrive on, where the only safe thing to do is write to disk.
Everything that can fail -- a server down, a secret revoked, a client closed
halfway through an evening -- belongs here instead, where failing costs nothing
but a later try.

What proves the account
-----------------------
The site is told which Wargaming account a battle belongs to, and that claim
is backed by a secret only this installation and the site share, sent in
`X-Mod-Secret`.

An unlinked client sends nothing. A battle report is worth something only to a
site that already knows whose battle it is, and an unlinked client has nothing
to attribute one to.

Final means final
-----------------
A destination answers per report: accepted, duplicate or rejected. All three are
final, so all three end the same way -- the destination is marked as having
taken the report, and the report is dropped once every destination owed it has
taken it. Only an answer that asking again could change is retried. Without
that distinction a rejected battle would be offered again on each tick
for as long as the player kept the mod installed.

One account at a time
---------------------
Only the battles of the account logged in are sent. A machine two people play
on holds both their battles, and each set leaves while its own player is
playing. Sending one account's battles under the other's proof is how a report
ends up attributed to the wrong player, which is the one fault that makes every
number computed downstream wrong rather than merely late.
"""
import copy
import json
import logging
import os
import time

from battle_conquest import config
from battle_conquest.quest_details import capabilities
from battle_conquest import service_hooks
from battle_conquest.modes import MODES
from battle_conquest.report_queue import Queue
from battle_conquest.report_wire import FIELDS, account_number, answer, rejections, wire

_logger = logging.getLogger('battle_conquest.report_sender')

SCHEMA = 1
MOD_NAME = 'battle-conquest-mod'

# Reports per request. The site's own ceiling is 50, and a failure that throws
# away one batch throws away that rather than a whole backlog.
BATCH = 50

# The batch a destination could not read, kept beside the queue for whoever
# has to find out why. One file, overwritten: a diagnosis, not a history.
REFUSED_STORE = os.path.join(config.CONFIG_DIR, 'battle-reports-refused.json')

# Startup wake-up plus the local queue check. Results may arrive after the
# account-becomes-player event; they must not wait five minutes for a drain.
# Empty ticks make no HTTP requests or disk writes, and refusal backoff remains.
_START_DELAY = 20.0
_INTERVAL = 5.0

# How long a destination that could not take a batch is left alone. Matched to
# the quarter of an hour a rate limit is usually counted over, so a mod that
# ran into one does not spend the next window running into it again.
_BACKOFF = 900.0

# Said in the log beside the HTTP code, because the code alone tells a player
# nothing about what they can do.
_ADVICE = {
    400: 'it could not read what we sent, which is ours to fix; the batch is on '
         'disk beside the queue',
    404: 'it has no battle endpoint',
    413: 'the batch was too large for it',
}

def retry_later(code):
    """Whether asking this destination again could change its answer.

    401 counts: a player can renew a revoked secret without restarting the
    client, so a link repaired mid-session heals itself rather than waiting for
    one. Anything else in the 400s is a fault that no amount of asking will
    clear, and asking anyway would spend the player's quota on it.
    """
    if not code:
        # No answer at all: unreachable, or the request never left.
        return True
    return code in (401, 408, 429) or code >= 500


# Refusals about the address rather than the payload. Nothing read the batch,
# so keeping it says nothing about which side was wrong -- and a copy of the
# player's battles left on disk for an endpoint that does not exist is exactly
# the pointless copy destinations.py refuses to make.
_NOT_ABOUT_THE_PAYLOAD = (404, 405, 410)


def keep_refused(batch, code, store=REFUSED_STORE):
    """Leave a batch a destination could not read on disk, beside the queue.

    The shape of a report is a contract between this mod, a client nobody here controls and a server in
    another repository, and a batch that was refused is the only thing that
    says which of the three was wrong.

    Which is why only a refusal of the *payload* is kept. A destination whose
    endpoint is missing never read the batch, so the batch holds no evidence
    about it; the queue already remembers the battles, and the log already says
    the endpoint is not there.
    """
    if not (400 <= (code or 0) < 500):
        return
    if code in _NOT_ABOUT_THE_PAYLOAD:
        return
    try:
        directory = os.path.dirname(store)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(store, 'wb') as handle:
            json.dump({'code': code, 'battles': [wire(report) for report in batch]}, handle)
    except (IOError, OSError):
        _logger.debug('could not write the refused batch down', exc_info=True)


def at_garage():
    """Whether the client is standing in the garage rather than in a battle."""
    try:
        from helpers import isPlayerAccount
        return bool(isPlayerAccount())
    except Exception:
        return False


class Target(object):
    """One destination as the sender sees it: where it is, and what proves us."""

    def __init__(self, url, label, modes, headers=None):
        self.url = url
        self.label = label
        self.modes = tuple(modes)
        # None when nothing can prove the account to it yet, which is not a
        # failure: it is a player who has not linked this destination.
        self.headers = headers

    def __repr__(self):
        return '<Target %s %s>' % (self.label, ','.join(self.modes) or 'nothing')


class Sender(object):
    """Gives each destination the battles it is owed, a batch at a time."""

    def __init__(self, session, account, queue=None, destinations=None,
                 version='', garage=at_garage, refused_store=REFUSED_STORE):
        self._session = session
        self._account = account
        self._queue = queue if queue is not None else Queue()
        self._destinations = destinations
        self._version = version
        self._garage = garage
        self._refused_store = refused_store
        self._busy = False
        # Destinations to leave alone until the client is next started, and
        # destinations to leave alone for a while, by URL.
        self._stopped = {}
        self._waiting = {}
        # What the settings page says about the last batch: when it was
        # answered, and how. None until something has been sent this session.
        self.last_sent = None
        self.last_result = None
        self._listeners = []

    def on_change(self, callback):
        """Be told when a batch has been answered, or the queue has moved."""
        self._listeners.append(callback)

    def _changed(self):
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                _logger.exception('a sender listener failed')

    def waiting(self):
        """How many battles of the account logged in wait to be sent."""
        account = getattr(self._account, 'account', None)
        if account is None:
            return 0
        return len([report for report in self._queue.all() if report.get('account') == account])

    def install(self):
        # Three ways to start, and the first that fires wins. The event is the
        # one that matters: a client that crashed left its battles on disk, and
        # a drain is skipped outside the garage and before the account is known
        # -- so the 20s shot is a guess a slow start loses, and losing it used
        # to mean five minutes with the battles sitting there.
        self._follow_the_garage()
        self._session.callback(_START_DELAY, self.drain)
        self._session.repeat(_INTERVAL, self.drain)
        _logger.info('installed')

    def _follow_the_garage(self):
        """Send as soon as the account becomes the player, if that can be heard."""
        account = service_hooks.account_events()
        event = getattr(account, 'onAccountBecomePlayer', None) if account is not None else None
        if event is None or not hasattr(event, '__iadd__'):
            _logger.info('this client does not announce the account becoming the player; '
                         'battles are sent on the %.0fs tick instead', _INTERVAL)
            return
        self._session.subscribe(event, self._became_player)

    def _became_player(self, *args):
        self.drain()

    def targets(self):
        """Every destination owed battles: the site while it is linked, or nothing.

        Built to the same rule the capture keeps, so the two cannot drift: a
        battle is captured exactly when the destination here would want it.
        """
        targets = []
        for destination in (self._destinations.all() if self._destinations else []):
            if not (destination.enabled and destination.secret and destination.modes):
                continue
            targets.append(Target(destination.url, destination.label, destination.modes,
                                  {'X-Mod-Secret': destination.secret}))
        return targets

    def owed(self, targets=None):
        """mode -> the destinations still waiting for a battle of that mode.

        A destination that refused this session is still counted, and that is
        deliberate rather than an oversight: it has not withdrawn its interest
        the way a destination the player switched off has, so its reports stay
        in the queue until the client is restarted and it can be asked again.
        An endpoint that does not exist yet is the case this is written for.
        """
        targets = self.targets() if targets is None else targets
        return dict((mode, [target.url for target in targets if mode in target.modes])
                    for mode in MODES)

    def drain(self):
        """Give every destination what it is owed, and forget what is settled."""
        if self._busy or not self._garage():
            return
        account = getattr(self._account, 'account', None)
        if account_number(account) is None:
            return
        targets = self.targets()
        owed = self.owed(targets)
        # Before the work is picked, so a report nobody wants any more is never
        # carried into a batch.
        self._queue.settle(lambda mode: owed.get(mode, ()))
        work = []
        now = time.time()
        for target in targets:
            if target.headers is None or target.url in self._stopped:
                continue
            if now < self._waiting.get(target.url, 0):
                continue
            reports = [report for report in self._queue.pending(target.url, target.modes)
                       if report.get('account') == account]
            if reports:
                work.append((target, reports))
        if not work:
            return
        self._busy = True
        self._send(work)

    def _send(self, work):
        """One batch, then the next. One destination at a time, in order."""
        if not work:
            self._busy = False
            self._queue.settle(lambda mode: self.owed().get(mode, ()))
            self._changed()
            return
        target, reports = work[0]
        active = next((current for current in self.targets()
                       if current.url == target.url and current.headers == target.headers), None)
        account = getattr(self._account, 'account', None)
        # A backlog can span several responses. A fresh link/account or a new
        # battle must stop the old work just as it stops the initial drain.
        if not self._garage() or active is None or not reports or reports[0].get('account') != account:
            self._send(work[1:])
            return
        reports = [report for report in reports
                   if report.get('account') == account and report.get('mode') in active.modes]
        if not reports:
            self._send(work[1:])
            return
        batch, rest = copy.deepcopy(reports[:BATCH]), reports[BATCH:]
        # Respawn observations are wider than a legacy report. Respect the
        # server's body limit as well as its report-count limit.
        while len(batch) > 1 and len(self.payload(batch)) > 240000:
            rest.insert(0, batch.pop())
        remaining = ([(target, rest)] if rest else []) + work[1:]

        def answered(response):
            code = getattr(response, 'responseCode', None)
            if code == 200:
                self._took(target, batch, response)
                self._send(remaining)
                return
            self._refused(target, batch, code)
            # On to the next destination, not the next batch: whatever stopped
            # this one stops the rest of its backlog just the same.
            self._send(work[1:])

        _logger.info('sending %d battle(s) to %s', len(batch), target.label)
        try:
            self._post(target, batch, answered)
        except Exception:
            # A transport setup failure installs no callback to release _busy.
            # Keep the reports and apply the ordinary unreachable-site backoff.
            _logger.exception('could not initiate battle delivery to %s', target.label)
            self._refused(target, batch, None)
            self._send(work[1:])

    def _post(self, target, batch, answered):
        headers = dict(target.headers)
        headers['Content-Type'] = 'application/json'
        self._session.fetch(target.url, answered, headers=headers,
                            timeout=config.API_TIMEOUT, method='POST',
                            post_data=self.payload(batch))

    def payload(self, reports):
        """A batch as a destination is given it, the account it belongs to and all."""
        return json.dumps({
            'schema': SCHEMA,
            'client': {'mod': MOD_NAME, 'version': self._version, 'capabilities': capabilities()},
            'account': {'id': account_number(reports[0].get('account')),
                        # A property of the client, not of a battle: one
                        # installation plays on one realm.
                        'region': config.REGION},
            'battles': [wire(report) for report in reports],
        })

    def _took(self, target, batch, response):
        """A batch the destination has answered. Every verdict in it is final."""
        payload = answer(response)
        snapshots = {}
        results = (payload or {}).get('results')
        for result in (results if isinstance(results, list) else []):
            if not isinstance(result, dict) or result.get('status') not in ('accepted', 'duplicate'):
                continue
            index = result.get('index')
            if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(batch):
                report = batch[index]
                snapshots[report['arena_unique_id']] = report.get('quest_details')
        self._queue.mark(target.url, [report['arena_unique_id'] for report in batch],
                         account=batch[0].get('account'), snapshots=snapshots)
        self.last_sent = time.time()
        self.last_result = {'code': 200, 'battles': len(batch),
                            'accepted': (payload or {}).get('accepted'),
                            'duplicates': (payload or {}).get('duplicates'),
                            'rejected': (payload or {}).get('rejected')}
        if payload is None:
            # 200 means the batch was processed, whatever the body turned out
            # to be, so the reports are done either way. Still worth a line: a
            # destination whose answer we cannot read is one whose rejections
            # nobody will ever notice.
            _logger.warning('%s took %d battle(s) and answered in a shape we cannot read',
                            target.label, len(batch))
            return
        refused = rejections(payload)
        if refused:
            _logger.warning('%s rejected some of %d battle(s): %s',
                            target.label, len(batch), ', '.join(refused))
        _logger.info('%s took %d battle(s): %s accepted, %s already known, %s rejected',
                     target.label, len(batch), payload.get('accepted', '?'),
                     payload.get('duplicates', '?'), payload.get('rejected', '?'))

    def _refused(self, target, batch, code):
        """What a destination's refusal means for the batch it refused.

        The reports are kept either way. They are still true, and a link
        renewed or an endpoint deployed makes them sendable again; what changes
        is how soon this destination is asked anything.
        """
        waiting = len(self._queue.pending(target.url, target.modes))
        self.last_sent = time.time()
        self.last_result = {'code': code, 'battles': len(batch)}
        if retry_later(code):
            self._waiting[target.url] = time.time() + _BACKOFF
            _logger.info('%s is not taking battles right now (HTTP %s); %d wait',
                         target.label, code, waiting)
            return
        self._stopped[target.url] = code
        _logger.warning('%s refused a batch (HTTP %s): %s. Nothing more is sent to it '
                        'until the client is restarted, and %d battle(s) wait.',
                        target.label, code, _ADVICE.get(code, 'it gave no usable reason'),
                        waiting)
        keep_refused(batch, code, self._refused_store)


def install(session, account, destinations=None, version='', queue=None):
    """Install the sender over the SAME queue the capture writes to.

    One object, not one each: two Queues over one file each hold their own copy
    of it, and whichever saved last would quietly drop what the other had
    learned -- a battle captured between two drains, or a delivery already made.
    """
    sender = Sender(session, account, queue=queue,
                    destinations=destinations, version=version)
    sender.install()
    return sender
