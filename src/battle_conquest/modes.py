"""Which kind of battle this is.

The kind comes from the arena's bonus type, which tells Onslaught from its
Light, training and tournament variants and a Stronghold battle from a random
one; the GUI type is coarser. A bonus type not listed here, such as a seasonal
event, is "other".

The names are part of the contract with the site: a captured battle carries
one of them, and the site answers which of them it scores.
"""
MODES = ('random', 'ranked', 'onslaught', 'stronghold', 'frontline', 'training', 'other')

# MODES -> the ARENA_BONUS_TYPE names they cover. Names rather than numbers: a
# name missing from this client's constants is skipped.
_BONUS_TYPES = {
    'random': ('REGULAR', 'RANDOM_NP2', 'EPIC_RANDOM'),
    'ranked': ('RANKED',),
    'onslaught': ('COMP7', 'COMP7_LIGHT', 'TOURNAMENT_COMP7', 'TRAINING_COMP7'),
    'stronghold': ('SORTIE_2', 'FORT_BATTLE_2', 'CLAN', 'GLOBAL_MAP'),
    'frontline': ('EPIC_BATTLE', 'EPIC_BATTLE_TRAINING'),
    'training': ('TRAINING', 'EPIC_RANDOM_TRAINING'),
}

# Stable API slug -> verified symbolic ARENA_BONUS_TYPE names.
# Add a rule only after observing the event on an actual client.
_EVENT_BONUS_TYPES = {}

assert set(_BONUS_TYPES) | set(['other']) == set(MODES)


def mode_of(bonus_type, constants=None):
    """The MODES name of an arena bonus type."""
    if constants is None:
        from constants import ARENA_BONUS_TYPE as constants
    for mode, names in _BONUS_TYPES.items():
        if bonus_type in [getattr(constants, name) for name in names if hasattr(constants, name)]:
            return mode
    return 'other'


def _event_types(constants):
    if not _EVENT_BONUS_TYPES:
        return {}
    if constants is None:
        try:
            from constants import ARENA_BONUS_TYPE as constants
        except ImportError:
            # Linking and sending can advertise the base capabilities before
            # the client makes its battle constants available.
            return {}
    types = {}
    for submode, names in _EVENT_BONUS_TYPES.items():
        for name in names:
            value = getattr(constants, name, None)
            if (isinstance(value, (int, long)) and not isinstance(value, bool)
                    and value > 0 and mode_of(value, constants) == 'other'):
                types.setdefault(value, set()).add(submode)
    return dict((value, next(iter(submodes))) for value, submodes in types.items()
                if len(submodes) == 1)


def event_submode(bonus_type, constants=None):
    """Resolve a confirmed event, leaving ambiguous and unknown results generic."""
    if not isinstance(bonus_type, (int, long)) or isinstance(bonus_type, bool):
        return None
    return _event_types(constants).get(bonus_type)


def supported_event_submodes(constants=None):
    """Advertise only event rules this version of the game can resolve."""
    return sorted(set(_event_types(constants).values()))
