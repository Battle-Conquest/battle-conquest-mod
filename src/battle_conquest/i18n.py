"""Site account language, scoped to the current game account and link."""
import logging

from battle_conquest.translations_fr import MESSAGES

_logger = logging.getLogger('battle_conquest.i18n')
_language = 'en'
_scope = None
_identity = None
_listeners = []


def locale():
    global _scope, _language
    scope = _identity() if _identity is not None else _scope
    if scope != _scope:
        changed = _language != 'en'
        _scope, _language = scope, 'en'
        if changed:
            _changed()
    return _language


def tr(message):
    return MESSAGES.get(message, message) if locale() == 'fr' else message


def variants(message):
    return (message, MESSAGES.get(message, message))


def accept(payload, account, secret):
    global _language
    locale()
    if (not isinstance(payload, dict) or payload.get('language') not in ('fr', 'en')
            or not account or not secret or payload.get('account_id') != str(account)
            or (_identity is not None and _identity() != (str(account), secret))):
        return False
    if payload['language'] == _language:
        return False
    _language = payload['language']
    _logger.info('site account language: %s', _language)
    _changed()
    return True


def _changed():
    for callback in list(_listeners):
        try:
            callback()
        except Exception:
            _logger.exception('language listener failed')


def on_change(session, callback):
    _listeners.append(callback)
    session.on_close(lambda: _listeners.remove(callback) if callback in _listeners else None)


def install(session, account, places):
    global _identity, _scope, _language
    def identity():
        destination = places.current
        return (str(getattr(account, 'account', None)), destination.secret if destination else None)
    _identity, _scope, _language = identity, identity(), 'en'
    def close():
        global _identity, _scope, _language
        _identity, _scope, _language = None, None, 'en'
    session.on_close(close)
