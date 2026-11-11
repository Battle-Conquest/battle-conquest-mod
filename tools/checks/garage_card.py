"""Card coexistence and settings commands preserve their ownership boundaries."""
import os
import re

from checks.common import REPO, check
from checks.engine import FakeBigWorld


def check_garage_card_ownership():
    directory = os.path.join(REPO, 'src', 'battle_conquest', 'web', 'hangar')
    with open(os.path.join(directory, 'garage.js')) as handle:
        script = handle.read()
    with open(os.path.join(directory, 'garage.css')) as handle:
        style = handle.read()
    # Unicum's DOM classes are observation points, never styling targets.
    # Browser tests cover geometry; this also guards the packaged resources
    # when the Python-only client suite runs without a browser.
    check('garage CSS never takes ownership of Unicum widgets',
          not re.search(r'\.Unicum[^\n{}\'\"]*\{', script + style))
    check('the card cannot inject a competing stylesheet into the garage',
          not re.search(r'createElement\([\'"]style[\'"]\)', script))


def check_garage_card_settings():
    from battle_conquest import garage_display, mods_list
    from battle_conquest.runtime import session as runtime
    from battle_conquest.destinations import Destination, battles_url

    names = ('_open_aslain', '_open_izeberg', '_open_settings_entry')
    originals = [getattr(mods_list, name) for name in names]
    standing = (mods_list.BigWorld, runtime.BigWorld, mods_list.time, mods_list._last_open[:],
                garage_display.at_garage, garage_display.garage_ready)
    scheduler = FakeBigWorld()
    clock, context = [100.0], [True, True]
    calls, notices = [], []
    mods_list.BigWorld = runtime.BigWorld = scheduler
    mods_list._last_open[0] = 0.0
    mods_list.time = type('Clock', (object,), {'time': staticmethod(lambda: clock[0])})
    garage_display.at_garage = lambda: context[0]
    garage_display.garage_ready = lambda: context[1]
    sessions = []

    def outcome(index, success=None, broken=False):
        def open_window():
            calls.append(index)
            if broken:
                raise RuntimeError('optional menu failed')
            return index == success
        return open_window

    def display():
        session = runtime.Session(38)
        sessions.append(session)
        account = type('Account', (object,), {'account': '123'})()
        places = type('Places', (object,), {'current': Destination(battles_url(), secret='a' * 64)})()
        panel = type('Panel', (object,), {})()
        view = garage_display.Displays(session, account, places, None, panel, preferences=object())
        view.scope, view.scope_key = 'current', (123, 'a' * 64)
        view.restore_notice = lambda: notices.append('fallback')
        return view

    try:
        for success in range(3):
            calls[:], notices[:] = [], []
            clock[0] += 3
            for index, name in enumerate(names):
                setattr(mods_list, name, outcome(index, success))
            view = display()
            payload = {'scope': view.scope, 'action': 'settings'}
            view.command(payload)
            view.command(payload)
            check('settings wait until the menu closes without an early notification',
                  not calls and not notices and len(scheduler.pending) == 1)
            scheduler.run_pending()
            check('successful settings adapter %d suppresses fallback and later adapters' % success,
                  calls == list(range(success + 1)) and not notices)

        for broken in (False, True):
            calls[:], notices[:] = [], []
            clock[0] += 3
            for index, name in enumerate(names):
                setattr(mods_list, name, outcome(index, broken=broken))
            view = display()
            payload = {'scope': view.scope, 'action': 'settings'}
            view.command(payload)
            view.command(payload)
            scheduler.run_pending()
            check('absent or failing menus yield exactly one fallback notification',
                  calls == [0, 1, 2] and notices == ['fallback'])

        # An exception in one menu must not prevent the next adapter opening.
        calls[:], notices[:] = [], []
        clock[0] += 3
        mods_list._open_aslain = outcome(0, broken=True)
        mods_list._open_izeberg = outcome(1, success=1)
        view = display()
        view.command({'scope': view.scope, 'action': 'settings'})
        scheduler.run_pending()
        check('a later menu can recover an earlier adapter failure', calls == [0, 1] and not notices)

        for change in ('account', 'link', 'scope', 'battle', 'waiting', 'stop'):
            calls[:], notices[:] = [], []
            clock[0] += 3
            context[:] = [True, True]
            view = display()
            view.command({'scope': view.scope, 'action': 'settings'})
            if change == 'account':
                view.account.account = '456'
            elif change == 'link':
                view.places.current = Destination(battles_url(), secret='b' * 64)
            elif change == 'scope':
                view.scope = 'replacement'
            elif change == 'battle':
                context[0] = False
            elif change == 'waiting':
                context[1] = False
            else:
                view.session.close()
            scheduler.run_pending()
            check('delayed settings are discarded after %s changes' % change, not calls and not notices)

        calls[:] = []
        clock[0] += 3
        mods_list._open_aslain = outcome(0, success=0)
        mods_list.open_settings()
        scheduler.run_pending()
        check('the existing no-argument mod menu callback still opens settings', calls == [0])
    finally:
        for session in sessions:
            session.close()
        for name, original in zip(names, originals):
            setattr(mods_list, name, original)
        (mods_list.BigWorld, runtime.BigWorld, mods_list.time, previous_open,
         garage_display.at_garage, garage_display.garage_ready) = standing
        mods_list._last_open[:] = previous_open
