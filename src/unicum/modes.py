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

assert set(_BONUS_TYPES) | set(['other']) == set(MODES)


def mode_of(bonus_type, constants=None):
    """The MODES name of an arena bonus type."""
    if constants is None:
        from constants import ARENA_BONUS_TYPE as constants
    for mode, names in _BONUS_TYPES.items():
        if bonus_type in [getattr(constants, name) for name in names if hasattr(constants, name)]:
            return mode
    return 'other'
