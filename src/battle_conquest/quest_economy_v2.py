"""Explicit random-battle economies; delayed premium rewards never score.

Credit +50% and free-XP +200% reserves follow the user's stated hypothesis.
The numerical gains are read from results, never reconstructed from a factor.
"""


def integer(value, bound=100000000, signed=False):
    return (isinstance(value, (int, long)) and not isinstance(value, bool)
            and (-bound if signed else 0) <= value <= bound)


def known_zero(values, keys):
    return all(integer(values.get(key)) and values[key] == 0 for key in keys)


def without_delayed_bonus(values, raw, expected, subtotal):
    if not integer(raw, 1000000) or not integer(expected, 1000000):
        return False
    extra = values.get('additionalXPFactor10')
    if not integer(extra) or extra not in (10, 30):
        return False
    return raw == expected or (extra == 30 and raw - expected in (2 * subtotal, 3 * subtotal))


def xp_values(values):
    zeros = ('premiumVehicleXP', 'orderXP', 'achievementXP', 'squadXP',
             'referral20XP', 'playerRankXP', 'xpPenalty', 'originalXPPenalty')
    keys = ('originalXP', 'subtotalXP', 'xp', 'factualXP', 'boosterXP', 'eventXP')
    if (not known_zero(values, zeros)
            or not all(integer(values.get(key), 1000000) for key in keys)
            or not integer(values.get('dailyXPFactor10')) or values['dailyXPFactor10'] not in (10, 20)
            or not integer(values.get('igrXPFactor10')) or values['igrXPFactor10'] != 10):
        return {}
    reserve = values.get('boosterXPFactor100')
    if (not integer(reserve) or reserve not in (0, 50)
            or (reserve == 0 and values['boosterXP'] != 0)):
        return {}
    subtotal = values['subtotalXP']
    total = subtotal * values['dailyXPFactor10'] // 10 + values['boosterXP'] + values['eventXP']
    if (not without_delayed_bonus(values, values['xp'], total, subtotal)
            or values['factualXP'] not in (total, total - values['eventXP'],
                                          values['xp'], values['xp'] - values['eventXP'])):
        return {}
    return {'xp_base': values['originalXP'], 'xp_wg': subtotal, 'xp_total': total}


def free_xp_values(values):
    keys = ('originalFreeXP', 'subtotalFreeXP', 'freeXP', 'factualFreeXP', 'boosterFreeXP', 'eventFreeXP')
    zeros = ('orderFreeXP', 'achievementFreeXP', 'wotPlusFreeXP', 'wotPlusProBoostFreeXP')
    if (not all(integer(values.get(key), 1000000) for key in keys)
            or not known_zero(values, zeros)
            or not integer(values.get('dailyXPFactor10')) or values['dailyXPFactor10'] not in (10, 20)):
        return {}
    reserve = values.get('boosterFreeXPFactor100')
    if (not integer(reserve) or reserve not in (0, 200)
            or (reserve == 0 and values['boosterFreeXP'] != 0)):
        return {}
    subtotal = values['subtotalFreeXP']
    total = subtotal * values['dailyXPFactor10'] // 10 + values['boosterFreeXP'] + values['eventFreeXP']
    if (not without_delayed_bonus(values, values['freeXP'], total, subtotal)
            or values['factualFreeXP'] not in (total, total - values['eventFreeXP'],
                                              values['freeXP'], values['freeXP'] - values['eventFreeXP'])):
        return {}
    return {'free_xp_base': values['originalFreeXP'], 'free_xp_premium': subtotal, 'free_xp_total': total}


def credit_values(values):
    zeros = ('orderCredits', 'achievementCredits', 'premSquadCredits', 'referral20Credits',
             'wotPlusCredits', 'wotPlusProBoostCredits',
             'creditsContributionIn', 'creditsContributionOut', 'creditsPenalty')
    keys = ('originalCredits', 'subtotalCredits', 'credits', 'factualCredits',
            'petSystemCredits', 'boosterCredits', 'eventCredits')
    if (not known_zero(values, zeros)
            or not all(integer(values.get(key)) for key in keys)):
        return {}
    # An absent reserve factor is compatible only with an explicitly zero gain
    # (legacy #1052 results); a nonzero reserve needs its declared factor.
    reserve = values.get('boosterCreditsFactor100')
    if ((reserve is not None and (not integer(reserve) or reserve not in (0, 50)))
            or (values['boosterCredits'] != 0 and reserve != 50)):
        return {}
    earned = values['subtotalCredits'] + values['petSystemCredits'] + values['boosterCredits'] + values['eventCredits']
    if (not integer(earned) or values['credits'] != earned
            or values['factualCredits'] not in (earned, earned - values['eventCredits'])):
        return {}
    metrics = {'credits_gross': values['originalCredits'],
               'credits_gross_premium': values['subtotalCredits'], 'credits_total': earned}
    costs = (('autoLoadCost', 2), ('autoEquipCost', 3), ('autoEquipBoostersCost', 3))
    if not integer(values.get('autoRepairCost')):
        return metrics
    for key, size in costs:
        value = values.get(key)
        if (not isinstance(value, (list, tuple)) or len(value) != size
                or not all(integer(item) for item in value)):
            return metrics
    expense = values['autoRepairCost'] + sum(values[key][0] for key, _ in costs)
    for key, amount in (('credits_net', earned), ('credits_net_base', values['originalCredits']),
                        ('credits_net_premium', values['subtotalCredits'])):
        if integer(amount - expense, signed=True):
            metrics[key] = amount - expense
    return metrics


def standard_credits(values):
    """Keep the established standard-account proof when no subtotal is exposed."""
    zeros = ('boosterCredits', 'orderCredits', 'eventCredits', 'achievementCredits',
             'premSquadCredits', 'referral20Credits', 'wotPlusCredits', 'wotPlusProBoostCredits')
    if (values.get('isPremium') is not False or not known_zero(values, zeros)
            or not all(integer(values.get(key)) for key in ('originalCredits', 'credits', 'factualCredits', 'petSystemCredits'))
            or values['credits'] != values['originalCredits'] + values['petSystemCredits']
            or values['factualCredits'] != values['credits']):
        return {}
    # These fields were not part of the original standard proof. Do not
    # synthesize them for v2: preserve only its two established measures.
    result = {'credits_gross': values['originalCredits']}
    costs = (('autoLoadCost', 2), ('autoEquipCost', 3), ('autoEquipBoostersCost', 3))
    if (integer(values.get('autoRepairCost'))
            and all(isinstance(values.get(key), (list, tuple)) and len(values[key]) == size
                    and all(integer(item) for item in values[key]) for key, size in costs)):
        net = values['credits'] - values['autoRepairCost'] - sum(values[key][0] for key, _ in costs)
        if integer(net, signed=True):
            result['credits_net'] = net
    return result


def metrics(values, mode):
    if mode != 'random':
        return {}
    factor = values.get('appliedPremiumXPFactor100')
    result = {}
    if (integer(factor) and factor in (100, 150)
            and (factor == 100 or values.get('isPremium') is True)):
        xp = xp_values(values)
        if factor == 100 and not xp:
            # Preserve the pre-existing standard-account correspondence.
            if integer(values.get('originalXP'), 1000000):
                xp.update(xp_base=values['originalXP'], xp_wg=values['originalXP'])
            if integer(values.get('xp'), 1000000):
                xp['xp_total'] = values['xp']
        result.update(xp)
        result.update(free_xp_values(values))
    factor = values.get('appliedPremiumCreditsFactor100')
    if (integer(factor) and factor in (100, 150)
            and (factor == 100 or values.get('isPremium') is True)):
        credits = credit_values(values)
        if factor == 100 and not credits:
            credits = standard_credits(values)
        result.update(credits)
    return result
