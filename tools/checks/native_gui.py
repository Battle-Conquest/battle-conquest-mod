"""Native GUI fake with client enum types and clip-space text metrics."""
import types
from checks.native_font import metrics


def native_gui():
    font_tree, font_glyphs, font_height = metrics()
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
            self.textureName = text
            self.position = (0, 0, 0)
            self.children = []
            self._height = 200
            self._width = 400
            self.visible = True
            self.parent = None
            self.window = False
            self.script = None
            self.focus = self.mouseButtonFocus = self.moveFocus = False
            self.crossFocus = self.dragFocus = self.dropFocus = False
            self.horizontalPositionMode = self.verticalPositionMode = modes.LEGACY
            self.widthMode = self.heightMode = modes.LEGACY
        def stringDimensions(self, value):
            rows = value.split('\n')
            if getattr(self, 'font', None) == 'battle_conquest/garage.font':
                return (max(sum(font_glyphs.get(ord(char), font_glyphs[ord('?')])[2] for char in row) for row in rows),
                        len(rows) * font_height)
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
        def delChild(self, name):
            self.children[:] = [(key, child) for key, child in self.children if key != name]
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
            width, height = (self.width, self.height) if self.window else self.stringDimensions(self.text)
            return x < 0 or y < 0 or x + width > self.parent.width or y + height > self.parent.height

    def window(texture):
        node = Node(texture)
        node.window = True
        return node

    module = types.ModuleType('GUI')
    module.Simple = type('Simple', (object,), {'eSizeMode': modes, 'ePositionMode': modes, 'eHAnchor': horizontal, 'eVAnchor': vertical,
                                            'eMaterialFX': type('Material', (object,), {'BLEND': 1})})
    roots = []
    module.Text = Node
    module.Window = window
    resolution = [2560.0, 1440.0]
    module.screenResolution = lambda: tuple(resolution)
    module.addRoot = roots.append
    module.delRoot = roots.remove
    cursor = [0.3, 0.4]
    module.mcursor = lambda: type('Cursor', (object,), {'position': tuple(cursor)})()
    def native_dispatch(event):
        # Model the reported native-to-Python boundary failing before the
        # script callback runs. An exception guard inside Panel cannot help.
        def receives(component):
            if not component.visible:
                return False
            focused = any(getattr(component, name) for name in
                          ('focus', 'mouseButtonFocus', 'moveFocus', 'crossFocus', 'dragFocus', 'dropFocus'))
            return (component.script is not None and focused) or any(receives(child) for name, child in component.children)
        if any(receives(root) for root in roots):
            raise TypeError('Unregistered type : BW::KeyEvent')
        return False
    module.handleKeyEvent = module.handleMouseEvent = native_dispatch
    return module, roots, resolution, cursor, Node, modes
