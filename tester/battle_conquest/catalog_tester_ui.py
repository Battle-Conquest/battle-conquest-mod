"""Tester UI layered onto existing settings and native notification actions."""
from battle_conquest import settings_window, notices
from battle_conquest.catalog_tester import ACTION, BUTTON


def install(session, collector, page):
    # Without the optional settings window, native notices are the only status UI.
    collector.notify_progress = not page.available
    # Detach the bound callbacks while their identities still match the API's list.
    if page.available:
        page._unregister()
    original_name = settings_window.NAME
    settings_window.NAME = 'Battle-Conquest TESTER (private catalogue)'
    session.on_close(lambda: setattr(settings_window, 'NAME', original_name))

    def changed():
        if page.available:
            page._state = None
            page._check_state()
    collector.changed = changed

    def wrap_template(original):
        def template(state, templates=None):
            result = original(state, templates)
            if templates is None:
                from gui.modsSettingsApi import templates
            result['column2'] += [templates.createLabel('PRIVATE TESTER - manual catalogue upload'),
                settings_window._button_line(templates, collector.status, BUTTON,
                                             'Collect' if not collector.busy else 'Cancel')]
            return result
        return template

    def wrap_button(original):
        def clicked(window, linkage, var_name, value=None):
            if window is page and linkage == settings_window.LINKAGE and var_name == BUTTON:
                collector.cancel() if collector.busy else collector.start()
                return
            return original(window, linkage, var_name, value)
        return clicked

    session.patch(settings_window, 'template', wrap_template)
    session.patch(settings_window.SettingsWindow, '_on_button', wrap_button)
    # Existing API subscriptions hold a bound method: refresh them after patching.
    changed()
    holder = notices._actions_handlers()
    if holder is not None:
        def wrap_action(original):
            def handle(handlers, *args, **kwargs):
                if kwargs.get('actionName', args[-1] if args else None) == ACTION:
                    collector.cancel() if collector.busy else collector.start()
                    return None
                return original(handlers, *args, **kwargs)
            return handle
        session.patch(holder, 'handleAction', wrap_action)

    def announce():
        if not session.alive:
            return
        if not collector.garage():
            session.callback(5.0, announce)
            return
        if holder is not None:
            shown = notices.push('Battle-Conquest TESTER: catalogue collection is manual. '
                                 '<a href="event:%s">Collect and send catalogue</a>' % ACTION)
        else:
            shown = notices.push('Battle-Conquest TESTER: open mod settings to collect the catalogue manually.')
        if not shown:
            session.callback(5.0, announce)
    session.callback(5.0, announce)
