"""Entry point for the reloadable half of the mod.

The released client loads `mod_battle_conquest.py`, which calls start()
once. In development the client loads `mod_battle_conquest_dev.py` instead:
that stub calls start() and stop() here and reimports this package whenever a
source file under src/ changes, which is what lets the game stay running
across edits.

Both functions must be safe to call at any time and in any order: a reload
is nothing more than stop() followed by a fresh start().
"""
import logging

from battle_conquest import (account, battle_reports, battle_feedback, destinations, i18n, mods_list, notices, report_sender, quest_repairs, quest_garage_view,
                             results_request, settings_window, site_link)
from battle_conquest.modes import MODES
from battle_conquest.report_queue import Queue
from battle_conquest.results_diagnostic import Diagnostic
from battle_conquest.results_identity import request_context
from battle_conquest.runtime.session import Session

VERSION = '1.0.0'

_logger = logging.getLogger('battle_conquest')

_session = None


def start(generation=0):
    """Install everything the mod owns. Idempotent by way of stop()."""
    global _session
    if _session is not None:
        stop()
    _session = Session(generation)
    _logger.info('start: version=%s generation=%s', VERSION, generation)
    try:
        player = account.install(_session)
        places = destinations.install(_session, MODES, account=player)
        i18n.install(_session, player, places)
        site = site_link.install(_session, places, player, version=VERSION)
        # One queue for both halves: the capture writes to it and the sender
        # reads from it, and two objects over one file would each hold their
        # own copy of it.
        queue = Queue()
        reports = battle_reports.install(_session, places, player, queue,
                                         diagnostic=Diagnostic(version=VERSION))
        # After the capture, whose door it delivers through: this asks the
        # server for the battles the player never opened, which is the only way
        # they are captured at all.
        requests = results_request.install(_session, reports.arrived, reports.anything_wanted,
                                            context=request_context)
        sender = report_sender.install(_session, player, places, VERSION, queue)
        quest_repairs.install(_session, player, places, reports.arrived,
                              context=request_context, observe_stale=reports.arrived)
        garage = quest_garage_view.install(_session, player, places, sender)
        battle_feedback.Feedback(_session, garage, reports, sender, requests)
        page = settings_window.install(_session, site, places, sender)
        mods_list.install(_session)
        # After the page, which it falls back on: the garage's notice is how a
        # client without modsSettingsApi links at all.
        notices.install(_session, site, places, player, page)
    except Exception:
        # A feature that fails halfway leaves the ones before it installed.
        # Without this the session is orphaned: the loader sees start() fail
        # and forgets the module, so the next reload has nothing to call
        # stop() on, the package is purged, and the surviving patches are
        # left pointing at torn-down module globals. Undo, then report.
        _logger.exception('start failed, rolling back')
        stop()
        raise


def stop():
    """Release everything the current session owns."""
    global _session
    if _session is None:
        return
    _logger.info('stop: generation=%s', _session.generation)
    try:
        _session.close()
    finally:
        _session = None
