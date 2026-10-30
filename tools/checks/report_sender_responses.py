"""Malformed diagnostic fields must not interrupt final delivery verdicts."""
from checks.common import check
from checks.report_sender import _queue, _sender, _answer, _took


def check_report_sender_responses():
    from battle_conquest.report_sender import BATCH
    from battle_conquest.report_wire import rejections

    for reason in (17, True, ['bounds:xp'], {'code': 'bounds:xp'}, None, ''):
        queue = _queue(count=BATCH + 1)
        session, sender = _sender(queue)
        sender.drain()
        broken = False
        try:
            _answer(session, 200, {'accepted': 0, 'duplicates': 0, 'rejected': BATCH,
                    'results': [{'index': i, 'status': 'rejected', 'reason': reason} for i in range(BATCH)]})
        except (TypeError, ValueError):
            broken = True
        check('a malformed rejection code cannot stall the remaining backlog: %r' % reason,
              not broken and len(session.sent) == 1)
        _answer(session, 200, _took(1))
        check('the sender releases its in-flight gate and settles the final verdicts',
              not sender._busy and not queue.all())
        sender.drain()
        check('a malformed diagnostic never rearms a rejected battle', not session.sent)
    codes = rejections({'results': [None, {'status': 'accepted', 'reason': 'ignored'},
            {'status': 'rejected', 'reason': 'bounds:xp', 'message': 'private details'},
            {'status': 'rejected', 'reason': 'bounds:xp'}, {'status': 'rejected', 'reason': {'code': 'nested'}}]})
    check('diagnostic codes stay distinct strings and never expose messages or structured values', codes == ['bounds:xp', 'unknown'])
