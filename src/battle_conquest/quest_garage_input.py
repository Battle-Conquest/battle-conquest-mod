"""Session-owned input routing for a native panel over the Scaleform garage."""
from battle_conquest.quest_garage_widgets import screen_size


def point(event):
    x, y = event.cursorPosition
    width, height = screen_size()
    return (x + 1) * width / 2, (1 - y) * height / 2


class Input(object):
    def __init__(self, session, panel, game=None):
        self.session = session
        self.panel = panel
        self.game = game
        self.owned_keys = set()

    def active(self):
        panel = self.panel
        active = (panel.root is not None and panel.root.visible and panel.garage is not None
                  and panel.garage.garage() and panel.garage.ready())
        if not active:
            panel.drag = panel.pressed = None
            if panel.scroller is not None:
                panel.scroller.cancel()
            self.owned_keys.clear()
        return active

    def key(self, event):
        if not self.active():
            return False
        if event.isMouseButton():
            return self.panel.pointer(event)
        if not event.isKeyDown() and event.key in self.owned_keys:
            self.owned_keys.discard(event.key)
            return True
        handled = self.panel.handleKeyEvent(event)
        if handled and event.isKeyDown():
            self.owned_keys.add(event.key)
        return handled

    def mouse(self, event):
        return self.panel.pointer_move(event) if self.active() else False

    def install(self):
        if self.game is None:
            import game
            self.game = game
        def key(original):
            def handle(event):
                return True if self.key(event) else original(event)
            return handle
        def mouse(original):
            def handle(event):
                return True if self.mouse(event) else original(event)
            return handle
        self.session.patch(self.game, 'handleKeyEvent', key)
        self.session.patch(self.game, 'handleMouseEvent', mouse)
        self.session.on_close(self.owned_keys.clear)
