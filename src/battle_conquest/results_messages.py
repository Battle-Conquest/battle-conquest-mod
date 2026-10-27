"""Client message names used by the finished-battle request scheduler."""
import logging

_logger = logging.getLogger('battle_conquest.results_request')
BATTLE_RESULTS = 2


def _client(name):
    """Import a top-level client module, never a sibling of this one.

    Python 2 resolves a bare `import battle_results` inside this package to a
    sibling module first, when one exists -- this package had one, a different
    thing entirely. The import then fails, the failure is caught, and the mod
    quietly follows the wrong set of message types -- which is precisely how
    this was found, by a check rather than by another evening in the garage.
    """
    import importlib
    return importlib.import_module(name)


def arrival_types():
    """Every message type that carries a finished battle, as this client numbers them.

    Not one number, which is the mistake that made the first live test hear
    nothing. `SYS_MESSAGE_TYPE.battleResults` is **the random battle's** type,
    2, and each game mode registers its own on top -- `registerBattleResultSysMsgType`
    injects it past the end of the base enumeration, which ends at 155. A real
    2.4 client announced a finished battle on **161** while this module was
    listening for 2 alone, and said nothing because nothing matched.

    The client keeps the whole set in `ARENA_BONUS_TYPE_TO_SM_TYPE_BATTLE_RESULT`,
    one entry per mode, so that is what is read -- and read at every message
    rather than once, because the modes register while the client starts and
    this mod is installed somewhere in the middle of that.
    """
    found = set()
    try:
        mapping = _client('battle_results').ARENA_BONUS_TYPE_TO_SM_TYPE_BATTLE_RESULT
        found.update(mapping.values())
    except Exception:
        _logger.debug('this client does not map its modes to message types', exc_info=True)
    try:
        found.add(_client('chat_shared').SYS_MESSAGE_TYPE.battleResults.index())
    except Exception:
        _logger.debug('this client does not name its message types', exc_info=True)
    if not found:
        found.add(BATTLE_RESULTS)
    return found


def type_name(kind):
    """What this client calls a message type, or None if it cannot say.

    The enumeration can be read by index, so a number in the log costs nothing
    to turn into a name. Worth the three lines: the first live run raised
    exactly this question about four numbers, and a name answers it where a
    number sends someone to read the client's sources.
    """
    try:
        item = _client('chat_shared').SYS_MESSAGE_TYPE[kind]
        return item.name() if item is not None else None
    except Exception:
        return None


