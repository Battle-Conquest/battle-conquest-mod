"""A client event that refuses detachment cannot write from a closed load."""
import sys

from checks.common import check
from checks.engine import FakeEvent
from checks.owner_isolation import fixture, raw
from checks.battle_fixtures import ACCOUNT, Bonus


class StickyEvent(FakeEvent):
    def __isub__(self, handler):
        raise RuntimeError('client refuses event detachment')

    def fire(self, *args):
        for handler in list(self.handlers):
            handler(*args)


def check_closed_session_recovery():
    from battle_conquest.recovery_journal import Journal
    from battle_conquest.results_request import Requests
    from battle_conquest.runtime.session import Session
    previous = sys.modules.get('constants')
    sys.modules['constants'] = type('Constants', (), {'ARENA_BONUS_TYPE': Bonus})()
    try:
        player, places, queue, unused, reports, sender = fixture()
        session = Session(0)
        reports._session = session
        path = queue._store + '.recovery'
        old = Requests(session, reports.arrived, context=lambda: {'id': ACCOUNT, 'region': 'eu'},
                       journal=Journal(path), captured=queue.captured)
        old.remember(91)
        def report_saved(report):
            key = (report['owner']['region'], report['account'], long(report['arena_unique_id']))
            if queue.captured(key):
                old.complete(key)
        reports.on_capture(report_saved)
        retained_post = reports._wrap_post(lambda *args: 'client result')
        event = StickyEvent()
        session.subscribe(event, reports._from_account)
        session.close()
        # A fresh load has added work not known by the closed load's copies.
        current = Journal(path)
        current.add(('eu', ACCOUNT, 92), 1000, 1005)
        event.fire(raw(arena=91))
        check('undetachable event from a closed load cannot overwrite the new recovery journal',
              ('eu', ACCOUNT, 92) in Journal(path).entries and not queue.all())
        outcome = retained_post(None, raw(arena=91))
        check('patch retained beneath another mod still delegates without writing from a closed load',
              outcome == 'client result' and ('eu', ACCOUNT, 92) in Journal(path).entries and not queue.all())
        active = Session(1)
        received = []
        active.subscribe(event, lambda value: received.append(value))
        event.fire('current event')
        check('guarded events still forward normally to the active session', received == ['current event'])
        active.close()
        event.fire('late event')
        check('all closed subscriptions remain inert even when client detachment fails', received == ['current event'])
    finally:
        if previous is None:
            sys.modules.pop('constants', None)
        else:
            sys.modules['constants'] = previous
