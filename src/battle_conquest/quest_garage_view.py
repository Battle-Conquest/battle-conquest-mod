"""A movable native quest window, independent of optional mod menus."""
import json
import logging
import math
import os

from battle_conquest import config
from battle_conquest.quest_garage_text import clean, lines, metric_value, status_line
from battle_conquest.i18n import tr
from battle_conquest.quest_garage_widgets import (PALETTE, bounded_position, caption, label,
                                                paint, screen_size, surface, text_pixels, wrapped)

_logger = logging.getLogger('battle_conquest.quest_garage')
STORE = os.path.join(config.CONFIG_DIR, 'garage-panel.json')


class Panel(object):
    def __init__(self, session, store=STORE):
        self.session, self.store = session, store
        self.root = self.title = self.body = self.garage = None
        self.collapsed = False
        self.position = (32.0, 120.0, 0.2)
        self.legacy_position = None
        self.drag = self.pressed = self.editing = self.edit_version = None
        self.attached = self.failed = False
        self.buttons, self.button_labels, self.actions = [], [], []
        self.disabled = set()
        self.scroll = self.overflow = 0
        self.scroller = None
        self.scroll_key = None
        self.content_key = None
        self.content = None
        self.picker = None
        self.cards_shown = False
        self.hovered, self.styles = None, {}
        try:
            with open(store, 'rb') as handle:
                state = json.load(handle)
            if not isinstance(state, dict):
                return
            pos = state.get('position')
            if isinstance(pos, list) and len(pos) == 3:
                pos = (float(pos[0]), float(pos[1]), 0.2)
                if any(math.isnan(value) or math.isinf(value) for value in pos):
                    raise ValueError('non-finite panel position')
                if state.get('coordinate_space') == 'pixels':
                    self.position = pos
                else:
                    self.legacy_position = pos
            self.collapsed = bool(state.get('collapsed'))
        except (ValueError, TypeError, IOError, OSError):
            pass

    def build(self):
        self.root = surface(None, 'root', 'panel')
        if self.legacy_position is not None:
            width, height = screen_size()
            x, y = self.legacy_position[:2]
            self.position = ((x + 1) * width / 2, (1 - y) * height / 2, 0.2)
            self.legacy_position = None
        self.root.position = self.position
        self.header = surface(self.root, 'header', 'header')
        self.accent = surface(self.root, 'accent', 'accent')
        self.title = label(self.header, 'title', u'Battle-Conquest', 'accent')
        self.subtitle = label(self.header, 'subtitle', u'Quest tracker - drag header to move', 'muted')
        self.fold_button = surface(self.header, 'fold', 'button')
        self.fold_label = label(self.fold_button, 'caption')
        self.region = surface(self.root, 'content')
        self.body = label(self.region, 'text')
        from battle_conquest.quest_garage_content import Content
        self.content = Content(self.region)
        self.input_box = surface(self.region, 'input', 'input')
        from battle_conquest.quest_garage_players import Picker
        self.picker = Picker(self)
        self.picker.build()
        self.footer = label(self.root, 'status', '', 'muted')
        self.status_dot = surface(self.root, 'connection', 'official')
        self.track = surface(self.root, 'track', 'track')
        self.thumb = surface(self.root, 'thumb', 'accent')
        from battle_conquest.quest_garage_scroll import Scroll
        self.scroller = Scroll(self)
        for index in range(4):
            button = surface(self.root, 'button%s' % index, 'button')
            self.buttons.append(button)
            self.button_labels.append(label(button, 'caption'))
        self.layout()
        import GUI
        GUI.addRoot(self.root)
        self.attached = True
        if self.session is not None:
            from battle_conquest.quest_garage_input import Input
            Input(self.session, self).install()
        _logger.info('garage geometry feedback-v13: viewport=%s position=%s size=%s projected=%s',
                     screen_size(), self.position, (self.root.width, self.root.height), self.root.localToScreen((0, 0)))
        _logger.info('garage theme: baked-dds background=%s material=%s colour=%s',
                     self.root.textureName, self.root.materialFX, self.root.colour)
        _logger.info('garage input: game-hooks-only; native GUI callbacks disabled')
        _logger.info('garage font: bundled-unicode font=%s', self.title.font)
        _logger.info('garage display: data-age=hh:mm:ss')

    def visible(self, visible, preserve_draft=False):
        if self.root is None and visible and not self.failed:
            try:
                self.build()
            except Exception:
                self.failed = True
                _logger.exception('native garage panel unavailable')
                self.close()
                return
        if self.root is not None:
            was_visible = self.root.visible
            self.root.visible = visible
            if not visible:
                query = self.picker.query
                self.picker.cancel()
                self.scroller.cancel()
                self.drag = self.pressed = self.hovered = None
                if preserve_draft:
                    self.picker.query = query
                else:
                    self.editing = self.edit_version = None
                self.restyle()
            elif not was_visible and not self.collapsed and self.editing is not None and self.picker.query:
                self.picker.type(self.picker.query)

    def reset(self):
        if self.picker is not None:
            self.picker.cancel()
        self.editing = self.edit_version = self.drag = self.pressed = None
        self.content_key = self.scroll_key = None
        self.scroll = 0
        if self.scroller is not None:
            self.scroller.cancel()
        if self.content is not None:
            self.content.clear()
        if self.body is not None:
            self.body.text = u''

    def render(self, garage):
        self.garage = garage
        if self.root is None:
            return
        rows = [] if garage.data else [u'Offline - no data yet.' if garage.offline else u'Waiting for quest data...']
        status = status_line(garage) if garage.data else tr(u'Connecting...')
        rows = [row for row in rows if row != status and row != garage.error]
        editing = self.editing is not None
        if editing:
            rows = [u'Follow up to four other Battle-Conquest players.', u'Search by player name and choose a suggestion.']
        elif garage.data and not garage.data.get('selected'):
            rows += [u'', u'Choose a quest on the website or click Change quest.']
        self.subtitle.text = tr(u'Configuration conflict - Reload' if garage.conflict else
                               u'Offline - values retained' if garage.offline else u'QUEST TRACKER - drag to move')
        if garage.busy is not None:
            status = tr(u'Updating...  |  ') + status
        wrapped(self.footer, [tr(garage.error) if garage.error else status], max(200, min(640, screen_size()[0] - 32)) - 48)
        self.footer.colour = PALETTE['error' if garage.error else 'muted']
        paint(self.status_dot, 'error' if garage.error or garage.offline else 'official')
        width = max(240, min(640, screen_size()[0] - 32))
        rows = [tr(row) for row in rows]
        key = (tuple(rows), width, editing)
        if key != self.content_key:
            wrapped(self.body, rows, width - 44)
            self.content_key = key
        self.cards_shown = garage.data is not None and not editing
        self.body.visible = not self.cards_shown and not editing
        scope = (((garage.data or {}).get('selected') or {}).get('key', (garage.data or {}).get('config', {}).get('selection')), editing)
        if scope != self.scroll_key:
            self.scroll, self.scroll_key = 0, scope
        if self.cards_shown:
            self.content.render(garage.display_data(), width - 48)
        self.content.show(self.cards_shown)
        busy = garage.busy is not None
        editable = garage.data is not None and not garage.conflict and not busy
        titles = [u'Save', u'Cancel', u'Clear', u'Reload'] if editing else [u'Change quest', u'Mode: Manual' if garage.data and garage.data['config']['mode'] == 'manual' else u'Mode: Platoon', u'Edit players', u'Reload']
        callbacks = [self.submit_edit, self.cancel_edit, self.clear_edit, self.reload] if editing else [garage.next_quest, garage.toggle_mode, self.edit, self.reload]
        enabled = [editable, True, True, not busy] if editing else [editable, editable, editable, not busy]
        self.disabled = set(id(node) for node, ok in zip(self.buttons, enabled) if not ok)
        self.actions = [(self.fold_button, self.toggle)] + list(zip(self.buttons, callbacks))
        self.styles = dict((id(node), 'disabled' if not ok else 'primary' if index == 0 else 'button')
                           for index, (node, ok) in enumerate(zip(self.buttons, enabled)))
        self.layout()
        for node, text, value, ok in zip(self.buttons, self.button_labels, titles, enabled):
            caption(node, text, value, ok)
        self.restyle()

    def restyle(self):
        for node in [self.fold_button] + self.buttons + (self.picker.targets if self.picker else []):
            role = self.styles.get(id(node), 'button')
            active = self.pressed[0] if self.pressed else self.hovered
            if node is active and id(node) not in self.disabled:
                role = 'primary_hover' if role == 'primary' else 'hover'
            paint(node, role)

    def layout(self):
        from battle_conquest.quest_garage_layout import layout
        layout(self)

    def place(self):
        self.position = bounded_position(self.root.position, (self.root.width, self.root.height))
        self.root.position = self.position

    def contains(self, node, point):
        x, y = self.root.position[:2]
        if node is not self.root:
            x, y = x + node.position[0], y + node.position[1]
            if self.picker is not None and node in self.picker.targets:
                x, y = x + self.input_box.position[0] + self.region.position[0], y + self.input_box.position[1] + self.region.position[1]
                if not self.region.visible or not self.contains(self.region, point):
                    return False
        return x <= point[0] <= x + node.width and y <= point[1] <= y + node.height

    def pointer(self, event):
        import Keys
        from battle_conquest.quest_garage_input import point
        if (self.root is None or not self.root.visible or self.garage is None
                or not self.garage.garage() or event.key != Keys.KEY_LEFTMOUSE):
            return False
        pos = point(event)
        if event.isKeyDown():
            if self.scroller.press(pos):
                return True
            for node, action in self.actions:
                if node.visible and self.contains(node, pos):
                    if id(node) not in self.disabled:
                        self.pressed = (node, action, self.editing is not None, self.edit_version)
                        self.restyle()
                    return True
            if self.contains(self.header, pos):
                self.handleDragStartEvent(self.header, event.cursorPosition)
                return True
        else:
            if self.scroller.release():
                return True
            if self.drag is not None:
                self.move(event.cursorPosition)
                self.handleDragStopEvent()
                return True
            if self.pressed is not None:
                node, action, editing, version = self.pressed
                self.pressed = None
                self.restyle()
                if (node.visible and self.contains(node, pos) and id(node) not in self.disabled
                        and editing == (self.editing is not None) and version == self.edit_version):
                    action()
                    self.render(self.garage)
                return True
        return self.contains(self.root, pos)

    def pointer_move(self, event):
        from battle_conquest.quest_garage_input import point
        if self.scroller.drag is not None:
            self.scroller.move(point(event)[1])
            return True
        if self.drag is not None:
            self.move(event.cursorPosition)
            return True
        pos = point(event)
        hovered = next((node for node, action in self.actions if node.visible and self.contains(node, pos)), None)
        if hovered is not self.hovered:
            self.hovered = hovered
            self.restyle()
        if not self.collapsed and getattr(event, 'dz', 0) and (self.contains(self.region, pos) or self.contains(self.track, pos)):
            self.scroller.wheel(event.dz)
            return True
        return False

    def edit(self):
        if self.garage and self.garage.data and not self.garage.conflict:
            self.edit_version = self.garage.data['config']['version']
            self.editing = u','.join(str(i) for i in self.garage.data['config']['manual_ids'])
            self.picker.open()
            self.render(self.garage)

    def cancel_edit(self):
        self.picker.cancel()
        self.editing = self.edit_version = None
        self.render(self.garage)

    def clear_edit(self):
        self.picker.clear()

    def submit_edit(self):
        if self.picker.query.strip():
            self.picker.message = u'Choose a player from the suggestions first.'
            self.render(self.garage)
            return
        values = self.editing.split(',') if self.editing.strip() else []
        if len(values) > 4 or not all(value.strip().isdigit() for value in values):
            self.garage.error = 'Choose up to four players.'
            return
        draft, version = self.editing, self.edit_version
        def acknowledged():
            if self.edit_version == version:
                self.edit_version = version + 1
                if self.editing == draft and not self.picker.query:
                    self.editing = None
        self.garage.save(expected_version=version, on_saved=acknowledged,
                                 manual_ids=[int(value.strip()) for value in values], mode='manual')

    def reload(self):
        if self.garage.busy is None:
            self.picker.cancel()
            self.editing = self.edit_version = None
            self.garage.reload()

    def handleKeyEvent(self, event):
        if self.editing is None or self.root is None or not self.root.visible or self.collapsed or event.isMouseButton():
            return False
        self.picker.key(event)
        return True

    def toggle(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.picker.sequence += 1
            self.picker.results = []
            if self.garage:
                self.garage.search_ticket = None
        self.remember()
        if self.garage:
            self.render(self.garage)
            if not self.collapsed and self.editing is not None and self.picker.query:
                self.picker.type(self.picker.query)

    def handleDragStartEvent(self, component, position):
        self.drag = (position[0], position[1], self.root.position[0], self.root.position[1])
        _logger.info('garage drag started at %s', self.root.position)

    def move(self, cursor=None):
        if self.drag is not None:
            if cursor is None:
                import GUI
                cursor = GUI.mcursor().position
            x, y, px, py = self.drag
            width, height = screen_size()
            self.root.position = (px + (cursor[0] - x) * width / 2, py - (cursor[1] - y) * height / 2, 0.2)
            self.place()

    def handleDragStopEvent(self, *args):
        self.drag = None
        _logger.info('garage drag stopped at %s', self.position)
        self.remember()

    def remember(self):
        try:
            directory = os.path.dirname(self.store)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)
            with open(self.store, 'wb') as handle:
                json.dump({'coordinate_space': 'pixels', 'position': self.position, 'collapsed': self.collapsed}, handle)
        except (IOError, OSError):
            _logger.exception('could not save garage panel position')

    def close(self):
        if self.picker is not None:
            self.picker.cancel()
        self.picker = None
        if self.scroller is not None:
            self.scroller.cancel()
        self.scroller = None
        root, attached = self.root, self.attached
        if self.content is not None:
            self.content.clear()
        self.content = self.hovered = None
        self.root = self.title = self.body = self.drag = self.pressed = None
        self.buttons, self.button_labels, self.actions = [], [], []
        for name in ('header', 'accent', 'subtitle', 'fold_button', 'fold_label', 'region', 'input_box', 'input_label', 'footer', 'status_dot', 'track', 'thumb'):
            setattr(self, name, None)
        self.attached = False
        if root is not None and attached:
            import GUI
            GUI.delRoot(root)

    def __getattr__(self, name):
        return lambda *args: False


def install(session, account, places, sender):
    from battle_conquest.quest_garage import Garage
    panel = Panel(session)
    garage = Garage(session, account, places, panel)
    panel.garage = garage
    garage.install(sender)
    return garage
