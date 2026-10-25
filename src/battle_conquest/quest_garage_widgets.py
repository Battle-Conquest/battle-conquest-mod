"""Native GUI building blocks using the enum and metric contract of the client."""
from battle_conquest.i18n import tr

PALETTE = {
    'panel': (17, 23, 30, 255), 'header': (27, 36, 46, 255),
    'card': (28, 38, 49, 255), 'button': (46, 61, 77, 255),
    'hover': (72, 91, 111, 255), 'primary': (109, 82, 30, 255),
    'primary_hover': (145, 108, 36, 255), 'disabled': (35, 45, 56, 255),
    'accent': (240, 197, 109, 255), 'text': (255, 255, 255, 255),
    'muted': (199, 211, 224, 255), 'input': (9, 15, 22, 255),
    'error': (255, 184, 161, 255), 'track': (55, 71, 87, 255),
    'official': (137, 225, 184, 255), 'estimate': (157, 205, 255, 255),
    'clear': (0, 0, 0, 0),
}
TEXTURES = 'gui/maps/battle_conquest/garage/'


def paint(node, role):
    # Baked pixels also work when the native material ignores vertex tint.
    texture = TEXTURES + (role or 'clear') + '.dds'
    if node.textureName != texture:
        node.textureName = texture
    node.colour = (255, 255, 255, 255)


def screen_size():
    import GUI
    width, height = GUI.screenResolution()
    return max(1.0, float(width)), max(1.0, float(height))


def bounded_position(position, size):
    width, height = screen_size()
    return (max(16.0, min(max(16.0, width - size[0] - 16), position[0])),
            max(16.0, min(max(16.0, height - size[1] - 16), position[1])), 0.2)


def text_pixels(node):
    width, height = screen_size()
    return node.width * width / 2, node.height * height / 2


def place(node, x, y):
    import GUI
    node.horizontalAnchor = GUI.Simple.eHAnchor.LEFT
    node.verticalAnchor = GUI.Simple.eVAnchor.TOP
    node.horizontalPositionMode = node.verticalPositionMode = GUI.Simple.ePositionMode.PIXEL
    node.position = (x, y, 0)


def surface(parent, name, color=None):
    import GUI
    node = GUI.Window(TEXTURES + (color or 'clear') + '.dds')
    node.widthMode = node.heightMode = GUI.Simple.eSizeMode.PIXEL
    node.materialFX = GUI.Simple.eMaterialFX.BLEND
    paint(node, color)
    place(node, 0, 0)
    if parent is not None:
        parent.addChild(node, name)
    return node


def label(parent, name, value='', color='text'):
    import GUI
    node = GUI.Text(tr(value))
    node.font = 'default_medium.font'
    node.colourFormatting = False
    node.multiline = True
    node.explicitSize = False
    node.widthMode = node.heightMode = GUI.Simple.eSizeMode.LEGACY
    node.colour = PALETTE[color]
    place(node, 0, 0)
    parent.addChild(node, name)
    return node


def wrapped(node, rows, width):
    """Measure with the native font instead of assuming a fixed character size."""
    result = []
    for row in rows:
        line = u''
        for word in unicode(row).split():
            candidate = (line + u' ' + word).strip()
            node.text = candidate
            if text_pixels(node)[0] <= width:
                line = candidate
                continue
            if line:
                result.append(line)
            line = u''
            for char in word:
                candidate = line + char
                node.text = candidate
                if line and text_pixels(node)[0] > width:
                    result.append(line.rstrip())
                    line = char
                else:
                    line = candidate
        result.append(line.rstrip())
    node.text = u'\n'.join(result)
    return text_pixels(node)


def caption(button, node, value, enabled=True):
    node.text = tr(value)
    node.colour = PALETTE['text' if enabled else 'muted']
    width, height = text_pixels(node)
    place(node, max(6, (button.width - width) / 2), max(4, (button.height - height) / 2))
