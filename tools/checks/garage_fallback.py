"""Slow Gameface startup, real failures and display preference isolation."""
import os
import shutil
import tempfile
from contextlib import contextmanager

from checks.common import check
from checks.report_sender import _Session


@contextmanager
def garage_display():
    from battle_conquest import garage_display as module, notices
    from battle_conquest.destinations import Destination, battles_url
    from battle_conquest.display_preferences import Preferences
    from battle_conquest.hangar_inject import Bridge
    from battle_conquest.quest_garage import Garage

    class Panel(object):
        editing = None
        shown = False
        def reset(self): pass
        def render(self, garage): pass
        def visible(self, shown, preserve_draft=False): self.shown = shown

    class Client(object):
        time = 100.0
        in_garage = True
        ready = True

        def draw(self):
            self.garage.tick()
            # Stand in for an authenticated server snapshot after a scope change.
            if self.garage.data is None:
                self.garage.data = {}
                self.garage.tick()

        def advance(self, seconds):
            self.time += seconds
            self.draw()

        def command(self, action, scope=None):
            self.display.command({'scope': scope or self.display.scope, 'action': action})

    client = Client()
    session = _Session()
    session.alive = True
    client.account = type('Account', (object,), {'account': '123'})()
    destination = Destination(battles_url(), enabled=True, modes=['random'], secret='a' * 64)
    client.places = type('Places', (object,), {'current': destination, 'linked': True})()
    site = type('Site', (object,), {'running': False})()
    folder = tempfile.mkdtemp()
    preferences = Preferences(os.path.join(folder, 'displays.json'))
    client.warnings = []
    standing = module.at_garage, module.garage_ready, notices.push
    module.at_garage = lambda: client.in_garage
    module.garage_ready = lambda: client.ready
    notices.push = lambda text, warning=False: client.warnings.append(text) if warning else None
    try:
        client.display = module.Displays(session, client.account, client.places, site, Panel(),
                                         preferences, now=lambda: client.time)
        client.display.bridge = Bridge(session, now=lambda: client.time)
        client.display.bridge.installed = True
        client.garage = Garage(session, client.account, client.places, client.display,
                               garage=lambda: client.in_garage, ready=lambda: client.ready,
                               platoon=lambda: [], now=lambda: client.time)
        client.draw()
        yield client
    finally:
        module.at_garage, module.garage_ready, notices.push = standing
        shutil.rmtree(folder)


def check_garage_fallback_startup():
    for delay in (12, 25):
        with garage_display() as client:
            client.advance(delay)
            check('a %ss Gameface startup raises no warning or detailed window' % delay,
                  not client.warnings and not client.display.panel.shown)
            client.command('ready')
            while client.time < 140:
                client.advance(2)
                client.command('ready')
            check('late startup stays healthy beyond the loading grace period',
                  not client.warnings and not client.display.panel.shown)

    with garage_display() as client:
        client.advance(29.9)
        check('a silent installed card gets its full loading grace period',
              not client.warnings and not client.display.panel.shown)
        client.advance(0.1)
        check('a card still silent at 30 seconds opens the fallback with one warning',
              len(client.warnings) == 1 and client.display.panel.shown)
        client.advance(2)
        check('fallback does not repeat its warning or persist display preferences',
              len(client.warnings) == 1 and client.display.switches() == {'widget': True, 'details': False})
        client.command('ready')
        client.draw()
        check('a recovered card closes only the automatically opened detailed window',
              not client.display.panel.shown)
        client.advance(5)
        check('an expired heartbeat still opens fallback without repeating its warning',
              client.display.panel.shown and len(client.warnings) == 1)
        client.command('details')
        client.command('ready')
        client.draw()
        check('recovery preserves explicitly enabled details', client.display.panel.shown)

    with garage_display() as client:
        client.command('ready')
        client.advance(30)
        check('a heartbeat that stops is still detected after the loading grace period',
              len(client.warnings) == 1 and client.display.panel.shown)
        client.display.panel.dismiss()
        client.advance(31)
        check('a deliberately dismissed fallback stays closed', not client.display.panel.shown)

    for bridge in ('missing', 'failed'):
        with garage_display() as client:
            if bridge == 'missing':
                client.display.bridge = None
            else:
                client.display.bridge.installed = False
            client.draw()
            check('a %s Gameface installation falls back immediately' % bridge,
                  len(client.warnings) == 1 and client.display.panel.shown)


def check_garage_fallback_transitions():
    for condition in ('ready', 'in_garage'):
        with garage_display() as client:
            client.advance(25)
            setattr(client, condition, False)
            client.draw()
            client.advance(60)
            check('time outside %s never opens a fallback' % condition,
                  not client.warnings and not client.display.panel.shown)
            setattr(client, condition, True)
            client.draw()
            client.advance(25)
            check('returning to %s grants a new loading period' % condition,
                  not client.warnings and not client.display.panel.shown)
            client.advance(5)
            check('a returning card still missing after 30 seconds falls back',
                  len(client.warnings) == 1 and client.display.panel.shown)

    for change in ('account', 'link'):
        with garage_display() as client:
            client.advance(25)
            previous = client.display.scope
            if change == 'account':
                client.account.account = '456'
            else:
                client.places.current.secret = 'b' * 64
            client.draw()
            client.command('ready', previous)
            client.advance(25)
            check('a new %s gets a fresh grace period without trusting old commands' % change,
                  not client.warnings and not client.display.panel.shown
                  and not client.display.bridge.healthy(client.display.scope))
            client.advance(5)
            check('a silent new %s still opens its own fallback' % change,
                  len(client.warnings) == 1 and client.display.panel.shown)

    with garage_display() as client:
        client.advance(25)
        client.display.switch('widget', False)
        client.advance(60)
        check('a disabled card never raises an unavailable warning', not client.warnings)
        client.display.switch('widget', True)
        client.advance(25)
        check('reenabling the card restarts its loading period',
              not client.warnings and not client.display.panel.shown)
        client.advance(5)
        check('reenabling retains fallback for a card that never responds',
              len(client.warnings) == 1 and client.display.panel.shown)
