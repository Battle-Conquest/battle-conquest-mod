"""Regression cases from the complete #954 review."""
import copy
import json
import os

from checks.battle_fixtures import Bonus
from checks.common import REPO, check


def check_quest_review():
    from battle_conquest.quest_details import details_of
    from checks.report_sender import _queue, _sender, _answer, _took, OTHER_ACCOUNT

    with open(os.path.join(REPO, 'tools', 'checks', 'fixtures', 'mod_quest_observations.json')) as handle:
        raw = copy.deepcopy(json.load(handle)[0])
    raw['personal']['99999'] = None
    details = details_of(raw, Bonus)
    check('an unreadable vehicle cannot turn a partial list into a complete one', 'vehicles' not in details)
    check('unreadable vehicles prevent a partial total being claimed', 'metrics' not in details)
    check('readable vehicle observations remain available', len(details['vehicle_observations']) == 1)

    queue = _queue(count=51)
    session, sender = _sender(queue)
    sender.drain()
    sender._account.account = OTHER_ACCOUNT
    _answer(session, 200, _took(50))
    check('switching accounts in flight stops the remaining backlog', not session.sent)
    check('the old account keeps its unsent battle', len(queue.all()) == 1 and not sender._busy)

    queue = _queue(count=51)
    session, sender = _sender(queue)
    sender.drain()
    sender._destinations.all()[0].secret = 'c' * 64
    _answer(session, 200, _took(50))
    check('changing the link in flight stops requests under the old credential', not session.sent)

    queue = _queue(count=51)
    session, sender = _sender(queue)
    sender.drain()
    sender._garage = lambda: False
    _answer(session, 200, _took(50))
    check('a new battle stops garage-only backlog transmission', not session.sent and len(queue.all()) == 1)
