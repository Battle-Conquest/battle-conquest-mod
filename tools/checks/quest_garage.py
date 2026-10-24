"""Garage polling, account isolation, conflicts and native panel teardown."""
import copy
import os
import sys
import tempfile
import types

from checks.common import check
from checks.report_sender import _Session, _Response


def check_quest_garage():
    from battle_conquest.quest_garage import Garage
    from battle_conquest.quest_garage_view import lines, metric_value
    from battle_conquest.destinations import Destination, battles_url

    class View(object):
        def __init__(self):
            self.shown = False
            self.resets = 0
        def reset(self):
            self.resets += 1
        def visible(self, state):
            self.shown = state
        def render(self, garage):
            pass
        def close(self):
            pass

    check('absent metrics are not rendered as zero', metric_value({'totals': {'credits_net': None}}, 'credits_net') == '?')
    check('partial known values remain readable', metric_value({'totals': {'credits_net': None}, 'known_totals': {'credits_net': -10}}, 'credits_net') == '-10 + ?')
    session = _Session()
    view = View()
    account = type('Account', (object,), {'account': '500883375'})()
    destination = Destination(battles_url(), enabled=True, modes=['random'], secret='a' * 64)
    places = type('Places', (object,), {'current': destination})()
    clock = [100.0]
    in_garage = [True]
    garage = Garage(session, account, places, view, garage=lambda: in_garage[0],
                    platoon=lambda: ['500883375', '2', '3', '4', '5', '6'], now=lambda: clock[0])
    data = {'schema': 1, 'config': {'version': 1, 'selection': 'individual:1', 'mode': 'platoon', 'manual_ids': []},
            'choices': [{'key': 'individual:1', 'title': 'Quest', 'status': 'active'}], 'selected': {'title': 'Quest'},
            'players': [{'username': 'Self', 'participant': True, 'official': {'available': False, 'updated_at': None}}]}
    garage.data = copy.deepcopy(data)
    garage.data['players'][0].update(official=None, estimate=None, participant=False)
    check('a followed player without a started period has an explicit no-data label', '  no data' in lines(garage))
    garage.data = None
    garage.tick()
    check('panel waits for an available server before appearing', not view.shown)
    check('garage uses the secret and bounds platoon to four other accounts',
          session.sent[0]['headers']['X-Mod-Secret'] == 'a' * 64 and session.sent[0]['url'].endswith('&platoon=2,3,4,5'))
    session.sent.pop(0)['answer'](_Response(200, copy.deepcopy(data)))
    garage.tick()
    check('native panel shown with no optional menu API', view.shown)
    check('no second poll before fifteen seconds', not session.sent)
    garage.poll(force=True)
    session.sent.pop(0)['answer'](_Response(200, {'schema': 1, 'config': []}))
    check('malformed successful replies retain the last readable snapshot', garage.offline and garage.data == data)
    malformed = copy.deepcopy(data)
    malformed['players'][0]['official'] = ['invalid score']
    garage.poll(force=True)
    session.sent.pop(0)['answer'](_Response(200, malformed))
    check('malformed score structures cannot replace readable values', garage.offline and garage.data == data)
    malformed['players'][0]['official'] = {'available': False, 'updated_at': [1, 2]}
    garage.poll(force=True)
    session.sent.pop(0)['answer'](_Response(200, malformed))
    check('malformed timestamps do not replace readable values', garage.offline and garage.data == data)
    fetch = session.fetch
    def unavailable(*args, **kwargs):
        raise RuntimeError('network initiation failed')
    session.fetch = unavailable
    check('a synchronous transport failure does not acknowledge a save', not garage.save(mode='manual'))
    check('transport failures release the in-flight gate and keep the data', garage.busy is None and garage.offline and garage.data == data)
    session.fetch = fetch
    garage.poll(force=True)
    session.sent.pop(0)['answer'](_Response(200, copy.deepcopy(data)))
    check('the poll recovers after a transport failure', not garage.offline)
    garage.save(mode='manual')
    repeated = copy.deepcopy(data)
    repeated['config']['version'] = 3
    session.sent.pop(0)['answer'](_Response(200, repeated))
    check('a concurrent write after successful saving is still visible', garage.conflict and garage.data == data)
    garage.reload()
    session.sent.pop(0)['answer'](_Response(200, copy.deepcopy(data)))
    clock[0] += 15
    garage.tick()
    session.sent.pop(0)['answer'](_Response(503))
    check('offline keeps the last values and says so', garage.data == data and garage.offline and 'Offline' in lines(garage)[-1])
    garage.save(mode='manual', manual_ids=[2, 3])
    request = session.sent.pop(0)
    check('write includes the observed version', request['body']['version'] == 1 and request['method'] == 'POST')
    request['answer'](_Response(409, {'error': 'conflict'}))
    garage.save(mode='manual')
    check('conflicting writes stay blocked until explicit reload', garage.conflict and not session.sent)
    garage.poll(force=True)
    newer = copy.deepcopy(data)
    newer['config']['version'] = 2
    session.sent.pop(0)['answer'](_Response(200, newer))
    check('a background poll cannot silently resolve conflict', garage.data['config']['version'] == 1 and garage.conflict)
    garage.reload()
    session.sent.pop(0)['answer'](_Response(200, newer))
    check('explicit reload accepts the current server version', garage.data['config']['version'] == 2 and not garage.conflict)
    garage.poll(force=True)
    stale = session.sent.pop(0)['answer']
    account.account = '500999999'
    garage.tick()
    check('account switch clears the previous configuration and values', garage.data is None and view.resets == 2)
    stale(_Response(200, data))
    check('late response cannot restore previous account', garage.data is None)
    session.sent.pop(0)['answer'](_Response(200, newer))
    in_garage[0] = False
    clock[0] += 15
    garage.tick()
    garage.save(mode='manual')
    check('battle hides panel and prevents reads and writes', not view.shown and not session.sent)
    in_garage[0] = True
    garage.tick()
    check('returning to garage restores panel and retained values', view.shown and garage.data == newer)
    session.sent.pop(0)['answer'](_Response(200, newer))
    destination.secret = 'b' * 64
    garage.tick()
    check('link changes also clear the old account data', garage.data is None)
    session.sent.pop(0)['answer'](_Response(404, {'error': 'unavailable'}))
    garage.tick()
    check('disabled server feature keeps the native panel hidden', not view.shown and garage.unavailable)
    garage.poll(force=True)
    session.sent.pop(0)['answer'](_Response(200, newer))
    garage.tick()
    check('enabling the combined server release restores the panel', view.shown and not garage.unavailable)


def check_quest_garage_panel():
    from battle_conquest.quest_garage_view import Panel, text_pixels

    modes = type('Modes', (object,), {'CLIP': 0, 'PIXEL': 1, 'LEGACY': 2})
    horizontal = type('Anchors', (object,), {'LEFT': 0, 'CENTER': 1, 'RIGHT': 2})
    vertical = type('Anchors', (object,), {'TOP': 0, 'CENTER': 1, 'BOTTOM': 2})

    class Node(object):
        def __setattr__(self, name, value):
            # The client uses native enums. Bad strings must not appear to
            # switch the rendering coordinate system in a permissive fake.
            if name in ('widthMode', 'heightMode', 'horizontalPositionMode', 'verticalPositionMode', 'horizontalAnchor', 'verticalAnchor') and not isinstance(value, int):
                return
            object.__setattr__(self, name, value)
        def __init__(self, text):
            self.text = text
            self.position = (0, 0, 0)
            self.children = []
            self._height = 200
            self._width = 400
            self.visible = True
            self.parent = None
            self.window = False
            self.horizontalPositionMode = self.verticalPositionMode = modes.LEGACY
            self.widthMode = self.heightMode = modes.LEGACY
        def stringDimensions(self, value):
            rows = value.split('\n')
            return max(len(row) for row in rows) * 9, len(rows) * 24
        @property
        def width(self):
            return self._width if self.window else self.stringDimensions(self.text)[0] * 2.0 / resolution[0]
        @width.setter
        def width(self, value):
            self._width = value
        @property
        def height(self):
            return self._height if self.window else self.stringDimensions(self.text)[1] * 2.0 / resolution[1]
        @height.setter
        def height(self, value):
            self._height = value
        def addChild(self, child, name):
            self.children.append((name, child))
            child.parent = self
        def screen_position(self):
            # BigWorld PIXEL positions start at the screen's top left. Only
            # a Window changes that origin to its own top left for children.
            origin = self.parent.screen_position() if self.parent is not None and self.parent.window else (0, 0)
            x, y = self.position[:2]
            if self.horizontalPositionMode != modes.PIXEL:
                x = (x + 1) * resolution[0] / 2
            if self.verticalPositionMode != modes.PIXEL:
                y = (1 - y) * resolution[1] / 2
            return origin[0] + x, origin[1] + y
        def localToScreen(self, position):
            x, y = self.screen_position()
            return (x + position[0]) * 2.0 / resolution[0] - 1, 1 - (y + position[1]) * 2.0 / resolution[1]
        def clipped(self):
            if self.parent is None or not self.parent.window:
                return False
            x, y = self.position[:2]
            width, height = self.stringDimensions(self.text)
            return x < 0 or y < 0 or x + width > self.parent.width or y + height > self.parent.height

    def window(texture):
        node = Node(texture)
        node.window = True
        return node

    module = types.ModuleType('GUI')
    module.Simple = type('Simple', (object,), {'eSizeMode': modes, 'ePositionMode': modes, 'eHAnchor': horizontal, 'eVAnchor': vertical})
    roots = []
    module.Text = Node
    module.Window = window
    resolution = [2560.0, 1440.0]
    module.screenResolution = lambda: tuple(resolution)
    module.addRoot = roots.append
    module.delRoot = roots.remove
    cursor = [0.3, 0.4]
    module.mcursor = lambda: type('Cursor', (object,), {'position': tuple(cursor)})()
    previous = sys.modules.get('GUI')
    sys.modules['GUI'] = module
    directory = tempfile.mkdtemp(prefix='bc-garage-test-')
    store = os.path.join(directory, 'panel.json')
    try:
        observed = type('Text', (object,), {'width': 0.049224853515625, 'height': 0.03333282470703125})()
        width, height = text_pixels(observed)
        check('the live 2560x1440 text metrics represent about 63x24 pixels', abs(width - 63) < 0.05 and abs(height - 24) < 0.01)
        for width, height in [(1280, 720), (1920, 1080), (2560, 1440)]:
            resolution[:] = [width, height]
            fresh = Panel(None, store=store)
            fresh.visible(True)
            x, y = fresh.root.screen_position()
            check('the first panel fits inside a %sx%s viewport' % (width, height),
                  x >= 16 and y >= 16 and x + fresh.root.width <= width - 16 and y + fresh.root.height <= height - 16)
            projected = fresh.root.localToScreen((0, 0))
            check('the native projected origin is inside the screen clip range',
                  -1 <= projected[0] <= 1 and -1 <= projected[1] <= 1)
            check('native clip text metrics cannot shrink the window and clip its title or actions',
                  not any(node.clipped() for node in [fresh.title, fresh.body] + fresh.buttons))
            check('native text keeps its natural legacy size instead of interpreting clip sizes as pixels',
                  all(node.widthMode == modes.LEGACY and node.heightMode == modes.LEGACY and not node.explicitSize for node in [fresh.title, fresh.body] + fresh.buttons))
            fresh.close()
        resolution[:] = [2560, 1440]
        dragged = Panel(None, store=os.path.join(directory, 'drag.json'))
        dragged.visible(True)
        cursor[:] = [-0.7, 0.6]
        start = dragged.position
        dragged.handleDragStartEvent(dragged.title, tuple(cursor))
        cursor[:] = [-0.5, 0.4]
        dragged.move()
        check('dragging converts clip cursor movement to positive-down pixel offsets',
              abs(dragged.position[0] - start[0] - 256) < 0.001 and abs(dragged.position[1] - start[1] - 144) < 0.001)
        dragged.handleDragStopEvent()
        dragged.close()
        cursor[:] = [0.3, 0.4]
        panel = Panel(None, store=store)
        panel.visible(True)
        check('native panel builds without any third party API', len(roots) == 1 and len(panel.buttons) == 4)
        before = [node.screen_position() for node in [panel.title, panel.body] + panel.buttons]
        check('panel content starts below the draggable title', before[1][0] == before[0][0] and before[1][1] > before[0][1])
        panel.handleMouseClickEvent()
        panel.title.script.handleDragStartEvent(panel.title, (0.0, 0.0))
        panel.handleDragStopEvent()
        after = [node.screen_position() for node in [panel.title, panel.body] + panel.buttons]
        delta = tuple(after[0][i] - before[0][i] for i in (0, 1))
        check('moving the title moves every content and action by the same distance',
              all(all(abs((new[i] - old[i]) - delta[i]) < 0.001 for i in (0, 1)) for old, new in zip(before, after)))
        position = panel.position
        panel.visible(False)
        check('battle hides all panel children through their root', not panel.root.visible)
        panel.visible(True)
        check('garage preserves folding and position', panel.collapsed and panel.position == position)
        restored = Panel(None, store=store)
        check('reloading preserves saved panel placement', restored.collapsed and restored.position == position)
        panel.close()
        check('stopping releases native GUI root', not roots)
        with open(store, 'wb') as handle:
            handle.write('{"coordinate_space":"pixels","position":[-500,9999,0.2]}')
        recovered = Panel(None, store=store)
        recovered.visible(True)
        x, y = recovered.root.screen_position()
        check('saved off-screen positions are brought back into the visible viewport',
              x >= 16 and y >= 16 and x + recovered.root.width <= resolution[0] - 16 and y + recovered.root.height <= resolution[1] - 16)
        recovered.close()
        with open(store, 'wb') as handle:
            handle.write('{"position":[-0.5,0.5,0.2],"collapsed":true}')
        recovered = Panel(None, store=store)
        recovered.visible(True)
        check('legacy clip positions are converted to pixels without losing the fold state',
              recovered.position[:2] == (640.0, 360.0) and recovered.collapsed)
        recovered.close()

        # Full native editor with a poll arriving between typing and Enter.
        from battle_conquest.quest_garage import Garage
        from battle_conquest.destinations import Destination, battles_url
        session = _Session()
        account = type('Account', (object,), {'account': '500883375'})()
        places = type('Places', (object,), {'current': Destination(battles_url(), enabled=True, modes=['random'], secret='a' * 64)})()
        panel = Panel(None, store=store)
        panel.collapsed = False
        panel.visible(True)
        garage = Garage(session, account, places, panel, garage=lambda: True, platoon=lambda: [], now=lambda: 100.0)
        garage.key = garage.identity()
        garage.data = {'schema': 1, 'config': {'version': 1, 'selection': '', 'mode': 'manual', 'manual_ids': [2]},
                       'choices': [], 'selected': None, 'players': []}
        panel.garage = garage
        panel.edit()
        newer = copy.deepcopy(garage.data)
        newer['config'].update(version=2, manual_ids=[3])
        garage.poll(force=True)
        enter = type('Key', (object,), {'key': 13, 'isKeyDown': lambda self: True, 'isMouseButton': lambda self: False})()
        keys = types.ModuleType('Keys')
        keys.KEY_RETURN, keys.KEY_ESCAPE, keys.KEY_BACKSPACE = 13, 27, 8
        previous_keys = sys.modules.get('Keys')
        sys.modules['Keys'] = keys
        try:
            panel.editing = u''
            typed = type('Key', (object,), {'key': 4, 'character': u'4', 'isKeyDown': lambda self: True, 'isMouseButton': lambda self: False})()
            panel.handleKeyEvent(typed)
            check('native character events populate the manual account editor', panel.editing == u'4')
            check('the window includes the complete content and all controls',
                  not any(node.clipped() for node in [panel.title, panel.body] + panel.buttons))
            panel.handleMouseClickEvent()
            check('folding hides content and controls while retaining the title',
                  not panel.body.visible and not any(button.visible for button in panel.buttons) and not panel.title.clipped())
            check('folding an editor returns keyboard input to the garage', not panel.handleKeyEvent(typed) and panel.editing == u'4')
            check('a folded editor cannot submit a hidden draft', not panel.handleKeyEvent(enter) and panel.editing == u'4')
            panel.handleMouseClickEvent()
            check('unfolding restores every control inside the window bounds',
                  panel.body.visible and all(button.visible and not button.clipped() for button in panel.buttons))
            mouse = type('Mouse', (object,), {'key': 256, 'isKeyDown': lambda self: True, 'isMouseButton': lambda self: True})()
            check('editing does not swallow mouse events outside the panel', not panel.handleKeyEvent(mouse))
            panel.editing = u'4'
            garage.offline = True
            panel.render(garage)
            check('editing keeps network failures visible', 'Offline - input retained' in panel.body.text)
            garage.offline = False
            panel.handleKeyEvent(enter)
            check('Enter while a poll is in flight retains the pending input', panel.editing == '4')
            session.sent.pop(0)['answer'](_Response(200, newer))
            panel.handleKeyEvent(enter)
            request = session.sent.pop(0)
            check('manual edits keep the version observed at the start of editing', request['body']['version'] == 1)
            request['answer'](_Response(409, {'error': 'conflict'}))
            check('polling cannot hide a conflicting manual edit', garage.conflict)
            panel.reload()
            session.sent.pop(0)['answer'](_Response(200, newer))
            check('explicit Reload discards the old draft and accepts fresh settings', panel.editing is None and garage.data['config']['version'] == 2)
            panel.edit()
            panel.editing = u'4'
            panel.handleKeyEvent(enter)
            check('an asynchronous save keeps the draft until acknowledged', panel.editing == u'4')
            session.sent.pop(0)['answer'](_Response(503))
            check('a failed asynchronous save leaves the draft ready to retry', panel.editing == u'4' and garage.offline)
            panel.handleKeyEvent(enter)
            session.sent.pop(0)['answer'](_Response(422))
            check('a rejected configuration retains the entered IDs and error', panel.editing == u'4' and garage.error)
            panel.handleKeyEvent(enter)
            request = session.sent.pop(0)
            panel.editing = u'5'
            saved = copy.deepcopy(newer)
            saved['config'].update(request['body'], version=3)
            request['answer'](_Response(200, saved))
            check('typing during a successful save preserves the new draft and advances its version',
                  panel.editing == u'5' and panel.edit_version == 3)
            panel.handleKeyEvent(enter)
            request = session.sent.pop(0)
            check('the retained draft uses the version of its acknowledged write', request['body']['version'] == 3)
            saved['config'].update(request['body'], version=4)
            request['answer'](_Response(200, saved))
            check('a successful acknowledgement closes only the saved draft', panel.editing is None)
        finally:
            if previous_keys is None:
                del sys.modules['Keys']
            else:
                sys.modules['Keys'] = previous_keys
        panel.close()
        with open(store, 'wb') as handle:
            handle.write('[]')
        damaged = Panel(None, store=store)
        check('a valid JSON value of the wrong shape cannot break mod startup', damaged.root is None)
        count = [0]
        def broken_text(value):
            count[0] += 1
            if count[0] == 2:
                raise ValueError('native component unavailable')
            return Node(value)
        module.Text = broken_text
        damaged.visible(True)
        check('a partially built panel cleans up without removing an unregistered GUI root', damaged.failed and damaged.root is None and not roots)

    finally:
        if previous is None:
            del sys.modules['GUI']
        else:
            sys.modules['GUI'] = previous
        import shutil
        shutil.rmtree(directory)


def check_quest_garage_platoon():
    from battle_conquest.quest_garage import platoon_accounts
    names = ('gui.prb_control.dispatcher', 'constants', 'gui.prb_control')
    previous = dict((name, sys.modules.get(name)) for name in names)
    constants = types.ModuleType('constants')
    constants.PREBATTLE_TYPE = type('Types', (object,), {'SQUAD': 1})
    entity = type('Entity', (object,), {'getEntityType': lambda self: 1,
                                       'getPlayers': lambda self: {12: object(), 34: object()}})()
    dispatcher = types.ModuleType(names[0])
    dispatcher.g_prbLoader = type('Loader', (object,), {
        'getDispatcher': lambda self: type('Dispatcher', (object,), {'getEntity': lambda self: entity})()})()
    package = types.ModuleType('gui.prb_control')
    package.__path__ = []
    sys.modules['gui.prb_control'] = package
    sys.modules[names[0]] = dispatcher
    sys.modules['constants'] = constants
    try:
        check('platoon adapter reads the native squad player IDs', set(platoon_accounts()) == set(['12', '34']))
        entity.getEntityType = lambda: 999
        check('a larger unit is never treated as a platoon', platoon_accounts() == [])
    finally:
        for name, module in previous.items():
            if module is None:
                del sys.modules[name]
            else:
                sys.modules[name] = module
