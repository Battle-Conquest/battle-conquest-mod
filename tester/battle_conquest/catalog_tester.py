"""Manual catalogue upload, for the private tester build only.

The normal release never contains this module. Installation creates UI and
notification actions; only a deliberate click reads the catalogue or sends it.
"""
import json
import logging

from battle_conquest import catalog_source
from battle_conquest.account import current_account_id
from battle_conquest.destinations import BATTLES_PATH, valid_url
from battle_conquest.garage_ready import garage_ready
from battle_conquest.notices import push

_logger = logging.getLogger('battle_conquest.catalog_tester')
ACTION = 'battle_conquest.collect_catalogue'
BUTTON = 'collectCatalogue'
_MAX_BYTES = 2097152
_RETRIES = (5.0, 30.0, 120.0)


class Collector(object):
    def __init__(self, session, account, places, version, changed=lambda: None,
                 garage=garage_ready, current=current_account_id,
                 source=catalog_source.vehicles, client_version=catalog_source.game_version,
                 notify=push):
        self.session, self.account, self.places = session, account, places
        self.version, self.changed = version, changed
        self.garage, self.current = garage, current
        self.source, self.client_version, self.notify = source, client_version, notify
        self.status = 'Private tester: catalogue collection is manual. Nothing collected this session.'
        self.busy = False
        self._identity = None
        self._sequence = 0
        self._entries, self._iterator, self._body = [], None, None
        self._attempt = 0
        self._game_version = None
        session.on_close(self.close)
        account.on_change(self._account_changed)
        # Polling at retry time misses pause/resume or unlink/relink in between.
        # Invalidate immediately when the existing link actually changes.
        for name in ('set_enabled', 'forget', 'remember'):
            if callable(getattr(places, name, None)):
                session.patch(places, name, self._wrap_link_change)

    def _wrap_link_change(self, original):
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            if self.busy and self.identity() != self._identity:
                self.cancel()
            return result
        return changed

    def identity(self):
        target = self.places.current
        account = self.current()
        if (not account or account != self.account.account or target is None
                or not target.enabled or not target.secret or not valid_url(target.url)
                or not target.url.endswith(BATTLES_PATH)):
            return None
        return (account, target.url, target.secret)

    def _say(self, message, finished=False):
        self.status = message
        self.changed()
        if finished:
            self.notify('Battle-Conquest TESTER: ' + message)

    def _account_changed(self):
        if self.busy:
            self.cancel()

    def cancel(self):
        self.close()
        self._say('Collection cancelled. Any upload already submitted still requires admin review.', True)

    def close(self):
        self._sequence += 1
        self.busy = False
        self._entries, self._iterator, self._body, self._identity = [], None, None, None

    def start(self):
        if self.busy:
            return
        identity = self.identity()
        if not self.session.alive or not self.garage() or identity is None:
            self._say('Load the garage and link the current account with sending enabled first.', True)
            return
        self._sequence += 1
        self._identity, self.busy, self._attempt = identity, True, 0
        try:
            self._game_version = self.client_version()
            self._iterator = iter(self.source())
        except Exception:
            self._fail()
            return
        self._entries = []
        self._say('Collecting the full client catalogue...')
        self._later(0.0, self._read)

    def _later(self, delay, callback):
        sequence = self._sequence
        def guarded():
            if self.session.alive and self.busy and sequence == self._sequence:
                callback()
        self.session.callback(delay, guarded)

    def _ready(self):
        if self.identity() != self._identity:
            self.cancel()
            return False
        return self.garage()

    def _read(self):
        if not self._ready():
            if self.busy:
                self._later(2.0, self._read)
            return
        try:
            for unused in range(25):
                self._entries.append(next(self._iterator))
                if len(self._entries) > catalog_source.MAX_VEHICLES:
                    raise ValueError('catalogue too large')
        except StopIteration:
            try:
                self._prepare()
            except Exception:
                self._fail()
            return
        except Exception:
            self._fail()
            return
        self._say('Collecting catalogue: %s vehicles read.' % len(self._entries))
        self._later(0.0, self._read)

    def _prepare(self):
        from battle_conquest import config
        if not self._entries:
            raise ValueError('empty catalogue')
        self._body = json.dumps({'schema': 2,
            'account': {'id': int(self._identity[0]), 'region': config.REGION},
            'client': {'mod': 'battle-conquest-catalog-tester', 'version': self.version,
                       'game_version': self._game_version},
            'fingerprint': catalog_source.fingerprint(self._entries),
            'vehicles': sorted(self._entries, key=lambda v: v['tank_id'])}, separators=(',', ':'))
        if len(self._body) > _MAX_BYTES:
            raise ValueError('catalogue payload too large')
        self._send()

    def _send(self):
        if not self._ready():
            if self.busy:
                self._later(2.0, self._send)
            return
        identity, sequence = self._identity, self._sequence
        url = identity[1][:-len(BATTLES_PATH)] + '/api/mod/vehicle-catalog'
        self._say('Sending %s vehicles for admin review...' % len(self._entries))
        def answered(response):
            if not self.busy or sequence != self._sequence:
                return
            if self.identity() != identity:
                self.cancel()
                return
            code = getattr(response, 'responseCode', 0)
            try:
                payload = json.loads(response.body)
            except (AttributeError, TypeError, ValueError):
                payload = None
            if (code == 200 and isinstance(payload, dict) and payload.get('schema') == 2
                    and type(payload.get('count')) is int and payload['count'] == len(self._entries)
                    and type(payload.get('duplicate')) is bool):
                message = ('Catalogue already received; no extra proposal.' if payload['duplicate'] else
                           '%s vehicles received. Admin validation is still required.' % payload['count'])
                self.close()
                self._say(message, True)
                return
            temporary = code in (0, 408, 429) or code >= 500 or code == 200
            if temporary and self._attempt < len(_RETRIES):
                delay = _RETRIES[self._attempt]
                if code == 429:
                    try:
                        delay = max(delay, min(3600.0, float(response.headers().get('Retry-After', 3600))))
                    except (AttributeError, TypeError, ValueError):
                        delay = 3600.0
                self._attempt += 1
                self._say('Upload unavailable (HTTP %s); retrying in %s seconds.' % (code, int(delay)))
                self._later(delay, self._send)
                return
            reason = payload.get('error', 'invalid_response') if isinstance(payload, dict) else 'invalid_response'
            # Server codes are shown only when they match the protocol's ASCII alphabet.
            if not isinstance(reason, basestring) or not reason.replace('_', '').isalnum() or len(reason) > 64:
                reason = 'invalid_response'
            self.close()
            self._say('Upload stopped (HTTP %s, %s). Click Collect to retry manually.' % (code, reason), True)
        try:
            self.session.fetch(url, answered, headers={'X-Mod-Secret': identity[2], 'Content-Type': 'application/json'},
                               method='POST', post_data=self._body, timeout=30.0)
        except Exception:
            self._fail()

    def _fail(self):
        _logger.warning('private catalogue collection failed; no partial catalogue is sent', exc_info=True)
        self.close()
        self._say('Catalogue unavailable or invalid. No partial catalogue was sent. See tester documentation.', True)


def install(session, account, places, page, version):
    from battle_conquest.catalog_tester_ui import install as install_ui
    collector = Collector(session, account, places, version)
    install_ui(session, collector, page)
    return collector
