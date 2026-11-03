"""Optional Gameface adapter; its failure never stops battle capture or sending."""
import functools
import json
import logging
import time
import weakref
import zlib

from battle_conquest.hangar_resources import read

_logger = logging.getLogger('battle_conquest.hangar_inject')
FEATURE = 'BattleConquestGarage'
LAYOUT = 'R.mods.battle_conquest.Garage.views.BattleConquestGarage'
REGISTRY = '_battleConquestGarageModels'
MODULE = 'coui://gui/gameface/mods/battle_conquest/Garage/Garage.js'
_COMMAND = functools.partial(eval, "__import__('battle_conquest.garage_display', None, None, ['on_item']).on_item(locals())", {})


def layout_id():
    try:
        from gui.impl.gen import R
        node = R
        for name in LAYOUT.split('.')[1:]:
            node = getattr(node, name)
        found = node()
        if found != -1:
            return found
    except (ImportError, AttributeError, TypeError):
        pass
    from openwg_gameface import res_id_by_key
    found = res_id_by_key(FEATURE)
    return found if found != -1 else None


def model_type():
    from frameworks.wulf import ViewModel

    class Model(ViewModel):
        __slots__ = ('onAction',)

        def __init__(self):
            super(Model, self).__init__(properties=5, commands=1)

        def _initialize(self):
            super(Model, self)._initialize()
            from openwg_gameface import gf_mod_inject
            gf_mod_inject(self, FEATURE, modules=[MODULE])
            self._addNumberProperty('revision', 0)
            self._addStringProperty('script', '')
            self._addStringProperty('style', '')
            self._addStringProperty('snapshot', '')
            self.onAction = self._addCommand('onAction')
    return Model


class Bridge(object):
    def __init__(self, session, now=time.time):
        self.session, self.now = session, now
        self.installed = False
        self.presenter = None
        self.last_scope, self.last_seen = None, 0
        self.payload = '{}'
        self.sources = None
        self.revision = 0

    def models(self):
        return list(getattr(self.presenter, REGISTRY, ()))

    def install(self):
        try:
            import openwg_gameface
            from gui.impl.lobby.hangar.presenters.vehicle_menu_presenter import VehicleMenuPresenter
            self.layout = layout_id()
            if self.layout is None:
                raise RuntimeError('garage layout not registered; restart the client')
            self.presenter = VehicleMenuPresenter
            if not hasattr(self.presenter, REGISTRY):
                setattr(self.presenter, REGISTRY, weakref.WeakSet())
            self.refresh()
            if self.sources is None:
                raise RuntimeError('garage UI resources unavailable')
            self.session.patch(self.presenter, '_getChildComponents', self.wrap)
            self.installed = True
        except Exception:
            _logger.warning('Gameface garage card unavailable', exc_info=True)

    def wrap(self, original):
        def children(presenter):
            result = dict(original(presenter))
            result[self.layout] = self.make_view
            return result
        return children

    def make_view(self):
        from gui.impl.pub.view_component import ViewComponent
        view = ViewComponent(layoutID=self.layout, model=model_type())
        model = view.getViewModel()
        model.onAction += _COMMAND
        getattr(self.presenter, REGISTRY).add(model)
        self.load(model)
        return view

    def refresh(self):
        try:
            script = read('web/hangar/garage.js')
            style = read('web/hangar/garage.css')
            if (script, style) == self.sources:
                return
            self.sources = (script, style)
            self.revision = (zlib.crc32((script + style).encode('utf-8')) & 0x3fffffff) or 1
            for model in self.models():
                self.load(model)
        except Exception:
            self.installed = False
            _logger.exception('could not load garage card resources')

    def load(self, model):
        model._setString(2, self.sources[0])
        model._setString(3, self.sources[1])
        model._setString(4, self.payload)
        model._setNumber(1, self.revision)

    def publish(self, payload):
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        if encoded == self.payload:
            return
        self.payload = encoded
        for model in self.models():
            try:
                model._setString(4, encoded)
            except Exception:
                _logger.exception('could not update garage card')

    def received(self, scope):
        self.last_scope, self.last_seen = scope, self.now()

    def healthy(self, scope):
        return self.installed and self.last_scope == scope and self.now() - self.last_seen < 5

    def close(self):
        for model in self.models():
            try:
                model._setNumber(1, 0)
            except Exception:
                _logger.debug('garage model already disposed', exc_info=True)
        self.installed = False
