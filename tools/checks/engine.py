"""A fake BigWorld: callbacks that run when told to, and no network."""


class FakeBigWorld(object):
    """Scheduler that runs when told to, instead of on a frame clock."""

    def __init__(self):
        self.pending = {}
        # Handles of the responses this class queues itself (fetchURL), which
        # are the client's delivery rather than anything the mod scheduled.
        self.deliveries = set()
        self.fetched = []
        self._next = 1

    def callback(self, delay, func):
        handle = self._next
        self._next += 1
        self.pending[handle] = func
        return handle

    def cancelCallback(self, handle):
        self.pending.pop(handle, None)

    def player(self):
        """No player entity: the lobby, before any battle."""
        return None

    def fetchURL(self, url, callback, headers, timeout, method, postData):
        """No network: every request is answered as unreachable, deferred.

        Deferred the way the client delivers it, because code that accidentally
        depends on the response having already arrived would pass against a
        synchronous fake and deadlock against the game. The checks that need an
        answer use a fake session of their own.
        """
        self.fetched.append(url)
        self.deliveries.add(self.callback(0.0, lambda: callback(FakeResponse(0, ''))))

    def run_pending(self):
        """Fire everything queued right now, once."""
        due, self.pending = self.pending, {}
        for handle, func in sorted(due.items()):
            self.deliveries.discard(handle)
            func()

    @property
    def scheduled(self):
        """What the mod has queued: a response still on its way is the client's."""
        return dict((handle, func) for handle, func in self.pending.items()
                    if handle not in self.deliveries)


class FakeResponse(object):
    """The shape BigWorld hands back: a code, a body, and headers()."""

    def __init__(self, code, body):
        self.responseCode = code
        self.body = body

    def headers(self):
        return {}


class FakeEvent(object):
    """Stands in for a WG Event, and remembers who is attached."""

    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def __isub__(self, handler):
        if handler in self.handlers:
            self.handlers.remove(handler)
        return self
