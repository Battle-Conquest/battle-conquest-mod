"""Recovery requests stay bounded and belong to the active account and link."""
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
    response = {'repair_requests': [{'arena_unique_id': '18446744073709551615'},
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
    check('an invalid cursor never becomes a query parameter', '&cursor=' not in session.sent[0]['url'])
    session.sent.pop(0)['answer'](_Response(200, {'repair_requests': [{'arena_unique_id': str(i)} for i in range(1, 31)]}))
    check('each response queues at most twenty recovery requests', len(repairs._seen) <= 21)
