"""Entry point for the reloadable half of the mod.

The released client loads `mod_unicum.py`, which calls start() once. In
development the client loads `mod_unicum_dev.py` instead: that stub calls
start() and stop() here and reimports this package whenever a source file
under src/ changes, which is what lets the game stay running across edits.

Both functions must be safe to call at any time and in any order: a reload
is nothing more than stop() followed by a fresh start().
"""
import logging

from unicum import (account, battle_reports, destinations, mods_list, report_sender, results_request,
                    settings_window, site_link)
from unicum.modes import MODES
from unicum.report_queue import Queue
from unicum.runtime.session import Session

VERSION = '0.1.0-dev'

_logger = logging.getLogger('unicum')

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
        places = destinations.install(_session, MODES)
        site = site_link.install(_session, places, player)
        # One queue for both halves: the capture writes to it and the sender
        # reads from it, and two objects over one file would each hold their
        # own copy of it.
        queue = Queue()
        reports = battle_reports.install(_session, places, player, queue)
        # After the capture, whose door it delivers through: this asks the
        # server for the battles the player never opened, which is the only way
        # they are captured at all.
        results_request.install(_session, reports.arrived, reports.anything_wanted)
        sender = report_sender.install(_session, player, places, VERSION, queue)
        settings_window.install(_session, site, places, sender)
        mods_list.install(_session)
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
