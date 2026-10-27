"""One provisional battle, replaced only by the site's stored receipt.

This never adds local counters to an official total and never awards a quest.
Capture hooks schedule their work on the next frame, outside native callbacks.
"""
import copy


_RETRIEVAL_SECONDS = 60.0


def in_battle():
    """A server transfer is not a battle, even while no account is the player."""
    try:
        from helpers import isPlayerAvatar
        return bool(isPlayerAvatar())
    except Exception:
        return False


class Feedback(object):
    def __init__(self, session, garage, reports, sender, requests, battle=in_battle):
        self.session, self.garage, self.sender, self.requests = session, garage, sender, requests
        self.in_battle = battle
        self.key = garage.identity()
        self.report = self.receipt = None
        self.stage = None
        self.scheduled = None
        self.send_pending = False
        self.was_in_battle = False
        self.retrieval_until = 0.0
        reports.on_capture(self.captured)
        sender.delivery.on_change(self.delivered)
        garage.feedback = self

    def current(self):
        key = self.garage.identity()
        if key != self.key:
            self.key, self.report, self.receipt, self.stage = key, None, None, None
            self.was_in_battle = False
            self.retrieval_until = 0.0
            self.scheduled, self.send_pending = None, False
        return key is not None

    def arena(self):
        return self.report['arena_unique_id'] if self.current() and self.report else None

    def captured(self, report):
        if not self.current() or report.get('account') != self.key[0]:
            return
        if self.report is not None:
            if (report.get('finished_at', ''), len(report['arena_unique_id']), report['arena_unique_id']) < (
                    self.report.get('finished_at', ''), len(self.report['arena_unique_id']), self.report['arena_unique_id']):
                return
            if report['arena_unique_id'] == self.report['arena_unique_id']:
                return
        self.report, self.receipt = copy.deepcopy(report), None
        self.retrieval_until = 0.0
        self.stage = 'queued'
        self.wake(send=True)

    def wake(self, send=False):
        self.send_pending = self.send_pending or send
        if self.scheduled:
            return
        ticket = self.scheduled = object()
        key = self.key
        def run():
            # A previous account/link callback must not consume a newer send,
            # even when the player has since switched back to the same key.
            if not self.current() or key != self.key or self.scheduled is not ticket:
                return
            self.scheduled = None
            send, self.send_pending = self.send_pending, False
            self.garage.tick()
            if send:
                self.sender.drain()
        self.session.callback(0.0, run)

    def delivered(self, event):
        if (not self.current() or event['account'] != self.key[0]
                or event['url'] != self.key[1] or event['proof'] != self.key[2]):
            return
        # Restored or older batches still change the official totals, even
        # when this session has no matching provisional last-battle card.
        if event['stage'] == 'answered':
            self.garage.refresh_after_delivery()
            self.wake()
        if not self.report or self.arena() not in event['arenas']:
            return
        if event['stage'] == 'answered':
            self.stage = 'rejected' if event['results'].get(self.arena()) == 'rejected' else 'confirming'
        else:
            self.stage = event['stage']
        self.wake()

    def accept(self, data):
        if not self.current() or not self.report:
            return
        receipt = data.get('receipt')
        if (not isinstance(receipt, dict) or receipt.get('arena_unique_id') != self.arena()
                or receipt.get('status') not in ('accepted', 'rejected')
                or not isinstance(receipt.get('mode'), basestring)
                or not isinstance(receipt.get('totals'), dict)
                or not all(isinstance(v, (int, long)) and not isinstance(v, bool)
                           for v in receipt['totals'].values())):
            return
        self.receipt = copy.deepcopy(receipt)
        self.stage = 'received' if receipt['status'] == 'accepted' else 'rejected'

    def snapshot(self):
        if not self.current():
            return None
        if self.in_battle():
            self.was_in_battle = True
        elif self.garage.garage() and self.was_in_battle:
            self.was_in_battle = False
            if self.receipt is not None:
                self.report = self.receipt = None
                self.stage = None
            if self.report is None:
                self.retrieval_until = self.garage.now() + _RETRIEVAL_SECONDS
        if self.report is None:
            return {'stage': 'retrieving'} if self.garage.now() < self.retrieval_until or self.requests.busy() else None
        totals = dict(self.report.get('metrics') or {})
        totals.update((self.report.get('quest_details') or {}).get('metrics') or {})
        totals['wins'] = int(self.report.get('outcome') == 'win')
        return {'stage': self.stage, 'source': 'site' if self.receipt is not None else 'local',
                'mode': self.receipt['mode'] if self.receipt is not None else self.report['mode'],
                'totals': self.receipt['totals'] if self.receipt is not None else totals}
