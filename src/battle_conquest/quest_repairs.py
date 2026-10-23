"""Retry missing quest evidence, once per arena and active link in this load.

The site lists only this account's missing fields. A cache answer goes through
the normal capture and its missing-only server merge; no score is invented here.
"""
import logging
import re
import time

from battle_conquest import config
from battle_conquest.destinations import battles_url
from battle_conquest.report_sender import answer, at_garage, account_number
from battle_conquest.results_request import Requests, results_cache

_logger = logging.getLogger('battle_conquest.quest_repairs')


class Repairs(object):

    def __init__(self, session, account, places, deliver, garage=at_garage,
                 cache=results_cache, now=time.time):
        self._session = session
        self._account = account
        self._places = places
        self._deliver = deliver
        self._garage = garage
        self._cache = cache
        self._now = now
        self._key = None
        self._requests = None
        self._seen = set()
        self._poll = None
        self._polled_at = 0
        self._cursor = None

    def install(self):
        self._session.repeat(60.0, self.poll)
        self._session.repeat(20.0, self.drain)

    def identity(self):
        current = self._places.current
        account = getattr(self._account, 'account', None)
        if (not self._garage() or account_number(account) is None or current is None
                or not current.enabled or not current.secret or not current.modes
                or current.url != battles_url()):
            return None
        return (account, current.url, current.secret)

    def drain(self):
        if self._requests is not None and self.identity() == self._key:
            self._requests.drain()

    def poll(self):
        key = self.identity()
        if key is None:
            return
        if key != self._key:
            self._key = key
            self._seen = set()
            self._poll = None
            self._cursor = None

            def active():
                return self.identity() == key

            def deliver(results, source):
                if active():
                    self._deliver(results, source)

            self._requests = Requests(self._session, deliver, garage=active, cache=self._cache)
        if self._poll is not None and self._now() - self._polled_at < 60.0:
            return
        ticket = object()
        self._poll = ticket
        self._polled_at = self._now()

        def answered(response):
            if self._poll is not ticket:
                return
            self._poll = None
            if self.identity() != key:
                return
            if getattr(response, 'responseCode', None) != 200:
                return
            payload = answer(response)
            requests = (payload or {}).get('repair_requests')
            if not isinstance(requests, list):
                return
            cursor = (payload or {}).get('next_cursor')
            self._cursor = cursor if isinstance(cursor, basestring) and re.match(r'^\d{1,19}:\d{1,19}$', cursor) else None
            for request in requests[:20]:
                arena = request.get('arena_unique_id') if isinstance(request, dict) else None
                if not isinstance(arena, basestring) or not arena.isdigit() or len(arena) > 20:
                    continue
                arena = long(arena)
                if arena < 1 or arena > 18446744073709551615 or arena in self._seen:
                    continue
                self._seen.add(arena)
                _logger.info('retrying missing quest evidence for battle %s', arena)
                self._requests.remember(arena)
            self.drain()

        url = (config.SITE.rstrip('/') + '/api/mod/quest-repairs?account_id=%s&region=%s'
               % (account_number(key[0]), config.REGION))
        if self._cursor is not None:
            url += '&cursor=' + self._cursor
        self._session.fetch(url, answered,
                            headers={'X-Mod-Secret': key[2]}, timeout=config.API_TIMEOUT)


def install(session, account, places, deliver):
    repairs = Repairs(session, account, places, deliver)
    repairs.install()
    return repairs
