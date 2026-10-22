"""Optional server update information, safe to show in the game's HTML labels."""
import json
import re

ACTION = 'battle_conquest.update'


def version(value):
    if not isinstance(value, basestring) or len(value) > 64:
        return None
    match = re.match(r'^v?([0-9]+\.[0-9]+\.[0-9]+)\Z', value.strip(), re.I)
    return match.group(1) if match else None


def numbers(value):
    return tuple(int(part) for part in value.split('.'))


def read(response, installed):
    """Old servers and malformed extensions leave linking fully usable."""
    installed = version(installed)
    if getattr(response, 'responseCode', None) != 200:
        return None
    try:
        payload = json.loads(response.body)
    except (ValueError, TypeError, AttributeError):
        return None
    raw = payload.get('mod_update') if isinstance(payload, dict) else None
    if not isinstance(raw, dict) or installed is None:
        return None
    result = {'installed_version': installed}
    newer = []
    for source in ('wgmods', 'github'):
        available = version(raw.get(source + '_version'))
        result[source + '_version'] = available
        if available and numbers(available) > numbers(installed):
            newer.append((source, available))
    # The target is verified against the advertised stable sources, including
    # the GitHub-only case, before it is allowed into a clickable notice.
    target = max((item[1] for item in newer), key=numbers) if newer else None
    declared = raw.get('target_version')
    if (declared is not None and version(declared) is None) or version(declared) != target:
        return None
    result['target_version'] = target
    result['recommended_source'] = newer[0][0] if newer else None
    return result


def text(update, installed=''):
    installed = version(installed) or 'unknown'
    if update is None:
        return u'Mod version: %s. Update information unavailable.' % installed
    sources = u', '.join(u'%s %s' % (label, update.get(source + '_version') or u'unknown')
                         for source, label in (('wgmods', 'WGMods'), ('github', 'GitHub')))
    if update.get('target_version'):
        recommended = 'WGMods' if update['recommended_source'] == 'wgmods' else 'GitHub'
        return (u'Mod version: %s. Update available: %s. %s. Recommended download: %s.'
                % (installed, update['target_version'], sources, recommended))
    return u'Mod version: %s. %s. No newer known version.' % (installed, sources)


def notice(update, clickable):
    detail = text(update, update['installed_version'])
    action = (u'<a href="event:%s">Update my mod</a>' % ACTION if clickable
              else u'Open the mod settings and click Open to update your mod on the site.')
    return u'Battle-Conquest: %s %s' % (detail, action)
