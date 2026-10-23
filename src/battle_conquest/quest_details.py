"""Additive quest measurements, separate from the historical seven counters.

The two random, single-vehicle observations from #953 establish only the
standard-account economy. Premium and respawn totals remain unverified.
Missing inputs omit a measure; no client clock or zero substitutes for them.
"""
import copy
import json
import time

MODES = ('random', 'ranked', 'onslaught', 'stronghold', 'frontline')
METRICS = ('xp_base', 'xp_total', 'credits_gross', 'credits_net',
           'shots', 'hits', 'piercings', 'explosion_hits')
ECONOMY = ('originalCredits', 'credits', 'factualCredits', 'petSystemCredits',
           'autoLoadCost', 'autoEquipCost', 'autoEquipBoostersCost', 'autoRepairCost',
           'appliedPremiumCreditsFactor100', 'appliedPremiumXPFactor100',
           'boosterCredits', 'orderCredits', 'eventCredits', 'achievementCredits',
           'premSquadCredits', 'referral20Credits', 'wotPlusCredits', 'wotPlusProBoostCredits',
           'originalXP', 'xp', 'factualXP', 'premiumVehicleXP', 'dailyXPFactor10',
           'boosterXP', 'orderXP', 'eventXP', 'appliedPremiumTmenXPFactor100',
           'shots', 'directHits', 'piercings', 'explosionHits', 'kills', 'spotted',
           'damageDealt', 'damageReceived', 'damageBlockedByArmor', 'damageAssistedRadio',
           'damageAssistedTrack', 'damageAssistedStun', 'stunNum', 'deathReason')


def capabilities():
    return {'schema': 1, 'fields': ['started_at', 'vehicles', 'economy'] + list(METRICS),
            'modes': list(MODES),
            'verified_scenarios': ['random_single_standard', 'first_win', 'pet_bonus']}


def header():
    return json.dumps(capabilities(), separators=(',', ':'))


def integer(value, bound=100000000, signed=False):
    return (isinstance(value, (int, long)) and not isinstance(value, bool)
            and (-bound if signed else 0) <= value <= bound)


def quest_mode(bonus, constants=None):
    if not integer(bonus):
        return None
    if constants is None:
        from constants import ARENA_BONUS_TYPE as constants
    # Keep the historical classification intact. Training/tournament variants
    # sharing an old family are not an eligible challenge mode.
    names = {'random': ('REGULAR', 'RANDOM_NP2', 'EPIC_RANDOM'),
             'ranked': ('RANKED',), 'onslaught': ('COMP7', 'COMP7_LIGHT'),
             'stronghold': ('SORTIE_2', 'FORT_BATTLE_2'), 'frontline': ('EPIC_BATTLE',)}
    for mode, candidates in names.items():
        if bonus in [getattr(constants, name) for name in candidates if hasattr(constants, name)]:
            return mode
    return None


def fill(known, incoming):
    out = copy.deepcopy(known) if isinstance(known, dict) else {}
    for key, value in incoming.items():
        if value is None:
            continue
        if key not in out or out[key] is None:
            out[key] = copy.deepcopy(value)
        elif key in ('metrics', 'economy') and isinstance(value, dict) and isinstance(out[key], dict):
            out[key] = fill(out[key], value)
    return out


def observations(vehicle):
    economy = {}
    costs = {'autoLoadCost': 2, 'autoEquipCost': 3, 'autoEquipBoostersCost': 3}
    for key in ECONOMY:
        value = vehicle.get(key)
        if key in costs:
            if isinstance(value, (list, tuple)) and len(value) == costs[key] and all(integer(v) for v in value):
                economy[key] = list(value)
        elif integer(value, signed=True):
            economy[key] = value
    return economy


def details_of(results, constants=None):
    common, personal = results.get('common', {}), results.get('personal', {})
    mode = quest_mode(common.get('bonusType'), constants)
    if mode is None:
        return None
    out = {'mode': mode}
    start, duration = common.get('arenaCreateTime'), common.get('duration')
    if integer(start, 4102444799) and integer(duration, 86400):
        out['started_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start))
    entries = [value for key, value in personal.items() if key != 'avatar']
    vehicles = [value for value in entries if isinstance(value, dict)]
    complete = len(entries) == len(vehicles)
    tanks = [value.get('typeCompDescr') for value in vehicles]
    if complete and tanks and len(tanks) <= 64 and all(integer(tank, 4294967295) and tank > 0 for tank in tanks):
        out['vehicles'] = sorted(set(tanks))
    raw_vehicles = []
    for vehicle in vehicles[:64]:
        entry = {'fields': observations(vehicle)}
        tank = vehicle.get('typeCompDescr')
        if integer(tank, 4294967295) and tank > 0:
            entry['tank_id'] = tank
        raw_vehicles.append(entry)
    if raw_vehicles:
        out['vehicle_observations'] = raw_vehicles
    if not complete or len(vehicles) != 1:
        return out
    vehicle = vehicles[0]
    metrics = {}
    for ours, theirs in (('shots', 'shots'), ('hits', 'directHits'),
                         ('piercings', 'piercings'), ('explosion_hits', 'explosionHits')):
        value = vehicle.get(theirs)
        if integer(value, 1000000):
            metrics[ours] = value
    # No inferred XP multiplier: retain the game's explicit base and total.
    if integer(vehicle.get('appliedPremiumXPFactor100')) and vehicle['appliedPremiumXPFactor100'] == 100:
        for ours, theirs in (('xp_base', 'originalXP'), ('xp_total', 'xp')):
            if integer(vehicle.get(theirs), 1000000):
                metrics[ours] = vehicle[theirs]
    economy = observations(vehicle)
    costs = ('autoLoadCost', 'autoEquipCost', 'autoEquipBoostersCost')
    if economy:
        out['economy'] = economy
    # Do not generalise the observed credit formula to untested contexts.
    no_extra = ('boosterCredits', 'orderCredits', 'eventCredits', 'achievementCredits',
                'premSquadCredits', 'referral20Credits', 'wotPlusCredits', 'wotPlusProBoostCredits')
    standard = (mode == 'random' and vehicle.get('isPremium') is False
                and economy.get('appliedPremiumCreditsFactor100') == 100
                and all(economy.get(key) == 0 for key in no_extra))
    gross, earned, pet = (economy.get(key) for key in ('originalCredits', 'credits', 'petSystemCredits'))
    if (standard and all(integer(value) for value in (gross, earned, pet))
            and earned == gross + pet and economy.get('factualCredits') == earned):
        metrics['credits_gross'] = gross
        if all(key in economy for key in costs) and integer(economy.get('autoRepairCost')):
            # The first slot alone is credits. Never sum across currencies,
            # and never charge the theoretical value of consumed inventory.
            net = earned - economy['autoRepairCost'] - sum(economy[key][0] for key in costs)
            if integer(net, signed=True):
                metrics['credits_net'] = net
    if metrics:
        out['metrics'] = metrics
    return out
