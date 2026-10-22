"""Server compatibility, version sources, garage timing and session teardown."""
from checks.common import check
from checks.site_link import _Response, _Session, _Link, _destinations


def _update(wg='1.1.0', github='1.2.0', target='1.2.0'):
    return {'installed_version': '1.0.0', 'wgmods_version': wg,
            'github_version': github, 'target_version': target,
            'recommended_source': 'wgmods' if wg else 'github'}


def _response(update):
    return _Response(200, {'label': 'Battle-Conquest', 'modes': ['random'], 'mod_update': update})


def check_mod_updates_contract():
    from battle_conquest import mod_updates
    from battle_conquest.site_link import SiteLink
    from battle_conquest.settings_window import SettingsWindow, template
    from checks.settings_window import _Templates

    check('an old server has no optional update information',
          mod_updates.read(_Response(200, {'modes': ['random']}), '1.0.0') is None)
    check('zero-padded numeric components are canonical',
          mod_updates.version('v01.002.000') == '1.2.0' and mod_updates.version('00.000.0') == '0.0.0')
    for wg, gh, target in (('1.02.0', '1.2.0', '1.2.0'), ('1.2.0', '1.02.0', '1.02.0')):
        padded = mod_updates.read(_response(_update(wg, gh, target)), '01.00.000')
        check('equivalent source spellings cannot hide an update',
              padded is not None and padded['target_version'] == '1.2.0'
              and padded['recommended_source'] == 'wgmods')
    for raw in (None, [], 'bad', {'target_version': '<a>evil</a>'}):
        check('an invalid extension is harmless', mod_updates.read(_response(raw), '1.0.0') is None)
    for wg, gh, target, source in (('1.1.0', '1.2.0', '1.2.0', 'wgmods'),
                                    (None, '1.2.0', '1.2.0', 'github'),
                                    ('1.10.0', None, '1.10.0', 'wgmods'),
                                    ('1.0.0', '1.0.0', None, None)):
        status = mod_updates.read(_response(_update(wg, gh, target)), '1.0.0')
        check('stable sources determine target and recommended source',
              status['target_version'] == target and status['recommended_source'] == source)
    check('a future installed version never alerts',
          mod_updates.read(_response(_update(target=None)), '9.0.0')['target_version'] is None)
    check('unknown installed versions cannot raise an alert',
          mod_updates.read(_response(_update()), 'dev') is None)
    check('a bogus target is refused',
          mod_updates.read(_response(_update(target='9.0.0')), '1.0.0') is None)
    check('markup in source versions never enters the UI',
          '<script>' not in mod_updates.text(mod_updates.read(
              _response(_update(wg='<script>', target='1.2.0')), '1.0.0'), '1.0.0'))
    unreadable = _Response(200)
    unreadable.body = '<html>unavailable</html>'
    check('HTML from a broken proxy cannot break linking', mod_updates.read(unreadable, '1.0.0') is None)

    places = _destinations()
    places.remember('Battle-Conquest', ['random'], 'a' * 64, enabled=False)
    session = _Session()
    sites = SiteLink(session, places, _Link(), site='https://example.test', version='1.0.0')
    sites.install()
    check('verification runs at startup and every thirty minutes',
          session.callbacks[0][0] == 0.0 and len(session.repeats) == 2)
    # The fake stores the periodic callback; record its actual interval too.
    intervals = []
    session.repeat = lambda seconds, func: intervals.append(seconds)
    sites.install()
    check('periodic verification uses 1800 seconds', intervals == [1800.0])
    sites.verify()
    check('paused sending still asks for updates with the installed version',
          session.sent[-1]['headers']['X-Mod-Version'] == '1.0.0' and not places.enabled)
    session.sent[-1]['answer'](_response(_update()))
    check('the response is retained for both UIs', sites.mod_update['target_version'] == '1.2.0')
    page = template(SettingsWindow(session, sites, places).state(), _Templates)
    text = ' '.join(item.get('text', '') for item in page['column2'])
    check('optional settings name installed and both sources with recommendation',
          all(part in text for part in ('1.0.0', 'WGMods 1.1.0', 'GitHub 1.2.0', 'Recommended download: WGMods')))
    sites.verify()
    session.sent[-1]['answer'](_Response(200, {'modes': ['random']}))
    check('an old server still leaves the account linked', places.linked and sites.mod_update is None)
    sites.verify()
    sites.unlink()
    session.sent[-1]['answer'](_response(_update()))
    check('a response after unlinking cannot restore an update', sites.mod_update is None)
    from battle_conquest import site_link
    original = site_link.open_url
    site_link.open_url = lambda url: None
    try:
        sites.start()
        sites._attempt._answered(_response(_update()))
        check('a fresh linking response supplies update information immediately',
              sites.linked and sites.mod_update['target_version'] == '1.2.0')
    finally:
        site_link.open_url = original


def check_mod_updates_garage():
    from battle_conquest import mod_updates, site_link
    from battle_conquest.notices import Notices
    from checks.notices import _Account, _Site, _Session, _Handlers, _with_handlers, _places

    _with_handlers(True)
    session = _Session()
    places = _places()
    places.remember('Battle-Conquest', ['random'], 'a' * 64)
    site = _Site(places)
    site.page = 'https://example.test/my-mod'
    site.mod_update = None
    garage = [False]
    pushed = []
    notices = Notices(session, site, places, _Account(), garage=lambda: garage[0],
                      push=lambda text, warning=False: pushed.append((text, warning)) or True)
    notices.install()
    try:
        site.mod_update = mod_updates.read(_response(_update()), '1.0.0')
        site.changed()
        site.changed()
        check('duplicate responses coalesce into one pending garage callback', len(session.later) == 1)
        session.run_later()
        check('updates wait while the garage is unavailable', not pushed and len(session.later) == 1)
        garage[0] = True
        push = notices._push
        notices._push = lambda text, warning=False: False
        session.run_later()
        check('a garage whose notification centre is not ready is retried',
              not pushed and len(session.later) == 1)
        notices._push = push
        session.run_later()
        check('the deferred warning names versions and opens the update action',
              len(pushed) == 1 and pushed[0][1] and '1.0.0' in pushed[0][0]
              and 'event:' + mod_updates.ACTION in pushed[0][0])
        site.changed()
        session.run_later()
        check('the same target is announced only once this session', len(pushed) == 1)
        site.mod_update = mod_updates.read(_response(_update('01.01.000', '01.02.000', '01.02.000')), '1.0.0')
        site.changed()
        session.run_later()
        check('another numeric spelling does not rearm the same target', len(pushed) == 1)
        site.mod_update = mod_updates.read(_response(_update(github='1.3.0', target='1.3.0')), '1.0.0')
        site.changed()
        session.run_later()
        check('a newer target is announced in the same session', len(pushed) == 2 and '1.3.0' in pushed[-1][0])
        opened = []
        original = site_link.open_url
        site_link.open_url = opened.append
        try:
            _Handlers().handleAction(None, 1, 2, mod_updates.ACTION)
            check('click opens my-mod in the external browser', opened == [site.page])
        finally:
            site_link.open_url = original
    finally:
        session.real.close()


def check_mod_updates_teardown():
    from battle_conquest import mod_updates
    from battle_conquest.notices import Notices
    from battle_conquest.runtime import session as runtime
    from checks.engine import FakeBigWorld
    from checks.notices import _Account, _Site, _places, _with_handlers

    original = runtime.BigWorld
    engine = FakeBigWorld()
    runtime.BigWorld = engine
    session = runtime.Session(0)
    _with_handlers(True)
    pushed = []
    places = _places()
    site = _Site(places)
    site.mod_update = mod_updates.read(_response(_update()), '1.0.0')
    try:
        Notices(session, site, places, _Account(), garage=lambda: True,
                push=lambda *args, **kwargs: pushed.append(args) or True).install()
        pending = list(engine.pending.values())
        session.fetch('https://example.test/api/mod/me', lambda response: pushed.append('late response'))
        session.close()
        for callback in pending:
            callback()
        engine.run_pending()
        check('closing cancels garage callbacks and gates in-flight responses', not pushed and not engine.scheduled)
    finally:
        session.close()
        runtime.BigWorld = original
