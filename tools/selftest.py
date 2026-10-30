"""Exercise the mod and its reload harness outside the game.

The client is a slow place to find out that a hook did not come back off.
This stands in fake BigWorld and client modules, drives the bootstrap through
a full edit-and-reload cycle, and checks the one property the whole design
rests on: after stop(), the game's own function is back, by identity. Then it
runs every check of the capture, the link and the sender.

    python2.7 tools/selftest.py

Python 2.7, same as the client. Nothing here reaches the network.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checks.battle_report_hooks import (check_battle_report_arrival,
                                        check_battle_report_arrival_as_method,
                                        check_battle_report_hooks,
                                        check_battle_report_no_arrival)
from checks.battle_reports import (check_battle_report_arena_id, check_battle_report_capture,
                                   check_battle_report_queue, check_battle_report_reading,
                                   check_battle_report_tank)
from checks.battle_feedback import check_battle_feedback, check_battle_feedback_refresh, check_garage_finished_selection, check_battle_feedback_identity_callbacks
from checks.recovery_review import check_recovery_review_atomic_capacity, check_recovery_review_posted
from checks.recovery import check_recovery, check_receipts
from checks.client import install_fake_client
from checks.catalog_tester import check_catalog_tester
from checks.common import REPO, check, render_stub
from checks.quest_garage import check_quest_garage, check_quest_garage_age, check_quest_garage_panel, check_quest_garage_platoon
from checks.quest_garage_input import check_quest_garage_input
from checks.garage_ready import check_garage_ready, check_sender_after_capture
from checks.report_sender_responses import check_report_sender_responses
from checks.quest_garage_scroll import check_quest_garage_scroll
from checks.quest_garage_theme import check_quest_garage_theme
from checks.i18n import check_i18n
from checks.native_font import check_native_font
from checks.quest_garage_players import check_quest_garage_players
from checks.quest_details import check_quest_details
from checks.quest_review import check_quest_review
from checks.quest_repairs import check_quest_repairs
from checks.destinations import (check_destination_capture, check_destination_modes,
                                 check_destination_pause_and_forget, check_destination_reading,
                                 check_destination_secrets, check_destination_silence,
                                 check_destination_urls)
from checks.owner_isolation import (check_owner_extraction, check_owner_lifecycle,
                                   check_owner_quarantine, check_owner_refusals,
                                   check_owner_migration, check_owner_requests, check_owner_storage)
from checks.owner_review import (check_owner_unknown_notification, check_owner_isolated_receipt,
                                 check_owner_invalid_legacy_refresh, check_owner_settings_scope)
from checks.owner_migration_review import (check_legacy_unlink_race, check_legacy_unlink_restart,
                                           check_legacy_unlink_owner_scope)
from checks.queue_write_review import check_owner_capture_write_failure, check_owner_enrichment_write_failure
from checks.engine import FakeBigWorld
from checks.mod_updates import (check_mod_updates_contract, check_mod_updates_garage,
                                check_mod_updates_teardown)
from checks.fakes import ORIGINAL_POST_RESULT, FakeBattleResultsService
from checks.notices import (check_notices_click, check_notices_dismiss_reminders,
                            check_notices_remind, check_notices_texts,
                            check_notices_without_handler, check_notices_revoked_link)
from checks.report_sender import (check_report_sender_account, check_report_sender_batching,
                                  check_report_sender_delivery, check_report_sender_payload,
                                  check_report_sender_refusals, check_report_sender_startup,
                                  check_report_sender_status, check_report_sender_targets)
from checks.results_dict import (check_results_dict_cycle, check_results_dict_miss,
                                 check_results_dict_paths, check_results_dict_said_once,
                                 check_results_dict_search)
from checks.results_diagnostic import (check_diagnostic_projection, check_diagnostic_bounded_values,
                                       check_diagnostic_storage, check_diagnostic_capture_integration)
from checks.results_identity import (check_identity_projection, check_identity_limits,
                                    check_identity_storage, check_identity_request_context,
                                    check_identity_capture_context, check_identity_repair_context, check_identity_shutdown)
from checks.results_request import (check_results_request_delivers,
                                    check_results_request_anything_wanted,
                                    check_results_request_only_when_taking,
                                    check_results_request_filter,
                                    check_results_request_gives_up,
                                    check_results_request_install,
                                    check_results_request_mode_message_types,
                                    check_results_request_names_the_type,
                                    check_results_request_no_channel,
                                    check_results_request_one_at_a_time,
                                    check_results_request_queue,
                                    check_results_request_refusals,
                                    check_results_request_stale,
                                    check_results_request_waits_for_the_garage)
from checks.service_hooks import (check_service_hooks, check_service_hooks_filter,
                                  check_service_signatures)
from checks.session import check_session_patches
from checks.settings_window import (check_settings_window, check_settings_window_api_variants,
                                    check_settings_window_labels, check_settings_window_live,
                                    check_settings_window_pending_pause,
                                    check_settings_window_without_api)
from checks.site_link import (check_site_link_gives_up, check_site_link_needs_an_account,
                              check_site_link_unlinks, check_site_link_url, check_site_link_verifies,
                              check_site_link_waiting, check_site_link_writes_the_destination,
                              check_site_link_startup)


def main():
    import imp
    import logging
    logging.basicConfig(level=logging.INFO,
                        format='       %(name)s: %(message)s')

    workdir = tempfile.mkdtemp(prefix='battle-conquest-selftest-')
    original_cwd = os.getcwd()
    try:
        # A copy, so a test run never writes .pyc into the checkout.
        src_root = os.path.join(workdir, 'src')
        shutil.copytree(os.path.join(REPO, 'src'), src_root)

        # The mod keeps its link and its queue relative to the client's working
        # directory. Running from a scratch one keeps a test run from reading or
        # writing anything under the checkout.
        os.chdir(workdir)

        bigworld = FakeBigWorld()
        service = install_fake_client(bigworld)
        stub = imp.load_source('mod_battle_conquest_dev', render_stub(workdir, src_root))

        def hooked():
            return FakeBattleResultsService.__dict__['postResult'] is not ORIGINAL_POST_RESULT

        def delegates():
            # Nothing readable in the result, so nothing is captured: what comes
            # back is exactly what the client's own method decided.
            return service.postResult(None) == 'the client answer'

        stub.init()
        check('load installed the hook', hooked())
        check('hook delegates to the original', delegates())
        check('watcher armed', bool(bigworld.pending))

        check_recovery_review_atomic_capacity()
        check_recovery_review_posted()
        check_recovery()
        check_receipts()
        check_owner_capture_write_failure()
        check_owner_enrichment_write_failure()
        check_legacy_unlink_race()
        check_legacy_unlink_restart()
        check_legacy_unlink_owner_scope()
        check_owner_unknown_notification()
        check_owner_isolated_receipt()
        check_owner_invalid_legacy_refresh()
        check_owner_settings_scope()
        check_owner_extraction()
        check_owner_lifecycle()
        check_owner_quarantine()
        check_owner_refusals()
        check_owner_migration()
        check_owner_requests()
        check_owner_storage()
        check_catalog_tester()
        check_session_patches()
        check_battle_feedback()
        check_battle_feedback_refresh()
        check_garage_finished_selection()
        check_battle_feedback_identity_callbacks()
        check_quest_garage()
        check_quest_garage_age()
        check_quest_garage_panel()
        check_quest_garage_input()
        check_garage_ready()
        check_sender_after_capture()
        check_report_sender_responses()
        check_quest_garage_scroll()
        check_quest_garage_theme()
        check_i18n()
        check_native_font()
        check_quest_garage_players()
        check_quest_garage_platoon()
        check_quest_details()
        check_quest_review()
        check_quest_repairs()
        check_battle_report_reading()
        check_battle_report_tank()
        check_battle_report_arena_id()
        check_battle_report_queue()
        check_battle_report_capture()
        check_battle_report_arrival()
        check_battle_report_arrival_as_method()
        check_battle_report_no_arrival()
        check_battle_report_hooks()
        check_identity_projection()
        check_identity_limits()
        check_identity_storage()
        check_identity_request_context()
        check_identity_capture_context()
        check_identity_repair_context()
        check_identity_shutdown()
        check_diagnostic_projection()
        check_diagnostic_bounded_values()
        check_diagnostic_storage()
        check_diagnostic_capture_integration()
        check_service_hooks()
        check_service_hooks_filter()
        check_service_signatures()
        check_site_link_url()
        check_site_link_waiting()
        check_site_link_writes_the_destination()
        check_site_link_needs_an_account()
        check_site_link_gives_up()
        check_site_link_unlinks()
        check_site_link_verifies()
        check_site_link_startup()
        check_mod_updates_contract()
        check_mod_updates_garage()
        check_mod_updates_teardown()
        check_results_dict_paths()
        check_results_dict_search()
        check_results_dict_cycle()
        check_results_dict_said_once()
        check_results_dict_miss()
        check_results_request_filter()
        check_results_request_mode_message_types()
        check_results_request_names_the_type()
        check_results_request_only_when_taking()
        check_results_request_anything_wanted()
        check_results_request_queue()
        check_results_request_one_at_a_time()
        check_results_request_waits_for_the_garage()
        check_results_request_delivers()
        check_results_request_refusals()
        check_results_request_gives_up()
        check_results_request_stale()
        check_results_request_install()
        check_results_request_no_channel()
        check_destination_urls()
        check_destination_modes()
        check_destination_reading()
        check_destination_secrets()
        check_destination_pause_and_forget()
        check_destination_silence()
        check_destination_capture()
        check_report_sender_targets()
        check_report_sender_payload()
        check_report_sender_delivery()
        check_report_sender_account()
        check_report_sender_refusals()
        check_report_sender_batching()
        check_report_sender_startup()
        check_report_sender_status()
        check_settings_window_labels()
        check_settings_window()
        check_settings_window_without_api()
        check_settings_window_live()
        check_settings_window_api_variants()
        check_settings_window_pending_pause()
        check_notices_texts()
        check_notices_remind()
        check_notices_click()
        check_notices_without_handler()
        check_notices_revoked_link()
        check_notices_dismiss_reminders()

        first_hook = FakeBattleResultsService.__dict__['postResult']
        generation_before = stub._generation

        # Touch a source file the way an editor would.
        edited = os.path.join(src_root, 'battle_conquest', 'battle_reports.py')
        os.utime(edited, (os.path.getatime(edited), os.path.getmtime(edited) + 10))

        bigworld.run_pending()
        check('reload happened', stub._generation == generation_before + 1)
        check('hook was reinstalled, not stacked',
              FakeBattleResultsService.__dict__['postResult'] is not first_hook)
        check('still delegates to the game original', delegates())

        bigworld.run_pending()
        check('watcher still running after reload', bool(bigworld.pending))

        # A reload with a broken file must not take the watcher down.
        with open(edited) as handle:
            intact = handle.read()
        with open(edited, 'a') as handle:
            handle.write('\nthis is not python\n')
        bigworld.run_pending()
        check('broken source leaves the original restored', not hooked())
        bigworld.run_pending()
        check('watcher survived the failed load', bool(bigworld.pending))

        # And the fix lands without a restart, which is the whole point.
        with open(edited, 'w') as handle:
            handle.write(intact)
        bigworld.run_pending()
        check('saving a fix recovers in place', hooked())

        stub.fini()
        check('fini leaves the game function untouched', not hooked())
        # Not `pending`: a response the fake client is still about to deliver
        # is its own, and the session's alive gate already makes it a no-op.
        check('fini cancelled every callback', not bigworld.scheduled)
        # Beside another mod's configs, not among them: a player running
        # Unicum too must find each mod's files in its own folder.
        from battle_conquest import config
        configs = os.path.join(workdir, 'mods', 'configs')
        written = os.listdir(configs) if os.path.isdir(configs) else []
        check('nothing is written outside the mod\'s own config folder',
              set(written) <= set([os.path.basename(config.CONFIG_DIR)]))

        print('\nall checks passed')
    finally:
        # Windows will not remove the directory a process is standing in.
        os.chdir(original_cwd)
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == '__main__':
    main()
