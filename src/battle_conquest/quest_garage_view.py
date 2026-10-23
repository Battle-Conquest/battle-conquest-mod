"""A native BigWorld GUI panel; no optional mod menu is required."""
import json
import logging
import os
import time
import calendar

from battle_conquest import config

_logger = logging.getLogger('battle_conquest.quest_garage')
STORE = os.path.join(config.CONFIG_DIR, 'garage-panel.json')


def clean(value, limit=64):
    return u' '.join(unicode(value).split())[:limit]


def lines(garage):
    data = garage.data
    if data is None:
        return [u'Waiting for quest data...' if not garage.offline else u'Offline - no data yet.']
    result = [u'Active quests / joined sessions:']
    active = [choice for choice in data.get('choices', []) if choice.get('joined', True)]
    for choice in active[:5]:
        result.append(u'  %s (%s)' % (clean(choice['title']), clean(choice['status'])))
    if len(active) > 5:
        result.append(u'  +%s more (see website)' % (len(active) - 5))
    selected = data.get('selected')
    result.append(u'Selected: %s' % (clean(selected['title']) if selected else u'none'))
    period = data.get('period')
    if period:
        result.append(u'UTC: %s / %s' % (period['start'], period['end']))
    timestamps = []
    for player in data.get('players', [])[:5]:
        result.append(u'%s%s' % (clean(player['username'], 30), u'' if player['participant'] else u' - indicative, no rewards'))
        for source in ('official', 'estimate'):
            score = player.get(source)
            if score is None:
                continue
            label = u'Official' if source == 'official' else u'Mod estimate'
            if not score.get('available'):
                detail = u'no data'
            elif score.get('comparable') is False:
                detail = u'not comparable'
            else:
                detail = u', '.join(u'%s %s/%s' % (criterion['criterion_type'].replace('_', ' '),
                                                  score['totals'].get(criterion['criterion_type'], '?'), criterion['target_value'])
                                    for criterion in data.get('criteria', []))
                detail += u' (%s battles)' % score['battles']
            if score.get('incomplete'):
                detail += u' - incomplete'
            result.append(u'  %s: %s' % (label, detail))
            stamp = score.get('updated_at')
            if stamp:
                try:
                    timestamps.append(calendar.timegm(time.strptime(stamp, '%Y-%m-%d %H:%M:%S')))
                except ValueError:
                    pass
    age = max(0, int(garage.now() - min(timestamps))) if timestamps else None
    result.append(u'%s | Data age: %s' % (u'Offline' if garage.offline else u'Online',
                                         u'%ss' % age if age is not None else u'unknown'))
    if garage.error:
        result.append(garage.error)
    return result


class Click(object):
    def __init__(self, action):
        self.action = action

    def handleMouseClickEvent(self, *args):
        self.action()
        return True

    def handleMouseButtonEvent(self, *args):
        return True

    def __getattr__(self, name):
        return lambda *args: False


class Panel(object):
    def __init__(self, session, store=STORE):
        self.session = session
        self.store = store
        self.root = None
        self.body = None
        self.garage = None
        self.collapsed = False
        self.position = (-0.95, 0.75, 0.2)
        self.drag = None
        self.editing = None
        self.buttons = []
        self.failed = False
        try:
            with open(store, 'rb') as handle:
                state = json.load(handle)
            pos = state.get('position')
            if isinstance(pos, list) and len(pos) == 3:
                self.position = (max(-0.95, min(0.45, float(pos[0]))), max(-0.5, min(0.95, float(pos[1]))), 0.2)
            self.collapsed = bool(state.get('collapsed'))
        except (ValueError, TypeError, IOError, OSError):
            pass

    def build(self):
        import GUI
        self.root = GUI.Text(u'Battle-Conquest quests [click to fold, drag to move]')
        self.root.colourFormatting = False
        self.root.horizontalAnchor = 'LEFT'
        self.root.verticalAnchor = 'TOP'
        self.root.position = self.position
        self.root.script = self
        self.root.focus = True
        self.root.mouseButtonFocus = True
        self.root.dragFocus = True
        self.root.moveFocus = True
        self.body = self.label(u'', 24)
        for offset, label, action in (
                (0, u'Next quest', lambda: self.garage.next_quest()),
                (110, u'Switch mode', lambda: self.garage.toggle_mode()),
                (230, u'Manual IDs', self.edit),
                (330, u'Reload', lambda: self.garage.reload())):
            button = self.label(label, 48, offset)
            button.focus = True
            button.mouseButtonFocus = True
            button.script = Click(action)
            self.buttons.append(button)
        GUI.addRoot(self.root)

    def label(self, value, y, x=0):
        import GUI
        node = GUI.Text(value)
        node.colourFormatting = False
        node.multiline = True
        node.heightMode = 'PIXEL'
        node.widthMode = 'PIXEL'
        node.horizontalAnchor = 'LEFT'
        node.verticalAnchor = 'TOP'
        node.horizontalPositionMode = 'PIXEL'
        node.verticalPositionMode = 'PIXEL'
        node.position = (x, -y, 0)
        self.root.addChild(node, 'part%s' % len(self.root.children))
        return node

    def visible(self, visible):
        if self.root is None and visible and not self.failed:
            try:
                self.build()
            except Exception:
                self.failed = True
                _logger.exception('native garage panel unavailable')
                self.close()
                return
        if self.root is not None:
            self.root.visible = visible
            if not visible:
                self.drag = None
                self.editing = None

    def reset(self):
        self.editing = None
        self.drag = None
        if self.body is not None:
            self.body.text = u''

    def render(self, garage):
        self.garage = garage
        if self.root is None:
            return
        self.move()
        self.body.visible = not self.collapsed
        for button in self.buttons:
            button.visible = not self.collapsed
        if self.collapsed:
            return
        mode = garage.data['config']['mode'] if garage.data else 'unknown'
        content = [u'Mode: %s' % mode] + lines(garage)
        if self.editing is not None:
            content = [u'Other BC IDs, comma separated (max 4). Enter: save. Esc: cancel.', self.editing]
        self.body.text = u'\n'.join(content)
        height = self.body.height
        for button in self.buttons:
            button.position = (button.position[0], -height - 36, 0)

    def edit(self):
        if self.garage and self.garage.data and not self.garage.conflict:
            self.editing = u','.join(str(i) for i in self.garage.data['config']['manual_ids'])
            self.render(self.garage)

    def handleKeyEvent(self, event):
        if self.editing is None or not self.root.visible:
            return False
        import Keys
        if not event.isKeyDown():
            return True
        if event.key == Keys.KEY_ESCAPE:
            self.editing = None
        elif event.key == Keys.KEY_RETURN:
            values = self.editing.split(',') if self.editing.strip() else []
            if len(values) <= 4 and all(value.strip().isdigit() for value in values):
                self.garage.save(manual_ids=[int(value.strip()) for value in values], mode='manual')
                self.editing = None
            else:
                self.garage.error = 'Use up to four BC account IDs.'
        elif event.key == Keys.KEY_BACKSPACE:
            self.editing = self.editing[:-1]
        else:
            char = getattr(event, 'char', '')
            if char and char in '0123456789, ' and len(self.editing) < 100:
                self.editing += char
        self.render(self.garage)
        return True

    def handleMouseClickEvent(self, *args):
        self.collapsed = not self.collapsed
        self.remember()
        if self.garage:
            self.render(self.garage)
        return True

    def handleMouseButtonEvent(self, *args):
        return True

    def handleDragStartEvent(self, component, position):
        self.drag = (position[0], position[1], self.root.position[0], self.root.position[1])
        if self.session is not None:
            self.session.callback(0.02, self.follow_drag)
        return True

    def follow_drag(self):
        if self.drag and self.root is not None and self.root.visible:
            self.move()
            self.session.callback(0.02, self.follow_drag)

    def move(self):
        if self.drag:
            import GUI
            cursor = GUI.mcursor().position
            x, y, px, py = self.drag
            self.root.position = (max(-0.95, min(0.45, px + cursor[0] - x)), max(-0.5, min(0.95, py + cursor[1] - y)), 0.2)

    def handleDragStopEvent(self, *args):
        self.move()
        self.drag = None
        self.position = tuple(self.root.position)
        self.remember()

    def remember(self):
        try:
            directory = os.path.dirname(self.store)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)
            with open(self.store, 'wb') as handle:
                json.dump({'position': self.position, 'collapsed': self.collapsed}, handle)
        except (IOError, OSError):
            _logger.exception('could not save garage panel position')

    def close(self):
        if self.root is not None:
            import GUI
            GUI.delRoot(self.root)
            self.root = None
            self.body = None
            self.buttons = []

    def __getattr__(self, name):
        return lambda *args: False


def install(session, account, places, sender):
    from battle_conquest.quest_garage import Garage
    panel = Panel(session)
    garage = Garage(session, account, places, panel)
    panel.garage = garage
    garage.install(sender)
    return garage
