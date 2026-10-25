"""Pixel scrolling and scrollbar input, owned by the existing game hooks."""
from battle_conquest.quest_garage_widgets import place


class Scroll(object):
    def __init__(self, panel):
        self.panel = panel
        self.drag = None

    def cancel(self):
        self.drag = None

    def layout(self, height):
        panel = self.panel
        viewport = panel.region.height
        panel.overflow = max(0, height - viewport)
        panel.scroll = max(0, min(panel.scroll, panel.overflow))
        # Move children in pixels; GUI.Window clips them to the fixed viewport.
        # This avoids mixing native clip-space scroll units with pixel layout.
        if panel.content.node is not None:
            place(panel.content.node, 0, -panel.scroll)
        place(panel.body, 0, -panel.scroll)
        place(panel.input_box, 0, -panel.scroll)
        panel.track.visible = panel.thumb.visible = panel.overflow > 0
        if not panel.overflow:
            self.cancel()
        panel.track.width, panel.track.height = 10, viewport
        place(panel.track, panel.root.width - 26, panel.region.position[1])
        panel.thumb.width = 10
        panel.thumb.height = min(viewport, max(28, viewport ** 2 / max(1, height)))
        travel = viewport - panel.thumb.height
        place(panel.thumb, panel.track.position[0], panel.track.position[1] + travel * panel.scroll / max(1, panel.overflow))

    def move(self, y):
        panel = self.panel
        travel = panel.track.height - panel.thumb.height
        if self.drag is not None and travel > 0:
            top = panel.root.position[1] + panel.track.position[1]
            panel.scroll = max(0, min(1, (y - top - self.drag) / travel)) * panel.overflow
            panel.layout()

    def press(self, position):
        panel = self.panel
        if panel.collapsed or not panel.track.visible or not panel.contains(panel.track, position):
            return False
        if panel.contains(panel.thumb, position):
            self.drag = position[1] - panel.root.position[1] - panel.thumb.position[1]
        else:
            self.drag = panel.thumb.height / 2
            self.move(position[1])
        return True

    def release(self):
        captured = self.drag is not None
        self.cancel()
        return captured

    def wheel(self, delta):
        panel = self.panel
        steps = delta / 120.0 if abs(delta) >= 120 else delta
        panel.scroll = max(0, min(panel.overflow, panel.scroll - steps * 48))
        panel.layout()

    def reveal(self, top, height):
        panel = self.panel
        if top < panel.scroll:
            panel.scroll = top
        elif top + height > panel.scroll + panel.region.height:
            panel.scroll = top + height - panel.region.height
        panel.layout()
