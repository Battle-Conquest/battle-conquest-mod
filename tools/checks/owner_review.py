"""Regression paths missed by the first owner-isolation delivery."""
import json
import os
import sys
import tempfile

from checks.battle_fixtures import ACCOUNT, Bonus, Player, owned
from checks.common import check
from checks.owner_isolation import fixture, raw, OTHER
from checks.report_sender import _Response, _answer, _sender


def check_owner_unknown_notification():
    from battle_conquest.results_request import Requests
    from checks.results_request import _Cache, _Clock, _Session
    player, places, queue, session, reports, sender = fixture()
    context = {'id': None, 'region': 'eu'}
    garage, cache, clock = [False], _Cache(), _Clock()
    requests = Requests(_Session(),
                        lambda result, source, origin: reports.capture(result, constants=Bonus,
                                                                       request_context=origin),
                        garage=lambda: garage[0], cache=lambda: cache,
                        context=lambda: context, now=clock)
    requests.remember(91)
    requests.drain()
    check('an avatar announcement waits for the garage', not cache.asked)
    context['id'], garage[0] = ACCOUNT, True
    requests.drain()
    check('an announcement without login metadata is retrieved when the garage identifies the login', cache.asked == [91])
    player.account = OTHER
    context['id'] = OTHER
    cache.answer_now(91, 1, raw())
    check('the fetched result retains its actual request owner across a later login switch',
          queue.all()[0]['account'] == ACCOUNT and queue.all()[0]['request_owner']['id'] == ACCOUNT)
    requests.remember(92)
    cache._answers[92] = (-5, None)
    requests.drain()
    context['id'] = ACCOUNT
    clock.now += 21
    requests.drain()
    check('a retry never borrows another login after its first scoped request', cache.asked == [91, 92])
    # Another formerly unknown announcement can be fetched under A, but a
    # conflicting B personal result must still be isolated, never stamped A.
    context['id'] = None
    requests.remember(93)
    context['id'] = ACCOUNT
    requests.drain()
    cache.answer_now(93, 1, raw(OTHER, arena=93))
    check('retrieving an unscoped announcement does not bypass result ownership checks',
          queue.isolated() == 1 and not any(r.get('account') == OTHER for r in queue.all()))


def check_owner_isolated_receipt():
    from battle_conquest.report_queue import Queue
    path = os.path.join(tempfile.mkdtemp(), 'queue')
    malformed = {'account': {}, 'arena_unique_id': [], 'mode': 'ranked'}
    with open(path, 'wb') as handle:
        json.dump({'schema': 1, 'reports': [malformed]}, handle)
    queue = Queue(store=path)
    queue.add(owned({'arena_unique_id': '91', 'mode': 'ranked',
                     'finished_at': '2026-10-29T17:00:00Z', 'outcome': 'win',
                     'survived': True, 'metrics': {'xp': 10}}))
    session, sender = _sender(queue)
    sender.drain()
    _answer(session, 200, {'results': [{'index': 0, 'status': 'accepted'}]})
    check('an isolated structured arena cannot stall valid delivery acknowledgements',
          not sender._busy and queue.isolated() == 1 and len(queue.all()) == 1)
    queue.add(owned({'arena_unique_id': '92', 'mode': 'ranked'}))
    queue.drop(['92'], account=ACCOUNT)
    check('explicit owner deletion leaves malformed isolated history untouched',
          len(queue.all()) == 1 and queue.all()[0]['arena_unique_id'] == [])
    check('the isolated history and completed acknowledgement survive restart',
          Queue(store=path).all() == queue.all())


def check_owner_invalid_legacy_refresh():
    from battle_conquest.destinations import Destinations, battles_url
    from battle_conquest.site_link import SiteLink
    from checks.site_link import _Session
    path = os.path.join(tempfile.mkdtemp(), 'links')
    with open(path, 'wb') as handle:
        json.dump({'schema': 1, 'url': battles_url(), 'secret': 'invalid',
                   'modes': ['ranked'], 'enabled': True}, handle)
    player = Player()
    places = Destinations(('ranked', 'random'), store=path, account=player)
    places.remember('BC', ['ranked'], 'a' * 64)
    session = _Session()
    site = SiteLink(session, places, player)
    site.verify()
    check('an unusable legacy key cannot shadow the verified current link',
          len(session.sent) == 1 and session.sent[-1]['headers']['X-Mod-Secret'] == 'a' * 64)
    session.sent.pop()['answer'](_Response(200, {'account_id': ACCOUNT, 'region': 'eu',
                                               'modes': ['ranked', 'random']}))
    check('the replacement link still refreshes server preferences', places.current.modes == ['ranked', 'random'])
    site.verify()
    session.sent.pop()['answer'](_Response(401))
    check('the replacement link still follows revocation', not site.linked)


def check_owner_settings_scope():
    from battle_conquest.settings_window import LINKAGE, UNLINK_VAR, SettingsWindow
    from checks.settings_window import _install_api, _Site, _Session
    previous = sys.modules.get('gui.modsSettingsApi')
    api = _install_api()
    player, places, queue, unused, reports, sender = fixture()
    places.current.modes = ['ranked']
    places.for_owner(('eu', OTHER)).modes = ['ranked']
    site, session = _Site(places), _Session()
    window = SettingsWindow(session, site, places)
    try:
        window.install()
        api.open()
        old_apply, old_button, old_live = (api.onSettingsChanged.handlers[0],
                                         api.onButtonClicked.handlers[0], api.live[0])
        api.toggle(False)
        player.account = OTHER
        old_apply(LINKAGE, {'enabled': False})
        check('an Apply callback racing the account poll cannot modify B from the A page', places.enabled)
        site.changed()
        session.run_later()
        check('same-looking account settings still discard the former account preview',
              api.visible['enabled'] is True and places.enabled and window._preview_enabled is None)
        old_live(LINKAGE, {'enabled': False})
        old_button(LINKAGE, UNLINK_VAR)
        check('old live edits and Unlink callbacks cannot affect B', places.enabled and places.linked)
        player.account = ACCOUNT
        site.changed()
        session.run_later()
        old_apply(LINKAGE, {'enabled': False})
        old_button(LINKAGE, UNLINK_VAR)
        check('returning to A cannot revive its obsolete callbacks', places.enabled and places.linked)
        api.toggle(False)
        api.onSettingsChanged.handlers[0](LINKAGE, {'enabled': False})
        session.run_later()
        check('current account settings remain editable', not places.enabled)
        api.toggle(True)
        old_apply = api.onSettingsChanged.handlers[0]
        places.remember('BC', ['ranked'], 'c' * 64, enabled=False)
        site.changed()
        session.run_later()
        old_apply(LINKAGE, {'enabled': True})
        check('a renewed proof discards old previews and cannot be changed by old callbacks',
              not places.enabled and api.visible['enabled'] is False)
    finally:
        window._remove()
        if previous is None:
            sys.modules.pop('gui.modsSettingsApi', None)
        else:
            sys.modules['gui.modsSettingsApi'] = previous
    check('scoped settings handlers are all detached on stop',
          not api.live and not api.onSettingsChanged.handlers and not api.onButtonClicked.handlers)
