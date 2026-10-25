# -*- coding: utf-8 -*-
"""Authenticated language changes, native layout, drafts and account isolation."""
import copy
import os
import re
import sys

from checks.common import check
from checks.native_gui import native_gui
from checks.report_sender import _Session, _Response
from checks.settings_window import _Templates


def check_i18n():
    from battle_conquest import i18n, settings_window, notices, mod_updates
    from battle_conquest.destinations import Destination, battles_url
    from battle_conquest.quest_garage import Garage
    from battle_conquest.quest_garage_view import Panel
    from battle_conquest.runtime.session import Session
    from battle_conquest.site_link import SiteLink
    from battle_conquest.translations_fr import MESSAGES

    # Placeholders must survive translation before any UI tries formatting.
    for english, french in MESSAGES.items():
        check('French placeholders match: ' + english[:50],
              re.findall(r'%[sd]', english) == re.findall(r'%[sd]', french))
    gui, roots, resolution, cursor, node, modes = native_gui()
    previous = sys.modules.get('GUI')
    sys.modules['GUI'] = gui
    session = Session(958)
    account = type('Account', (object,), {'account': '500883375'})()
    destination = Destination(battles_url(), secret='a' * 64, modes=['random'], enabled=True)
    places = type('Places', (object,), {'current': destination})()
    i18n.install(session, account, places)
    panel = Panel(None, store=os.path.join(os.getcwd(), 'language-panel.json'))
    try:
        panel.visible(True)
        transport = _Session()
        garage = Garage(transport, account, places, panel, garage=lambda: True, platoon=lambda: [], now=lambda: 100.0)
        garage.key = garage.identity()
        data = {'schema': 1, 'language': 'fr', 'account_id': account.account,
                'config': {'version': 1, 'selection': 'individual:1', 'mode': 'manual', 'manual_ids': [2]},
                'choices': [], 'selected': {'title': 'Reload'},
                'criteria': [{'criterion_type': 'damage_dealt', 'target_value': 1000, 'label': u'Dégâts infligés'}],
                'players': [{'username': 'Save', 'participant': True,
                             'official': {'available': True, 'battles': 3, 'totals': {'damage_dealt': 350}}}]}
        garage.poll(force=True)
        transport.sent.pop(0)['answer'](_Response(200, copy.deepcopy(data)))
        def texts(component):
            result = [] if component.window else [component.text]
            for name, child in component.children:
                result.extend(texts(child))
            return result
        check('a garage refresh adopts the authenticated site language without relinking', i18n.locale() == 'fr')
        check('French captions, source labels and server criterion names render in the native window',
              panel.button_labels[0].text == u'Quête suivante' and panel.fold_label.text == u'Replier'
              and u'OFFICIEL | 3 batailles' in texts(panel.content.node)
              and u'Dégâts infligés: 350 / 1 000' in texts(panel.content.node))
        check('quest titles and usernames are never translated as interface messages',
              'Reload' in texts(panel.content.node) and 'Save' in texts(panel.content.node))
        for width, height in ((1280, 720), (1920, 1080), (2560, 1440)):
            resolution[:] = width, height
            panel.render(garage)
            check('French buttons remain readable in %sx%s' % (width, height),
                  all(not caption.clipped() for caption in panel.button_labels) and not panel.fold_label.clipped())
        panel.edit()
        panel.editing = u'2,3'
        before = (panel.editing, panel.edit_version, garage.data['config']['version'])
        english = copy.deepcopy(data)
        english.update(language='en')
        english['criteria'][0]['label'] = 'Damage dealt'
        garage.poll(force=True)
        transport.sent.pop(0)['answer'](_Response(200, english))
        check('switching to English preserves the open draft and its version',
              i18n.locale() == 'en' and panel.button_labels[0].text == 'Save'
              and (panel.editing, panel.edit_version, garage.data['config']['version']) == before)
        site = SiteLink(transport, places, account, version='1.2.0')
        site.verify()
        transport.sent.pop(0)['answer'](_Response(200, {'modes': ['random'], 'language': 'fr', 'account_id': account.account}))
        check('/api/mod/me also applies the linked account language', i18n.locale() == 'fr')
        page = settings_window.template(settings_window.State(linked=True, modes=['random']), _Templates)
        from battle_conquest.modes import MODES
        check('every supported battle mode has a French display name without changing wire IDs',
              all(mode in MESSAGES for mode in MODES) and u'Bastion' in settings_window.modes_label(MODES, True))
        check('optional settings and notifications use French too',
              page['column1'][1]['button']['text'] == u'Délier'
              and u'Compte : lié' == page['column1'][1]['text']
              and u'Lier mon compte' in notices.not_linked_text(True, False)
              and u'Version du mod' in mod_updates.text(None, '1.2.0'))
        for malformed in ({}, {'language': ['fr']}, {'language': 'de'}, {'language': '<script>'}):
            payload = dict(malformed, account_id=account.account)
            i18n.accept(payload, account.account, destination.secret)
        check('old servers and malformed preferences retain the last valid language', i18n.locale() == 'fr')
        garage.poll(force=True)
        transport.sent.pop(0)['answer'](_Response(503, english))
        check('network failure retains the language and translates the offline editor status',
              i18n.locale() == 'fr' and u'Hors ligne' in panel.subtitle.text and panel.editing == u'2,3')
        garage.poll(force=True)
        delayed = transport.sent.pop(0)['answer']
        account.account = '500999999'
        check('switching game accounts clears the previous language immediately', i18n.locale() == 'en')
        delayed(_Response(200, data))
        check('an old account response cannot restore its language', i18n.locale() == 'en')
        check('a preference bound to another WG account is rejected', not i18n.accept(data, account.account, destination.secret))
        current = dict(data, account_id=account.account)
        i18n.accept(current, account.account, destination.secret)
        destination.secret = 'b' * 64
        check('relinking clears cached language until the new secret is authenticated', i18n.locale() == 'en')
        check('a delayed old-link preference is rejected', not i18n.accept(current, account.account, 'a' * 64))
        i18n.accept(current, account.account, destination.secret)
        check('the new account/link can acquire its own preference', i18n.locale() == 'fr')
    finally:
        panel.close()
        session.close()
        if previous is None:
            del sys.modules['GUI']
        else:
            sys.modules['GUI'] = previous
    check('teardown returns language to its fallback and leaves no GUI root or listeners',
          i18n.locale() == 'en' and not roots and not i18n._listeners)
