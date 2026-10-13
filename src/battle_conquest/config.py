"""Settings that differ between a dev machine and a released mod."""
import os

# The Wargaming region this client plays on, from the client's own realm. It
# travels with every batch of battles, because one installation plays on one
# realm. Anything else (a test server, a sandbox) reads as EU rather than
# guessing.
_REALM_REGIONS = {'EU': 'eu', 'NA': 'na', 'ASIA': 'asia'}


def region_of(realm):
    return _REALM_REGIONS.get(realm, 'eu')


try:
    from constants import CURRENT_REALM as _REALM
except ImportError:
    _REALM = None

REGION = region_of(_REALM)

_DEFAULT_SITE = 'https://battle-conquest.eu'

# Overridden two ways, neither of which puts a LAN address in the repository.
#
# The environment variable is read once when the client starts, which is no
# use for a mod that is meant to be edited while the game runs. So a
# gitignored local_settings.py wins over it: dropping one in redirects the
# site on the next reload, without restarting anything.
try:
    from battle_conquest import local_settings
except ImportError:
    local_settings = None

SITE = (
    getattr(local_settings, 'SITE', None)
    or os.environ.get('BATTLE_CONQUEST_SITE')
    or _DEFAULT_SITE
).rstrip('/')

API_TIMEOUT = 10.0

# The mod's icon in the modsListApi menu, a resource file indexed when the
# client starts; modsListApi draws its default icon when it is not there.
ICON_RES_PATH = 'gui/maps/icons/battle_conquest/icon.png'

# Everything the mod writes, in one folder of its own beside the other mods'
# configs: the link to the site and the battles waiting to be sent.
CONFIG_DIR = os.path.join('mods', 'configs', 'battle_conquest')
