"""Private, read-only catalogue access. Never included in a public package."""
import hashlib
import re

MAX_VEHICLES = 10000
_NAME = re.compile(r'\A[A-Za-z0-9_:. -]{1,128}\Z')
_TAG = re.compile(r'\A[A-Za-z0-9_.:-]{1,64}\Z')


def game_version():
    from helpers import getClientVersion
    version = getClientVersion()
    if not isinstance(version, basestring) or not version.strip() or len(version) > 96:
        raise ValueError('client version unavailable')
    return version


def vehicles():
    """Read the client's national lists, not the player's inventory or a path."""
    from items import vehicles as client_vehicles
    import nations
    seen = set()
    for nation_id, nation in enumerate(nations.NAMES):
        if nation not in nations.AVAILABLE_NAMES:
            continue
        national = client_vehicles.g_list.getList(nation_id)
        if not isinstance(national, dict) or not national:
            raise ValueError('national catalogue unavailable')
        for descriptor in national.itervalues():
            tank_id = descriptor.compactDescr
            name = descriptor.name
            tags = sorted(set(descriptor.tags))
            if (not isinstance(tank_id, (int, long)) or isinstance(tank_id, bool)
                    or not 0 < tank_id <= 2147483647 or tank_id in seen
                    or not isinstance(name, basestring) or not _NAME.match(name)
                    or len(tags) > 64
                    or any(not isinstance(tag, basestring) or not _TAG.match(tag) for tag in tags)):
                raise ValueError('invalid or duplicate vehicle descriptor')
            seen.add(tank_id)
            if len(seen) > MAX_VEHICLES:
                raise ValueError('catalogue too large')
            yield {'tank_id': tank_id, 'name': name, 'tags': tags}


def fingerprint(entries):
    """ASCII rows shared with PHP; independent of JSON formatting and iteration order."""
    canonical = ''.join('%s\t%s\t%s\n' % (v['tank_id'], v['name'], ','.join(v['tags']))
                        for v in sorted(entries, key=lambda v: v['tank_id']))
    return hashlib.sha256(canonical.encode('ascii')).hexdigest()
