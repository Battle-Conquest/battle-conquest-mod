"""Stand-ins for the client objects the mod hooks, keeping their real shapes."""

from checks.engine import FakeEvent


class FakeBattleResultsService(object):
    """The client's battle results service, as the capture sits on it.

    `postResult` is patched by the capture and must come back by identity when
    the mod stops: it is what the reload checks watch.
    """

    def __init__(self):
        self.onResultPosted = FakeEvent()

    def postResult(self, result, *args):
        return 'the client answer'


ORIGINAL_POST_RESULT = FakeBattleResultsService.__dict__['postResult']
