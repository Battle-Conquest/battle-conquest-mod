"""Recovery requests stay bounded and belong to the active account and link."""
from checks.battle_fixtures import owned
from checks.common import check
from checks.report_sender import _Session, _Response


def check_quest_repairs():
    from battle_conquest.quest_repairs import Repairs
    from battle_conquest.destinations import Destination, battles_url

    session = _Session()
    account = type('Account', (object,), {'account': '500883375'})()
    destination = Destination(battles_url(), enabled=True, modes=['random'], secret='a' * 64)
    places = type('Places', (object,), {'current': destination})()
    garage = [True]
    asked = []
    delivered = []

    class Cache(object):
        def get(self, arena, callback):
            asked.append((arena, callback))

    repairs = Repairs(session, account, places, lambda *args: delivered.append(args),
                      garage=lambda: garage[0], cache=lambda: Cache())
    repairs.install()
    repairs.poll()
    check('recovery uses only the configured site and its secret',
          '/api/mod/quest-repairs?account_id=500883375&region=' in session.sent[0]['url']
          and session.sent[0]['headers'] == {'X-Mod-Secret': 'a' * 64})
    repairs.poll()
    check('one recovery poll in flight at a time', len(session.sent) == 1)
    response = {'repair_requests': [{'arena_unique_id': u'\u00b2'}, {'arena_unique_id': u'\u0661'},
                                    {'arena_unique_id': '1\n'}, {'arena_unique_id': '18446744073709551615'},
                                    {'arena_unique_id': '18446744073709551616'},
                                    {'arena_unique_id': 123}, {'arena_unique_id': '-1'}]}
    session.sent.pop(0)['answer'](_Response(200, response))
    check('uint64 arenas retain every digit and invalid arenas are refused',
          len(asked) == 1 and asked[0][0] == 18446744073709551615)
    asked.pop(0)[1](0, {'common': {}})
    check('a recovered result goes through normal capture', len(delivered) == 1)
    repairs.poll()
    session.sent.pop(0)['answer'](_Response(200, response))
    check('an unchanged absence is not requested forever', not asked)

    repairs.poll()
    account.account = '500999999'
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [{'arena_unique_id': '12'}]}))
    check('switching accounts in flight discards the response', not asked)
    repairs.poll()
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [{'arena_unique_id': '12'}]}))
    destination.secret = 'b' * 64
    asked.pop(0)[1](0, {'common': {}})
    check('changing the link discards a cache answer in flight', len(delivered) == 1)

    repairs.poll()
    garage[0] = False
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [{'arena_unique_id': '13'}]}))
    check('entering battle discards a poll response', not asked)
    repairs.poll()
    check('no network poll outside the garage', not session.sent)
    garage[0] = True
    destination.enabled = False
    repairs.poll()
    check('paused sending also pauses recovery', not session.sent)
    destination.enabled = True
    repairs.poll()
    session.sent.pop(0)['answer'](_Response(500))
    repairs.poll()
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': 'invalid'}))
    check('server errors and malformed responses do not reach the cache', not asked)
    repairs.poll()
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [], 'next_cursor': '12:34'}))
    repairs.poll()
    check('paging continues beyond earlier unrecoverable evidence', '&cursor=12:34' in session.sent[0]['url'])
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [], 'next_cursor': 'x&secret=leak'}))
    repairs.poll()
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [], 'next_cursor': '12:34\n'}))
    repairs.poll()
    check('an invalid cursor never becomes a query parameter', '&cursor=' not in session.sent[0]['url'])
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [{'arena_unique_id': str(i)} for i in range(1, 31)]}))
    check('each response queues at most twenty recovery requests', len(repairs._seen) <= 21)
    repairs.poll()
    check('a slow cache keeps its page instead of fetching work it could drop', not session.sent)
    # Every entry in this page gets its cache turn before the next page is polled.
    served = []
    while asked:
        arena, callback = asked.pop(0)
        served.append(arena)
        callback(0, {'common': {}})
    check('all twenty queued arenas get an attempt without eviction', served == list(range(1, 21)))
    repairs.poll()
    check('polling resumes once the previous page is drained', len(session.sent) == 1)

    # The site's repair can arrive after an earlier batch was acknowledged,
    # while the rest of that drain is still in flight.
    from checks.report_sender import _queue, _sender, _answer, HERE
    queue = _queue(count=51)
    sending, sender = _sender(queue)
    sender.drain()
    _answer(sending, 200, {'accepted': 50, 'results': [{'index': i, 'status': 'accepted'} for i in range(50)]})
    richer = dict(queue.all()[0])
    richer['quest_details'] = {'metrics': {'shots': 7}}
    queue.add(owned(richer))
    _answer(sending, 200, {'accepted': 1, 'results': [{'index': 0, 'status': 'accepted'}]})
    check('enrichment after acknowledgement survives the remaining backlog',
          len(queue.pending(HERE, ('ranked',))) == 1)
    sender.drain()
    check('the recovered fields leave in a new duplicate report',
          sending.sent[0]['body']['battles'][0]['quest_details']['metrics']['shots'] == 7)
    _answer(sending, 200, {'duplicates': 1, 'results': [{'index': 0, 'status': 'duplicate'}]})
    check('the completed report settles after its own acknowledgement', not queue.all())

    queue = _queue(count=51)
    queue.mark(HERE, ['1'], snapshots={'1': None}, account='500123456')
    richer = dict(queue.all()[0])
    richer['quest_details'] = {'metrics': {'shots': 7}}
    queue.add(owned(richer))
    sending, sender = _sender(queue)
    sender.drain()
    _answer(sending, 200, {'results': [{'index': i, 'status': 'rejected' if i == 0 else 'accepted'} for i in range(50)]})
    richer['quest_details']['metrics']['hits'] = 4
    queue.add(owned(richer))
    _answer(sending, 200, {'results': [{'index': 0, 'status': 'accepted'}]})
    check('a later rejection revokes the earlier permission to rearm', not queue.all())
