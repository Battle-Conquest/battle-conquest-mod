"""Explicit personal measurements for the observed single-vehicle scenarios.

Premium base XP and WG XP are different units. Never infer a missing subtotal
from a multiplier, and never apply the random observations to respawn modes.
"""


def integer(value, bound=100000000, signed=False):
    return (isinstance(value, (int, long)) and not isinstance(value, bool)
            and (-bound if signed else 0) <= value <= bound)


def xp_metrics(vehicle, mode):
    factor = vehicle.get('appliedPremiumXPFactor100')
    if not integer(factor):
        return {}
    if factor == 100:
        metrics = {}
        for ours, theirs in (('xp_base', 'originalXP'), ('xp_total', 'xp')):
            if integer(vehicle.get(theirs), 1000000):
                metrics[ours] = vehicle[theirs]
        # This is the pre-existing standard-account correspondence from #814.
        if mode == 'random' and 'xp_base' in metrics:
            metrics['xp_wg'] = metrics['xp_base']
        return metrics
    if mode != 'random' or factor != 150 or vehicle.get('isPremium') is not True:
        return {}
    for key in ('dailyXPFactor10', 'additionalXPFactor10', 'igrXPFactor10'):
        if not integer(vehicle.get(key)) or vehicle[key] != 10:
            return {}
    for key in ('premiumVehicleXP', 'eventXP', 'orderXP', 'achievementXP',
                'squadXP', 'referral20XP', 'playerRankXP', 'xpPenalty', 'originalXPPenalty'):
        if not integer(vehicle.get(key)) or vehicle[key] != 0:
            return {}
    for key in ('originalXP', 'subtotalXP', 'xp', 'factualXP', 'boosterXP'):
        if not integer(vehicle.get(key), 1000000):
            return {}
    booster = vehicle.get('boosterXPFactor100')
    if (not integer(booster) or booster not in (0, 50)
            or (booster == 0 and vehicle['boosterXP'] != 0)
            or vehicle['xp'] != vehicle['subtotalXP'] + vehicle['boosterXP']
            or vehicle['factualXP'] != vehicle['xp']):
        return {}
    return {'xp_base': vehicle['originalXP'], 'xp_total': vehicle['xp'],
            'xp_wg': vehicle['subtotalXP']}


def premium_credits(vehicle, economy, mode):
    if (mode != 'random' or vehicle.get('isPremium') is not True
            or not integer(economy.get('appliedPremiumCreditsFactor100'))
            or economy['appliedPremiumCreditsFactor100'] != 150):
        return {}
    for key in ('boosterCredits', 'orderCredits', 'eventCredits', 'achievementCredits',
                'premSquadCredits', 'referral20Credits', 'wotPlusCredits', 'wotPlusProBoostCredits',
                'creditsContributionIn', 'creditsContributionOut', 'creditsPenalty'):
        if not integer(economy.get(key)) or economy[key] != 0:
            return {}
    for key in ('originalCredits', 'subtotalCredits', 'credits', 'factualCredits', 'petSystemCredits'):
        if not integer(economy.get(key)):
            return {}
    if (economy['credits'] != economy['subtotalCredits'] + economy['petSystemCredits']
            or economy['factualCredits'] != economy['credits']):
        return {}
    metrics = {'credits_gross': economy['originalCredits']}
    costs = ('autoLoadCost', 'autoEquipCost', 'autoEquipBoostersCost')
    # observations() already checks all currencies and array lengths. Only the
    # actual credit slots contribute, including a known zero or a signed loss.
    if all(key in economy for key in costs) and integer(economy.get('autoRepairCost')):
        net = economy['credits'] - economy['autoRepairCost'] - sum(economy[key][0] for key in costs)
        if integer(net, signed=True):
            metrics['credits_net'] = net
    return metrics
