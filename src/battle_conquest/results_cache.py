"""Ask the client cache for results, using owner-scoped pending requests.

The service channel announces arenaUniqueID before any result screen opens.
The same battleResultsCache.get call the client uses retrieves those results;
cache .dat files are scratch copies, not a recovery source. Cache retrieval
also acknowledges the notification, so retain the live result-screen checks.
"""
import logging

from battle_conquest.results_messages import BATTLE_RESULTS, _client, arrival_types, type_name

_logger = logging.getLogger('battle_conquest.results_request')

# AccountCommands' refusals, for a client that does not hand them over. Only
# the three that mean "later" rather than "never" matter here.
_NON_PLAYER = -3
_COOLDOWN = -5
_DISCONNECTED = -7

# The cache serves one request at a time and answers the second with a
# cooldown, so these are asked for in single file. A tick takes the next one
# and retries whatever was refused for a reason that passes.
_TICK_SECONDS = 5.0
# An answer that never comes would otherwise hold the queue shut for the whole
# session. Long enough that a slow server is not mistaken for a lost callback.
_STALE_SECONDS = 60.0
# Asked for at most this many times before a battle is given up on, so a
# refusal that is somehow permanent cannot turn into a request every tick for
# as long as the client runs.
_MAX_ATTEMPTS = 5
# Battles waiting to be asked about. A player who queues straight into battle
# all evening builds this up; the number is generous because each entry is an
# integer, and the oldest goes first when it overflows.
LIMIT = 50


def service_channel():
    """The messenger events every server message passes through, or None."""
    try:
        from messenger.proto.events import g_messengerEvents
        return g_messengerEvents.serviceChannel
    except Exception:
        _logger.debug('could not reach the messenger events', exc_info=True)
        return None


def results_cache():
    """The account's battle results cache, or None when there is no account."""
    try:
        import BigWorld
        return getattr(BigWorld.player(), 'battleResultsCache', None)
    except Exception:
        _logger.debug('could not reach the battle results cache', exc_info=True)
        return None


def arena_id_of(message, wanted=None):
    """The arena a service channel message is about, when it is a battle's.

    Everything the server says reaches the same event -- rewards, reboots,
    clan news, the repair bill a second after the battle -- so this is the
    filter. A message of the right type with no arena in it is not an error
    worth a line: the server sends battle-adjacent messages that carry no
    battle.
    """
    wanted = arrival_types() if wanted is None else wanted
    if isinstance(wanted, int):
        wanted = (wanted,)
    if getattr(message, 'type', None) not in wanted:
        return None
    data = getattr(message, 'data', None)
    if not isinstance(data, dict):
        return None
    arena_id = data.get('arenaUniqueID')
    if not arena_id:
        return None
    try:
        return int(arena_id)
    except (TypeError, ValueError):
        return None


def announced_mode(message):
    """The kind of battle an announcement is about, or None when it cannot say.

    Read so the mod can decline to ask about a battle nothing is waiting for.
    A player whose only destination scores ranked plays mostly random, and
    asking the server about every one of those would be a request per battle
    for numbers this mod throws away the moment they arrive.

    None rather than a guess when the announcement does not carry the type:
    asking about a battle that turns out to be unwanted costs one request, and
    not asking about a wanted one costs the battle.
    """
    data = getattr(message, 'data', None)
    if not isinstance(data, dict):
        return None
    bonus_type = data.get('bonusType')
    if bonus_type is None:
        return None
    try:
        from battle_conquest.modes import mode_of
        return mode_of(bonus_type)
    except Exception:
        _logger.debug('could not name the mode of an announced battle', exc_info=True)
        return None


def retryable(code):
    """Whether a refusal is worth asking again for.

    Three of them mean "later": the account is not in the garage yet, another
    request is in flight, or the centre is down. Everything else is taken as
    final, because asking forever for a battle the server will not serve is
    indistinguishable from asking for nothing.
    """
    try:
        import AccountCommands
        later = (AccountCommands.RES_NON_PLAYER,
                 AccountCommands.RES_COOLDOWN,
                 AccountCommands.RES_CENTER_DISCONNECTED)
    except Exception:
        later = (_NON_PLAYER, _COOLDOWN, _DISCONNECTED)
    return code in later



class RequestContext(object):
    """Context snapshots and bounded diagnostic logging for the scheduler."""

    def _note_type(self, message):
        """Say once what kinds of message reach this event, and which carry a battle.

        """
        kind = getattr(message, 'type', None)
        if kind in self._seen_types:
            return
        self._seen_types.add(kind)
        named = type_name(kind)
        said = '%s, %s' % (kind, named) if named else str(kind)
        wanted = arrival_types()
        _logger.info('the service channel said something of type %s%s', said,
                     ' -- which is one battles arrive on' if kind in wanted else
                     ' -- not one battles arrive on (those are %s)'
                     % ', '.join(str(one) for one in sorted(wanted)))

    def _say_once(self, key, message, *args):
        """Say something that would otherwise be said every tick, or every battle."""
        if key in self._said:
            return
        self._said.add(key)
        _logger.info(message, *args)

    def _context_now(self):
        if self._context is None:
            return None
        try:
            return dict(self._context())
        except Exception:
            _logger.warning('could not snapshot request context; origin stays unknown')
            return {}

