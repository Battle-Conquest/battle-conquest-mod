"""One owner-scoped scheduler for live announcements and persistent recovery."""
import logging
import time

from battle_conquest import service_hooks
from battle_conquest.report_sender import at_garage
from battle_conquest.results_messages import BATTLE_RESULTS, _client, arrival_types, type_name
from battle_conquest.results_cache import (service_channel, results_cache, arena_id_of,
    RequestContext, announced_mode, retryable, LIMIT, _NON_PLAYER, _MAX_ATTEMPTS, _TICK_SECONDS, _STALE_SECONDS)

_logger = logging.getLogger('battle_conquest.results_request')


class Requests(RequestContext):
    """Battles the server announced, asked about one at a time."""

    def __init__(self, session, deliver, taking=None, garage=at_garage, cache=results_cache,
                 limit=LIMIT, now=time.time, context=None, journal=None, captured=None):
        self._journal = journal
        self._captured = captured or (lambda key: False)
        self._garage_ready = now() + 5.0 if journal is not None else 0
        self._was_garage = False
        self._origin = None
        self._session = session
        self._context = context
        self._deliver = deliver
        self._taking = taking if taking is not None else (lambda: True)
        self._garage = garage
        self._cache = cache
        self._limit = limit
        self._now = now
        self._pending = []
        self._attempts = {}
        self._completed = set()
        self._asking = None
        self._ask_ticket = None
        self._asked_at = 0.0
        self._retry_after = 0.0
        self._seen_types = set()
        self._said = set()
        self._origin = self._context_now()
        if journal is not None:
            self._pending = sorted(journal.entries, key=lambda key: journal.entries[key]['observed'])
            self._attempts = dict((key, row['attempts']) for key, row in journal.entries.items())

    def install(self):
        """Follow the server's announcements, and say whether anything was."""
        self._follow_the_garage()
        self._session.repeat(_TICK_SECONDS, self.drain)
        channel = service_channel()
        if channel is None:
            _logger.warning('no messenger events in this client, so a battle is only captured '
                            'when its results screen is opened')
            return False
        event = getattr(channel, 'onChatMessageReceived', None)
        if event is None or not hasattr(event, '__iadd__'):
            _logger.warning('the service channel announces nothing this mod can attach to, so a '
                            'battle is only captured when its results screen is opened')
            return False
        # The public event rather than the private method every other mod
        # patches: one is handed to subscribers by name, the other is a
        # name-mangled attribute that two mods cannot both wrap safely.
        self._session.subscribe(event, self._announced)
        _logger.info('asking the client for the results of every battle the server announces')
        return True

    def _follow_the_garage(self):
        """Drain when the account becomes the player, if that can be followed."""
        account = service_hooks.account_events()
        event = getattr(account, 'onAccountBecomePlayer', None) if account is not None else None
        avatar = getattr(account, 'onAvatarBecomePlayer', None)
        if avatar is not None and hasattr(avatar, '__iadd__'):
            self._session.subscribe(avatar, self._entered_battle)
        if event is None or not hasattr(event, '__iadd__'):
            _logger.info('this client does not announce the account becoming the player; '
                         'battles are asked about on the %.0fs tick instead', _TICK_SECONDS)
            return
        self._session.subscribe(event, self._became_player)

    def _entered_battle(self, *args):
        if not getattr(self._session, 'alive', True) or not self._taking():
            return
        self._was_garage = False
        try:
            import BigWorld
            arena = getattr(BigWorld.player(), 'arenaUniqueID', None)
            if arena is not None:
                self.remember(arena, origin=self._origin or {})
        except Exception:
            _logger.exception('could not journal the arena at battle entry')

    def _became_player(self, *args):
        if self._journal is not None:
            self._garage_ready = self._now() + 5.0
            self._origin = self._context_now()
        self.drain()
        self._session.callback(5.0 if self._journal is not None else 1.0, self.drain)

    def _announced(self, client_id=None, message=None, *args):
        """A server message arrived. Keep it if it is a battle worth asking about."""
        self._note_type(message)
        arena_id = arena_id_of(message)
        if arena_id is None:
            return
        if not self._taking():
            self._say_once('nothing taking',
                           'a battle finished, but nothing is taking battle reports right now, '
                           'so the server is not asked about it. Turn the setting on, or link a '
                           'site that wants it')
            return
        origin = self._context_now()
        if self._journal is not None and not (origin or {}).get('id'):
            origin = self._origin or origin
        scope = (origin.get('region'), origin.get('id')) if origin is not None else None
        known = next((key for key in self._pending + ([self._asking] if self._asking else [])
                      if self._arena(key) == arena_id and (not isinstance(key, tuple) or key[:2] == scope)), None)
        if isinstance(known, tuple):
            origin = dict(region=known[0], id=known[1])
        if self.remember(arena_id, origin=origin, announced=True):
            _logger.info('the server announced a %s battle, %s',
                         announced_mode(message) or 'battle of an unnamed mode', arena_id)
        self.drain()

    @staticmethod
    def _arena(key):
        return key[2] if isinstance(key, tuple) else key

    def remember(self, arena_id, origin=None, repair=False, announced=False):
        """Queue a battle to ask about, and say whether it was new."""
        if not getattr(self._session, 'alive', True) or not self._taking():
            return False
        if isinstance(arena_id, bool):
            return False
        try:
            arena_id = long(arena_id)
            if not 0 < arena_id <= 18446744073709551615:
                return False
        except (TypeError, ValueError, OverflowError):
            return False
        if self._context is not None:
            origin = self._context_now() if origin is None else origin
            arena_id = (origin.get('region'), origin.get('id'), arena_id)
        if not repair and (arena_id in self._completed or self._captured(arena_id)):
            return False
        if arena_id == self._asking or arena_id in self._pending:
            if self._journal is not None and arena_id in self._journal.entries:
                row = self._journal.entries[arena_id]
                if announced:
                    row['announced'] = True
                due = (max(self._now() + 5.0, self._retry_after)
                       if announced and arena_id != self._asking
                       else max(row['due'], self._now() + 5.0))
                if announced or due != row['due']:
                    row['due'] = due
                    self._journal.save()
            return False
        if self._journal is not None:
            if not self._journal.add(arena_id, self._now(), self._now() + 5.0,
                                     limit=self._limit, protected=self._asking,
                                     repair=repair, announced=announced):
                return False
            dropped = [key for key in self._pending if key not in self._journal.entries]
            for key in dropped:
                self._pending.remove(key)
                self._attempts.pop(key, None)
        self._pending.append(arena_id)
        scope = arena_id[:2] if isinstance(arena_id, tuple) else None
        candidates = self._pending + ([self._asking] if self._asking is not None else [])
        same_owner = [key for key in candidates
                      if (key[:2] if isinstance(key, tuple) else None) == scope]
        overflow = max(0, len(same_owner) - self._limit)
        for dropped in [key for key in same_owner if key != self._asking][:overflow]:
            self._pending.remove(dropped)
            self._attempts.pop(dropped, None)
            if self._journal is not None:
                self._journal.remove(dropped, 'saturated')
            _logger.warning('too many battles waiting for this owner; gave up on %s', dropped)
        return True

    def waiting(self):
        """The battles still to be asked about, oldest first."""
        return [self._arena(key) for key in self._pending]

    def busy(self):
        """Whether a page is still being served, including its in-flight ask."""
        origin = self._context_now()
        pending = self._pending if self._context is None else [key for key in self._pending
                   if key[:2] == (origin.get('region'), origin.get('id')) and key[1] is not None]
        return self._asking is not None or bool(pending)

    def drain(self):
        """Ask about the next battle, if this is a moment that can."""
        if not getattr(self._session, 'alive', True):
            return
        garage = None
        if self._journal is not None:
            garage = self._garage()
            if garage:
                if not self._was_garage:
                    self._garage_ready = self._now() + 5.0
                # Observe even an empty or paused scheduler. Some clients have
                # no account event, and the next avatar no longer exposes ID.
                self._origin = self._context_now()
            self._was_garage = garage
        self._clear_stale()
        if self._journal is not None:
            self._maintain()
        if not self._taking():
            return
        if self._asking is not None or not self._pending or self._now() < self._retry_after:
            return
        # Outside the garage the cache refuses every request, and a refusal
        # spends one of the attempts a battle gets. The sender waits for the
        # same moment, for the same kind of reason.
        if garage is None:
            garage = self._garage()
        if self._journal is not None and garage and self._now() < self._garage_ready:
            return
        if not garage:
            self._say_once('not the player',
                           'battles are waiting, but the account is not the player yet; '
                           'they are asked about on the way back to the garage')
            return
        cache = self._cache()
        if cache is None:
            self._say_once('no cache',
                           'battles are waiting, but this client has no battle results cache '
                           'to ask; they are captured only if their results screen is opened')
            return
        origin = self._context_now()
        if self._context is not None:
            eligible = next((key for key in self._pending
                             if origin.get('id') is not None and key[:2] == (origin.get('region'), origin.get('id'))
                             and (self._journal is None or self._journal.entries[key]['due'] <= self._now())), None)
            if eligible is None:
                return
            self._pending.remove(eligible)
            arena_id = (origin.get('region'), origin.get('id'), self._arena(eligible))
        else:
            arena_id = self._pending.pop(0)
        if self._journal is not None:
            try:
                from battle_conquest.battle_reports import BattleReports
                service = BattleReports._service()
                posted = getattr(service, 'areResultsPosted', None)
                row = self._journal.entries[arena_id]
                if (posted is not None and posted(self._arena(arena_id))
                        and not row.get('repair') and not row.get('posted_waited')):
                    # Give live hooks one grace period. The UI flag cannot
                    # prevent a repair or replace a durable report forever.
                    self._pending.append(arena_id)
                    row['posted_waited'] = True
                    row['due'] = self._now() + 5.0
                    self._journal.save()
                    return
            except Exception:
                _logger.debug('could not check whether results are posted', exc_info=True)
        _logger.info('asking the server about battle %s', arena_id)
        self._attempts[arena_id] = self._attempts.get(arena_id, 0) + 1
        if self._journal is not None:
            row = self._journal.entries[arena_id]
            row['attempts'] = self._attempts[arena_id]
            row['due'] = self._now() + _STALE_SECONDS
            if not self._journal.save():
                self._pending.insert(0, arena_id)
                self._attempts[arena_id] -= 1
                row['attempts'] -= 1
                return
        self._asking = arena_id
        self._asked_at = self._now()
        try:
            ticket = object()
            self._ask_ticket = ticket
            cache.get(self._arena(arena_id), self._answer(arena_id, origin, ticket))
        except Exception:
            _logger.exception('could not ask for the results of battle %s', arena_id)
            self._asking = None
            self._give_up_or_retry(arena_id, retry=False)

    def _clear_stale(self):
        """Stop waiting on an answer that is never going to come.
        """
        if self._asking is None:
            return
        if self._now() - self._asked_at <= _STALE_SECONDS:
            return
        arena_id = self._asking
        self._asking = None
        _logger.warning('no answer about battle %s after %.0fs; moving on', arena_id,
                        _STALE_SECONDS)
        # To the back, not the front: whatever is wrong with this one, the
        # battles behind it have waited long enough to go first.
        self._give_up_or_retry(arena_id, front=False)

    def _answer(self, arena_id, origin=None, ticket=None):

        def answered(code=None, results=None):
            # The game's cache callback cannot be cancelled when this load stops.
            # An old answer must not write to the new load's queue/diagnostic.
            if not getattr(self._session, 'alive', True):
                return
            # Not `arena_id is self._asking`: a stale ask was let go of, and
            # its answer arriving late is still an answer worth keeping.
            current = self._asking == arena_id and self._ask_ticket is ticket
            if current:
                self._asking = None
            if results is None and not current:
                return
            if results is not None:
                self._attempts.pop(arena_id, None)
                if arena_id in self._pending:
                    # Let go of as stale, then answered after all. Without
                    # this it is asked about a second time for an answer
                    # already in hand.
                    self._pending.remove(arena_id)
                try:
                    source = 'the client answering about battle %s' % self._arena(arena_id)
                    if self._context is None:
                        self._deliver(results, source)
                    else:
                        self._deliver(results, source, origin)
                except Exception:
                    _logger.exception('could not capture the answer about battle %s', arena_id)
                if self._journal is not None:
                    if self._captured(arena_id):
                        self.complete(arena_id)
                    elif arena_id in self._journal.entries:
                        self._attempts[arena_id] = self._journal.entries[arena_id]['attempts']
                        self._give_up_or_retry(arena_id)
                self.drain()
                return
            if self._journal is not None and (self._asking is not None or arena_id not in self._journal.entries):
                return
            _logger.info('the client refused to answer about battle %s with code %s',
                         arena_id, code)
            row = self._journal.entries.get(arena_id, {}) if self._journal is not None else {}
            unannounced = self._journal is not None and not row.get('announced') and not row.get('repair')
            # Leaving an ongoing battle can expose the garage before results
            # exist. An unavailable unannounced arena needs a later retry.
            again = retryable(code) or unannounced
            delay = 900.0 if unannounced and not retryable(code) else 20.0
            try:
                non_player = _client('AccountCommands').RES_NON_PLAYER
            except Exception:
                non_player = _NON_PLAYER
            # Faster discovery must not spend all five attempts during the
            # cache's ordinary cooldown or a centre disconnection.
            if again and code != non_player:
                self._retry_after = self._now() + 20.0
            self._give_up_or_retry(arena_id, retry=again, delay=delay)
            if not again:
                self.drain()

        return answered

    def _give_up_or_retry(self, arena_id, retry=True, front=True, delay=20.0):
        attempts = self._attempts.get(arena_id, 0)
        if not retry or attempts >= _MAX_ATTEMPTS:
            self._attempts.pop(arena_id, None)
            if self._journal is not None:
                self._journal.remove(arena_id, 'abandoned after attempts or permanent refusal')
            _logger.warning('giving up on the results of battle %s after %d attempt(s); it is '
                            'captured only if its results screen is opened', arena_id, attempts)
            return
        # At the front by default: the oldest battle is the one the player is
        # likeliest to have already walked away from.
        if self._journal is not None:
            row = self._journal.entries.get(arena_id)
            if row is None:
                return
            row['due'] = max(self._now() + delay, self._retry_after)
            self._journal.save()
        if arena_id not in self._pending:
            self._pending.insert(0 if front else len(self._pending), arena_id)


    def complete(self, key):
        self._completed.add(key)
        if len(self._completed) > 500:
            self._completed.pop()
        if self._journal is not None:
            self._journal.remove(key, 'report saved')
        if key in self._pending:
            self._pending.remove(key)
        self._attempts.pop(key, None)

    def _maintain(self):
        from battle_conquest.recovery_journal import RETENTION
        for key, row in list(self._journal.entries.items()):
            if not row.get('repair') and self._captured(key):
                self.complete(key)
            elif self._now() - row['observed'] >= RETENTION or row['attempts'] >= _MAX_ATTEMPTS and key != self._asking:
                self._journal.remove(key, 'expired or exhausted')
                if key in self._pending:
                    self._pending.remove(key)
                self._attempts.pop(key, None)


def install(session, deliver, taking=None, garage=at_garage, cache=results_cache, context=None,
            journal=None, captured=None):
    requests = Requests(session, deliver, taking=taking, garage=garage, cache=cache, context=context,
                        journal=journal, captured=captured)
    requests.install()
    return requests
