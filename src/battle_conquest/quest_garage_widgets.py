"""Native GUI building blocks using the enum and metric contract of the client."""

PALETTE = {
    'panel': (17, 24, 31, 242), 'header': (30, 42, 54, 255),
    'button': (48, 63, 77, 255), 'hover': (73, 89, 67, 255),
    'accent': (183, 197, 124, 255), 'text': (237, 241, 245, 255),
    'muted': (168, 183, 195, 255), 'input': (9, 15, 21, 255),
    'error': (249, 163, 127, 255), 'track': (48, 61, 70, 255),
}


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
    node = GUI.Window('system/maps/col_white.bmp' if color else '')
    node.widthMode = node.heightMode = GUI.Simple.eSizeMode.PIXEL
    node.materialFX = GUI.Simple.eMaterialFX.BLEND
    if color:
        node.colour = PALETTE[color]
    place(node, 0, 0)
    if parent is not None:
        parent.addChild(node, name)
    return node


def label(parent, name, value='', color='text'):
    import GUI
    node = GUI.Text(value)
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
    node.text = value
    node.colour = PALETTE['text' if enabled else 'muted']
    width, height = text_pixels(node)
    place(node, max(6, (button.width - width) / 2), max(4, (button.height - height) / 2))
