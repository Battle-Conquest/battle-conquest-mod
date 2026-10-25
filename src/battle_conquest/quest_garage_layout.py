"""Pixel layout of the garage card, fixed controls and scrollable snapshot."""
from battle_conquest.quest_garage_widgets import caption, place, screen_size, text_pixels


def layout(self):
    width = max(240, min(640, screen_size()[0] - 32))
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
        self.place()
        return
    editing = self.editing is not None
    extra = 0
    if editing:
        self.actions = self.actions[:5]
        self.actions += self.picker.layout(width - 32)
        extra = self.input_box.height + 16
    height = self.content.height if self.cards_shown else text_pixels(self.body)[1]
    self.region.width = width - 32
    self.region.height = min(height, max(24, screen_size()[1] - 192 - text_pixels(self.footer)[1] - extra))
    place(self.region, 16, 80)
    self.input_box.visible = editing
    y = 80 + self.region.height + 16
    if editing:
        self.input_box.width = width - 32
        place(self.input_box, 16, y)
        y += extra
    button_width = (width - 56) / 4
    for index, button in enumerate(self.buttons):
        button.width, button.height = button_width, 40
        place(button, 16 + index * (button_width + 8), y)
    place(self.footer, 32, y + 48)
    self.status_dot.width = self.status_dot.height = 8
    place(self.status_dot, 16, y + 56)
    self.root.height = y + 64 + text_pixels(self.footer)[1]
    self.overflow = max(0, height - self.region.height)
    self.scroll = min(self.scroll, self.overflow)
    self.region.minScroll, self.region.maxScroll = (0, 0), (0, self.overflow * 2 / screen_size()[1])
    self.region.scroll = (0, self.scroll * 2 / screen_size()[1])
    self.track.visible = self.thumb.visible = self.overflow > 0
    self.track.width, self.track.height = 3, self.region.height
    place(self.track, width - 20, 80)
    self.thumb.width, self.thumb.height = 3, max(20, self.region.height ** 2 / max(1, height))
    place(self.thumb, width - 20, 80 + (self.region.height - self.thumb.height) * self.scroll / max(1, self.overflow))
    self.place()

