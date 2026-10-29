"""Result ownership, independent of the login and the optional diagnostic.

Observed on EU 2.4.1.1: personal.avatar.accountDBID and each personal
vehicle's accountDBID identify the same owner; players is keyed by that id.
Never infer ownership from another participant or the current login.
"""
from battle_conquest import config
from battle_conquest.battle_report import own_vehicles

REGIONS = ('eu', 'na', 'ru', 'asia')


def account_id(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, long)):
        return str(value) if value > 0 and value <= 9223372036854775807 else None
    if isinstance(value, basestring) and value and all('0' <= c <= '9' for c in value):
        try:
            return account_id(long(value))
        except ValueError:
            pass
    return None


def owner_of(results, origin=None):
    personal = results.get('personal') if isinstance(results, dict) else None
    if not isinstance(personal, dict):
        return None, 'missing personal results'
    records = own_vehicles(personal)
    avatar = personal.get('avatar')
    if isinstance(avatar, dict):
        records.append(avatar)
    ids = set()
    for record in records:
        if 'accountDBID' not in record:
            continue
        identity = account_id(record['accountDBID'])
        if identity is None:
            return None, 'invalid accountDBID'
        ids.add(identity)
    if len(ids) != 1:
        return None, 'missing or contradictory accountDBID'
    identity = ids.pop()
    if config.REGION not in REGIONS:
        return None, 'unknown region'
    if origin is not None and (not isinstance(origin, dict)
            or account_id(origin.get('id')) != identity or origin.get('region') != config.REGION):
        return None, 'request and result owners disagree'
    return {'id': int(identity), 'region': config.REGION}, None


def report_owner(report):
    owner = report.get('owner')
    if (not isinstance(owner, dict) or isinstance(owner.get('id'), bool)
            or not isinstance(owner.get('id'), (int, long))
            or account_id(owner.get('id')) is None or owner.get('region') not in REGIONS
            or account_id(report.get('account')) != str(owner['id'])
            or report.get('quarantine')):
        return None
    return (owner['region'], str(owner['id']))


def owner_name(results, owner):
    players = results.get('players')
    if not isinstance(players, dict):
        return None
    player = players.get(owner['id'], players.get(str(owner['id'])))
    name = player.get('name') if isinstance(player, dict) else None
    return name if isinstance(name, basestring) else None
