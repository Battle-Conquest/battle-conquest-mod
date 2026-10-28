"""Opaque, observation-local references; no result is certified as an owner."""
import re

from battle_conquest import config
from battle_conquest.account import current_account_id

# Candidate spellings only; none has been validated as an owner field yet.
# Unknown/dynamic keys stay opaque so a nickname used as a key cannot leak.
_FIELDS = frozenset(('accountDBID', 'accountDBId', 'databaseID', 'databaseId',
                     'accountId', 'accountID', 'dbID', 'id', 'name', 'playerName',
                     'nickname', 'avatar', 'avatarID', 'avatarId', 'vehicleID',
                     'vehicleId', 'team', 'typeCompDescr', 'account', 'player',
                     'personal', 'players', 'avatars', 'vehicle', 'vehicles', 'intCD'))
_PRIVATE = re.compile(r'secret|password|token|email|url', re.I)


def request_context():
    # Do not use Account.account: it deliberately remembers the previous login.
    return {'id': current_account_id(), 'region': config.REGION}


def observation(results, origin, current):
    """Project shapes and equalities, never participant scalar values.

    Numeric strings and integers share references so mapping keys can be
    compared with fields. Tokens start afresh in each observation, preventing
    an inventory of participants across battles. Field names are candidates,
    not proof of their meaning in an actual client.
    """
    tokens = {}
    budget = [4096]

    def reference(value):
        if isinstance(value, bool) or value is None:
            return {'type': 'bool' if isinstance(value, bool) else 'null'}
        if isinstance(value, (int, long)):
            key = ('number', str(value))
        elif isinstance(value, basestring):
            key = ('number' if re.match(r'^[0-9]+\Z', value) else 'text', value)
        else:
            return {'type': 'unsupported'}
        if key not in tokens:
            tokens[key] = 'ref%d' % (len(tokens) + 1)
        return {'type': 'integer' if isinstance(value, (int, long)) else 'string',
                'ref': tokens[key]}

    def project(value, depth=0, collection=False):
        if budget[0] <= 0:
            return {'omitted': 'value limit'}
        budget[0] -= 1
        if depth >= 6:
            return {'omitted': 'depth limit'}
        if isinstance(value, dict):
            entries = []
            # Never stringify client objects or arbitrary mapping keys.
            for position, (key, item) in enumerate(value.iteritems()):
                if position >= 128:
                    return {'entries': entries, 'omitted': 'item limit'}
                if not collection and isinstance(key, basestring) and _PRIVATE.search(key):
                    continue
                field = (isinstance(key, basestring) and key in _FIELDS
                         and (not collection or (collection == 'personal' and key == 'avatar')))
                entries.append({'key': {'field': key} if field else reference(key),
                                'value': project(item, depth + 1)})
                if budget[0] <= 0:
                    return {'entries': entries, 'omitted': 'value limit'}
            return {'entries': entries}
        if isinstance(value, (list, tuple)):
            items = []
            for item in value[:128]:
                items.append(project(item, depth + 1))
                if budget[0] <= 0:
                    break
            return {'items': items, 'truncated': len(items) != len(value)}
        return reference(value)

    sections = {}
    for name in ('personal', 'players', 'avatars'):
        if name in results:
            sections[name] = project(results[name], collection=name)
    # Assign context references AFTER projection; these only indicate equality,
    # never that a particular participant is the owner of personal results.
    contexts = {}
    for name, context in (('request', origin), ('receipt', current)):
        contexts[name] = ({'id': context.get('id'), 'region': context.get('region'),
                           'reference': reference(context.get('id'))}
                          if isinstance(context, dict) else None)
    return {'status': 'unverified', 'contexts': contexts, 'sections': sections}
