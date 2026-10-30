"""Follow the login for UI and delivery selection, retaining it during battle.

Result ownership is read independently from personal.accountDBID. This tracker
never supplies the owner of a captured result.
"""
import logging

_logger = logging.getLogger('battle_conquest.account')

# How often the account logged in is looked at, to follow a switch.
_ACCOUNT_SECONDS = 2.0


def current_account_id():
    """The account id the client is logged in with, or None (a battle, the login screen)."""
    try:
        import BigWorld
        account_id = getattr(BigWorld.player(), 'databaseID', None)
    except Exception:
        return None
    return str(account_id) if account_id else None


class Account(object):
    """The account last seen logged in, and who wants to hear when it changes."""

    def __init__(self, session, account_id=current_account_id):
        self._session = session
        self._account_id = account_id
        self._account = None
        self._listeners = []

    @property
    def account(self):
        return self._account

    def on_change(self, callback):
        self._listeners.append(callback)

    def install(self):
        self._follow()
        self._session.repeat(_ACCOUNT_SECONDS, self._follow)

    def _follow(self):
        account = self._account_id()
        if not account or account == self._account:
            return
        self._account = account
        _logger.info('account %s logged in', account)
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                _logger.exception('an account listener failed')


def install(session):
    account = Account(session)
    account.install()
    return account
