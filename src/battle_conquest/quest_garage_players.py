"""Player-name suggestions with selected names and hidden BC identifiers."""
import unicodedata

from battle_conquest.i18n import tr
from battle_conquest.quest_garage_widgets import caption, label, native_text, place, surface, text_pixels


class Picker(object):
    def __init__(self, panel):
        self.panel = panel
        self.entries, self.results, self.targets = [], [], []
        self.query, self.message = u'', u''
        self.sequence, self.active = 0, -1
        self.selected_rows, self.result_rows, self.remove_buttons = [], [], []

    def build(self):
        parent = self.panel.input_box
        self.field = surface(parent, 'query', 'input')
        self.query_label = label(self.field, 'value')
        self.status = label(parent, 'searchStatus', color='muted')
        for index in range(4):
            row = surface(parent, 'selected%s' % index, 'card')
            self.selected_rows.append((row, label(row, 'name')))
            remove = surface(parent, 'remove%s' % index, 'button')
            self.remove_buttons.append((remove, label(remove, 'caption')))
            self.targets.append(remove)
        for index in range(5):
            row = surface(parent, 'result%s' % index, 'button')
            self.result_rows.append((row, label(row, 'name')))
            self.targets.append(row)

    def open(self):
        panel = self.panel
        self.cancel()
        known = dict((row['id'], row['username']) for row in panel.garage.data.get('manual_players', []))
        known.update((row['user_id'], row['username']) for row in panel.garage.data.get('players', []) if 'user_id' in row)
        self.entries = [{'id': value, 'username': known.get(value, u'')} for value in panel.garage.data['config']['manual_ids']]

    def cancel(self):
        self.sequence += 1
        self.results, self.query, self.message, self.active = [], u'', u'', -1
        if self.panel.garage is not None:
            self.panel.garage.search_ticket = None

    def changed(self):
        self.panel.editing = u','.join(str(row['id']) for row in self.entries)
        self.panel.render(self.panel.garage)

    def clear(self):
        self.cancel()
        self.entries = []
        self.changed()

    def remove(self, index):
        if index < len(self.entries):
            self.entries.pop(index)
            self.cancel()
            self.changed()

    def pick(self, index):
        if index < len(self.results) and len(self.entries) < 4:
            self.choose(self.results[index])

    def choose(self, row):
        if row in self.results and len(self.entries) < 4:
            if row['id'] not in [entry['id'] for entry in self.entries]:
                self.entries.append(row)
            self.cancel()
            self.changed()

    def type(self, value):
        self.sequence += 1
        self.query = native_text(value)[:64]
        self.results, self.active = [], -1
        self.panel.garage.search_ticket = None
        self.message = u'Type at least two characters.' if len(self.query.strip()) < 2 else u'Searching players...'
        if len(self.query.strip()) >= 2 and len(self.entries) < 4:
            sequence, query, key = self.sequence, self.query.strip(), self.panel.garage.identity()
            def search():
                panel = self.panel
                if (sequence != self.sequence or panel.editing is None or panel.collapsed
                        or panel.root is None or not panel.root.visible or panel.garage.identity() != key
                        or not panel.garage.garage()):
                    return
                def answered(rows):
                    if (sequence != self.sequence or panel.editing is None or panel.collapsed
                            or panel.garage.identity() != key or not panel.garage.garage()
                            or panel.root is None or not panel.root.visible):
                        return
                    chosen = [row['id'] for row in self.entries]
                    self.results = [row for row in rows or [] if row['id'] not in chosen][:5]
                    self.message = (u'Player search unavailable. Try again.' if rows is None else
                                    u'Choose a player below.' if self.results else u'No matching players.')
                    panel.render(panel.garage)
                panel.garage.search_players(query, answered)
            session = self.panel.session or self.panel.garage.session
            session.callback(0.3, search)
        self.panel.render(self.panel.garage)

    def key(self, event):
        import Keys
        if not event.isKeyDown():
            return
        if event.key == Keys.KEY_ESCAPE:
            if self.query or self.results:
                self.cancel()
            else:
                self.panel.cancel_edit()
        elif event.key == Keys.KEY_RETURN:
            if self.results:
                self.pick(max(0, self.active))
            else:
                self.panel.submit_edit()
        elif event.key == Keys.KEY_BACKSPACE:
            self.type(self.query[:-1])
        elif event.key in (getattr(Keys, 'KEY_DOWNARROW', None), getattr(Keys, 'KEY_UPARROW', None)):
            if self.results:
                delta = 1 if event.key == getattr(Keys, 'KEY_DOWNARROW', None) else -1
                self.active = (0 if delta > 0 else len(self.results) - 1) if self.active < 0 else (self.active + delta) % len(self.results)
        else:
            char = getattr(event, 'character', None)
            if char and len(self.entries) < 4:
                char = native_text(char)
                if all(not unicodedata.category(c).startswith('C') for c in char) and len(self.query) + len(char) <= 64:
                    self.type(self.query + char)
        self.panel.render(self.panel.garage)

    def fit(self, node, value, width):
        value = native_text(value)
        node.text = value
        while value and text_pixels(node)[0] > width:
            value = value[:-1]
            node.text = value + u'\u2026'

    def layout(self, width):
        y, actions = 0, []
        for index, ((row, name), (remove, remove_label)) in enumerate(zip(self.selected_rows, self.remove_buttons)):
            row.visible = remove.visible = index < len(self.entries)
            if not row.visible:
                continue
            row.width, row.height = width - 44, 34
            place(row, 0, y)
            self.fit(name, self.entries[index]['username'] or tr(u'Unavailable player'), row.width - 16)
            place(name, 8, 4)
            remove.width, remove.height = 36, 34
            place(remove, width - 36, y)
            caption(remove, remove_label, u'\u00d7')
            actions.append((remove, lambda i=index: self.remove(i)))
            y += 40
        self.field.width, self.field.height = width, 40
        place(self.field, 0, y)
        self.fit(self.query_label, self.query + u'|' if len(self.entries) < 4 else tr(u'Four players selected. Remove one to add another.'), width - 20)
        place(self.query_label, 10, 7)
        y += 46
        for index, (row, name) in enumerate(self.result_rows):
            row.visible = index < len(self.results)
            if not row.visible:
                continue
            row.width, row.height = width, 34
            place(row, 0, y)
            self.fit(name, self.results[index]['username'], width - 16)
            place(name, 8, 4)
            actions.append((row, lambda value=self.results[index]: self.choose(value)))
            if index == self.active:
                self.panel.styles[id(row)] = 'hover'
            y += 36
        self.status.text = tr(self.message or u'Type a player name, then choose a suggestion.')
        self.fit(self.status, self.status.text, width)
        place(self.status, 0, y)
        self.panel.input_box.height = y + text_pixels(self.status)[1]
        return actions
