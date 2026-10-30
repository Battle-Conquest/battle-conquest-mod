"""Server repair ownership must survive missing/stale client login metadata."""
from checks.common import check
from checks.owner_isolation import fixture as capture_fixture, OTHER
from checks.battle_fixtures import ACCOUNT
from checks.recovery_review import fixture
from checks.report_sender import _Response


def check_repair_poll_origin():
    from battle_conquest.quest_repairs import Repairs
    for unavailable in (None, OTHER):
        player, places, queue, session, reports, sender = capture_fixture()
        requests, clock, cache, identity, path = fixture(context={'id': ACCOUNT, 'region': 'eu'})
        repairs = Repairs(session, player, places, reports.arrived, garage=lambda: True,
                          now=clock, context=lambda: identity, requests=requests)
        repairs.poll()
        # The request was authenticated for A. Direct client metadata can be
        # unavailable/stale when its response arrives while the tracker is A.
        identity['id'] = unavailable
        session.sent.pop()['answer'](_Response(200, {'repair_requests': [{'arena_unique_id': '91'}]}))
        check('server repair retains its authenticated poll owner despite current metadata: %r' % unavailable,
              ('eu', ACCOUNT, 91) in requests._journal.entries
              and ('eu', unavailable, 91) not in requests._journal.entries)
        clock.now += 5
        requests.drain()
        check('repair never asks another active login for A results', not cache.asked)
        identity['id'] = ACCOUNT
        requests.drain()
        check('repair resumes when its actual original login becomes available', cache.asked == [91])
