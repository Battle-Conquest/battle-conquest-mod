"""Display isolation, command ownership, Gameface lifecycle and shared selection."""
import copy
import json
import os
import sys
import tempfile
import types

from checks.common import check
from checks.engine import FakeEvent
from checks.report_sender import _Session, _Response


def check_garage_displays():
    from battle_conquest import garage_display, i18n
    from battle_conquest.display_preferences import Preferences
    from battle_conquest.destinations import Destination, battles_url
    from battle_conquest.quest_garage import Garage

    store = os.path.join(tempfile.mkdtemp(), 'display.json')
    preferences = Preferences(store)
    check('first use shows only the integrated card', preferences.get('123') == {'widget': True, 'details': False})
    preferences.set('123', 'widget', False)
    preferences.set('123', 'details', True)
    reloaded = Preferences(store)
    check('switches survive restart independently', reloaded.get('123') == {'widget': False, 'details': True})
    check('another account retains its own display switches', reloaded.get('456') == {'widget': True, 'details': False})
    session = _Session()
    session.alive = True
    account = type('Account', (object,), {'account': '123'})()
    destination = Destination(battles_url(), enabled=True, modes=['random'], secret='a' * 64)
    places = type('Places', (object,), {'current': destination, 'linked': True})()
    actions = []
    site = type('Site', (object,), {'running': False, 'start': lambda self: actions.append('link'),
                                   'unlink': lambda self: actions.append('cancel')})()
    class Panel(object):
        editing = None
        def reset(self): pass
        def render(self, garage): pass
        def visible(self, shown, preserve_draft=False): self.shown = shown
        def close(self): self.closed = True
    clock = [100.0]
    display = garage_display.Displays(session, account, places, site, Panel(), preferences, lambda: clock[0])
    garage = Garage(session, account, places, display, garage=lambda: True, ready=lambda: True, platoon=lambda: [], now=lambda: clock[0])
    standing = garage_display.at_garage, garage_display.garage_ready
    garage_display.at_garage = garage_display.garage_ready = lambda: True
    try:
        garage.tick()
        scope = display.scope
        display.command({'scope': scope, 'action': 'link'})
        check('the card reuses the existing link service', actions == ['link'])
        account.account = '456'
        display.command({'scope': scope, 'action': 'link'})
        check('a delayed old-account command cannot start linking', actions == ['link'])
        garage.tick()
        display.command({'scope': display.scope, 'action': 'details'})
        check('Details persists its own switch for the current account', preferences.get('456')['details'])
        display.panel.dismiss()
        check('the detailed cross clears only its own switch', preferences.get('456') == {'widget': True, 'details': False})
        display.switch('widget', False)
        display.switch('widget', True)
        clock[0] = 109
        check('missing Gameface enables a session fallback', display.fallback(True))
        check('fallback never writes either display preference', preferences.get('456') == {'widget': True, 'details': False})
        garage.data = {'config': {'version': 1, 'selection': '', 'mode': 'manual', 'manual_ids': []}, 'players': []}
        garage.tick()
        check('fallback opens the detailed window while the card is unavailable', display.panel.shown)
        display.panel.dismiss()
        garage.tick()
        check('the fallback window stays closed after its cross is clicked', not display.panel.shown)
        display.switch('widget', True)
        display.switch('details', False)
        check('applying unchanged switches cannot resurrect a dismissed fallback', not display.panel.shown)
        display.switch('details', True)
        check('the notification can restore a dismissed fallback window', display.panel.shown)
        garage.data = {'criteria': [{'criterion_type': 'damage_dealt', 'label': 'Damage', 'target_value': 100}],
            'players': [{'username': 'Self', 'official': {'available': True, 'totals': {'damage_dealt': None},
                                                        'known_totals': {'damage_dealt': 20}, 'incomplete': True}},
                        {'username': 'Other', 'official': {'available': True, 'totals': {'damage_dealt': 999}}}]}
        snapshot = display.snapshot(True)
        check('partial scores remain explicitly unknown', snapshot['criteria'][0]['values']['official'] == '20 + ?')
        check('missing estimates stay unavailable', snapshot['criteria'][0]['values']['estimate'] == 'Unavailable')
        check('Gameface never receives secrets or followed players', 'Other' not in json.dumps(snapshot) and destination.secret not in json.dumps(snapshot))
        check('French catalogue covers the card controls', all(label in i18n.MESSAGES for label in garage_display.LABELS))
        display.command({'scope': display.scope, 'action': 'close'})
        check('closing the card persists only that account switch', not preferences.get('456')['widget'] and preferences.get('123')['details'])
    finally:
        garage_display.at_garage, garage_display.garage_ready = standing


def check_garage_auto_selection():
    from battle_conquest.quest_garage import Garage
    from battle_conquest.destinations import Destination, battles_url
    session = _Session()
    account = type('Account', (object,), {'account': '123'})()
    places = type('Places', (object,), {'current': Destination(battles_url(), enabled=True, modes=['random'], secret='a' * 64)})()
    class View(object):
        editing = None
        def visible(self, value, **kwargs): pass
        def reset(self): pass
        def render(self, garage): pass
    view = View()
    garage = Garage(session, account, places, view, garage=lambda: True, ready=lambda: True, platoon=lambda: [])
    garage.key = garage.identity()
    data = {'schema': 1, 'config': {'version': 3, 'selection': '', 'mode': 'manual', 'manual_ids': [2]},
            'automatic_selection': 'individual:1', 'choices': [], 'selected': None, 'players': []}
    garage.data = copy.deepcopy(data)
    garage.auto_select()
    request = session.sent.pop()
    check('automatic selection uses the authenticated versioned POST',
          '/auto-select?' in request['url'] and request['body'] == {'version': 3})
    data['config'].update(version=4, selection='individual:1')
    request['answer'](_Response(200, data))
    garage.auto_select()
    check('acknowledged automatic choices do not loop', not session.sent and garage.data['config']['version'] == 4)
    garage.data['config']['selection'] = ''
    view.editing = 'draft'
    garage.auto_select()
    check('automatic writes never interrupt the detailed editor draft', not session.sent)
    view.editing = None
    garage.auto_select()
    session.sent.pop()['answer'](_Response(409, {'error': 'conflict'}))
    check('automatic selection conflicts preserve the observed configuration', garage.conflict and garage.data['config']['selection'] == '')
    garage.conflict = False
    previous = copy.deepcopy(garage.data)
    garage.auto_select()
    changed = copy.deepcopy(garage.data)
    changed['config'].update(version=5, selection='individual:1', manual_ids=[3])
    session.sent.pop()['answer'](_Response(200, changed))
    check('automatic acknowledgements cannot adopt another client list update', garage.conflict and garage.data == previous)

    garage.conflict = False
    data['config'].update(version=5, selection='session:2')
    data.update(automatic_selection=None,
                choices=[{'key': 'individual:1', 'title': 'Active', 'status': 'active'},
                         {'key': 'session:2', 'title': 'Finished', 'status': 'settled'}],
                selected={'key': 'session:2', 'title': 'Finished', 'status': 'settled'},
                criteria=[{'criterion_type': 'damage_dealt', 'target_value': 100}],
                players=[{'username': 'Self', 'participant': True,
                          'official': {'available': True, 'totals': {'damage_dealt': 75}, 'battles': 2}}])
    garage.data = copy.deepcopy(data)
    garage.save(selection='individual:1')
    request = session.sent.pop()
    saved = copy.deepcopy(data)
    saved['config'].update(version=6, selection='individual:1')
    saved['selected'] = saved['choices'][0]
    request['answer'](_Response(200, saved))
    garage.next_quest()
    request = session.sent.pop()
    check('the detailed selector can choose the finished result beside an active quest',
          request['body']['selection'] == 'session:2')
    data['config']['version'] = 7
    request['answer'](_Response(200, data))
    garage.auto_select()
    check('the acknowledged result keeps its own official statistics without an automatic write',
          garage.data['selected']['key'] == 'session:2'
          and garage.data['players'][0]['official']['totals']['damage_dealt'] == 75 and not session.sent)
    restarted = Garage(session, account, places, View(), garage=lambda: True, ready=lambda: True, platoon=lambda: [])
    restarted.key = restarted.identity()
    restarted.poll(force=True)
    session.sent.pop()['answer'](_Response(200, data))
    restarted.auto_select()
    check('a new garage instance restores the server choice and final statistics',
          restarted.data == data and not session.sent)


def check_garage_gameface():
    from battle_conquest.hangar_inject import Bridge, REGISTRY
    from battle_conquest.runtime.session import Session
    names = ('openwg_gameface', 'frameworks.wulf', 'gui.impl.lobby.hangar.presenters.vehicle_menu_presenter', 'gui.impl.pub.view_component')
    modules = set(names)
    for name in names:
        parts = name.split('.')
        modules.update('.'.join(parts[:index]) for index in range(1, len(parts)))
    standing = dict((name, sys.modules.get(name)) for name in modules)
    class Model(object):
        def __init__(self, properties, commands): self.values = []
        def _initialize(self): pass
        def _addNumberProperty(self, name, value): self.values.append(value)
        _addStringProperty = _addNumberProperty
        def _addCommand(self, name): return FakeEvent()
        def _setString(self, index, value): self.values[index] = value
        _setNumber = _setString
    class View(object):
        def __init__(self, layoutID, model):
            self.model = model()
            self.model._initialize()
        def getViewModel(self): return self.model
    class Presenter(object):
        def _getChildComponents(self): return {1: 'native'}
    original = Presenter.__dict__['_getChildComponents']
    try:
        for name in sorted(modules, key=lambda value: len(value.split('.'))):
            module = types.ModuleType(name)
            module.__path__ = []
            sys.modules[name] = module
            if '.' in name:
                parent, child = name.rsplit('.', 1)
                setattr(sys.modules[parent], child, module)
        sys.modules[names[0]].gf_mod_inject = lambda model, feature, modules: model.values.append('inject')
        sys.modules[names[0]].res_id_by_key = lambda feature: 42
        sys.modules[names[1]].ViewModel = Model
        sys.modules[names[2]].VehicleMenuPresenter = Presenter
        sys.modules[names[3]].ViewComponent = View
        session = Session(1047)
        bridge = Bridge(session, now=lambda: 100)
        bridge.install()
        check('optional Gameface installs a distinct owned child', bridge.installed and 42 in Presenter()._getChildComponents())
        view = Presenter()._getChildComponents()[42]()
        model = view.getViewModel()
        bridge.publish({'scope': 'a', 'shown': True})
        check('view model resource and state indexes agree with its schema',
              len(model.values) == 5 and model.values[1] == bridge.revision and json.loads(model.values[4])['scope'] == 'a')
        bridge.received('a')
        check('only the current display scope acknowledges rendering', bridge.healthy('a') and not bridge.healthy('b'))
        from battle_conquest import hangar_inject
        original_read = hangar_inject.read
        try:
            def missing(name): raise IOError('resource temporarily replaced by editor')
            hangar_inject.read = missing
            bridge.refresh()
            check('a transient resource read keeps an already running card healthy', bridge.healthy('a'))
            another = bridge.make_view().getViewModel()
            setter = model._setString
            def disposed(index, value): raise RuntimeError('disposed native model')
            model._setString = disposed
            bridge.models = lambda: [model, another]
            hangar_inject.read = lambda name: original_read(name) + '\n'
            bridge.refresh()
            check('a disposed model cannot prevent live cards from receiving edited resources', another.values[1] == bridge.revision)
            model._setString = setter
            del bridge.models
        finally:
            hangar_inject.read = original_read
        bridge.close()
        session.close()
        check('teardown stops JavaScript and restores the original presenter',
              model.values[1] == 0 and Presenter.__dict__['_getChildComponents'] is original)
        session = Session(1048)
        bridge = Bridge(session)
        bridge.install()
        check('reload adopts live models without stacking a second child', len(getattr(Presenter, REGISTRY)) == 2)
        bridge.close()
        session.close()
    finally:
        for name, value in standing.items():
            if value is None: sys.modules.pop(name, None)
            else: sys.modules[name] = value


def check_garage_settings():
    from checks.settings_window import _install_api, _Session as SettingsSession, _Site, _places
    from battle_conquest.settings_window import SettingsWindow, LINKAGE
    api = _install_api()
    class Displays(object):
        def __init__(self): self.values = {'widget': True, 'details': False}
        def switches(self): return dict(self.values)
        def switch(self, name, value): self.values[name] = value
    display = Displays()
    places = _places()
    site = _Site(places)
    session = SettingsSession()
    window = SettingsWindow(session, site, places, displays=display)
    try:
        window.install()
        api.open()
        def value(name):
            return next(row['value'] for row in api.visible['column1'] if row.get('varName') == name)
        check('settings expose two independent real checkbox controls', value('widget') and not value('details'))
        window._on_live_window(LINKAGE, {'widget': False, 'details': True})
        site.start()
        session.run_later()
        check('status redraw preserves pending display switches without applying them',
              not value('widget') and value('details') and display.values == {'widget': True, 'details': False})
        window._on_window(LINKAGE, {'widget': False, 'details': True})
        check('Apply persists only the display controls independently of sending', display.values == {'widget': False, 'details': True} and not places.linked)
        window._on_live_window(LINKAGE, {'widget': True})
        api.close()
        api.open()
        check('Cancel discards pending display changes', not value('widget'))
    finally:
        window._remove()
        sys.modules.pop('gui.modsSettingsApi', None)
