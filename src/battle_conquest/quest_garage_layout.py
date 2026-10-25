"""Fixed-height garage viewport with pinned actions and status."""
from battle_conquest.quest_garage_widgets import caption, place, screen_size, text_pixels


def layout(self):
    width, screen_height = screen_size()
    width = max(240, min(640, width - 32))
    self.root.width, self.header.width, self.header.height = width, width, 64
    place(self.title, 16, 6)
    place(self.subtitle, 16, 33)
    self.fold_button.width, self.fold_button.height = 112, 36
    place(self.fold_button, width - 128, 14)
    caption(self.fold_button, self.fold_label, u'Expand' if self.collapsed else u'Collapse')
    self.accent.width, self.accent.height = width, 2
    place(self.accent, 0, 62)
    for node in [self.region, self.input_box, self.footer, self.status_dot, self.track, self.thumb] + self.buttons:
        node.visible = not self.collapsed
    if self.collapsed:
        self.root.height = 64
        self.scroller.cancel()
        self.place()
        return
    self.root.height = min(520, screen_height - 32)
    editing = self.editing is not None
    self.actions = self.actions[:5]
    self.input_box.visible = editing
    self.input_box.width = width - 48
    if editing:
        self.actions += self.picker.layout(self.input_box.width)
    height = self.input_box.height if editing else self.content.height if self.cards_shown else text_pixels(self.body)[1]
    footer_height = text_pixels(self.footer)[1]
    buttons_y = self.root.height - footer_height - 72
    self.region.width, self.region.height = width - 32, max(24, buttons_y - 88)
    place(self.region, 16, 72)
    button_width = (width - 56) / 4
    for index, button in enumerate(self.buttons):
        button.width, button.height = button_width, 40
        place(button, 16 + index * (button_width + 8), buttons_y)
    place(self.footer, 32, buttons_y + 48)
    self.status_dot.width = self.status_dot.height = 8
    place(self.status_dot, 16, buttons_y + 56)
    self.scroller.layout(height)
    self.place()
