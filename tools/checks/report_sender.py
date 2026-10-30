"""Checks for the sending half: who is owed what, and what a refusal costs.

Nothing here reaches the network. A fake session records what would have gone
out and hands back the answer each check wants, which is the only way to
exercise a refusal: a real server can be asked for a 500 exactly never.
"""

import json
import os
import tempfile

from checks.battle_fixtures import ACCOUNT, Player
from checks.battle_fixtures import owned
from checks.common import check

OTHER_ACCOUNT = '500999999'

HERE = 'https://battle-conquest.com/api/mod/battles'
THERE = 'https://example.org/in'

SECRET = 'a' * 64
OTHER_SECRET = 'b' * 64


class _Session(object):
    """Records what would have been sent, and answers when a check says so."""

    def __init__(self):
        self.sent = []

    def fetch(self, url, callback, headers=None, timeout=10.0, method='GET', post_data=''):
        self.sent.append({'url': url, 'headers': headers or {}, 'method': method,
                          'body': json.loads(post_data) if post_data else None,
                          'answer': callback})

    def callback(self, delay, func):
        pass

    def repeat(self, interval, func):
        pass

    def subscribe(self, event, handler):
        # The real Session also remembers the pair so a reload can take it off
        # again; what a check needs is only that the handler reaches the event.
        event += handler


class _Response(object):

    def __init__(self, code, payload=None, body=None):
        self.responseCode = code
        self.body = body if body is not None else json.dumps(payload or {})


def _answer(session, code, payload=None, body=None):
    """Answer the oldest request still waiting, as the client would."""
    request = session.sent.pop(0)
    if payload is not None and isinstance(payload.get('results'), list):
        import copy
        payload = copy.deepcopy(payload)
        for result in payload['results']:
            if isinstance(result, dict) and 'arena_unique_id' not in result:
                result['arena_unique_id'] = request['body']['battles'][result['index']]['arena_unique_id']
    request['answer'](_Response(code, payload, body))
    return request


def _took(count, rejected=0):
    """What a destination answers for a batch it processed."""
    return {'schema': 1, 'accepted': count - rejected, 'duplicates': 0, 'rejected': rejected,
            'results': [dict(index=i, status='rejected' if i < rejected else 'accepted',
                             reason='bounds:damage_dealt' if i < rejected else '') for i in range(count)]}


def _places(*destinations):
    """Stands in for destinations.Destinations; the sender only reads all()."""
    return type('Places', (object,), {'all': lambda self: list(destinations)})()


def _destination(url=HERE, modes=('ranked', ), enabled=True, secret=SECRET, label=None, account=ACCOUNT):
    from battle_conquest.destinations import Destination
    destination = Destination(url=url, label=label or url, enabled=enabled, modes=modes, secret=secret)
    destination.owner = ('eu', account) if account else None
    return destination


def _queue(store=None, count=1, mode='ranked', account=ACCOUNT, first=1):
    from battle_conquest.report_queue import Queue
    queue = Queue(store=store or os.path.join(tempfile.mkdtemp(), 'q.json'))
    for index in range(count):
        queue.add(owned({'arena_unique_id': str(first + index), 'mode': mode,
                   'finished_at': '2026-09-25T18:10:00Z', 'outcome': 'win',
                   'survived': True, 'metrics': {'xp': 1420}, 'account': account}))
    return queue


def _sender(queue, places=None, secret=SECRET, account=ACCOUNT, refused=None):
    """A sender over this queue, linked to the site unless `places` says otherwise."""
    from battle_conquest.report_sender import Sender
    if places is None:
        places = _places(_destination(secret=secret, account=account))
    session = _Session()
    sender = Sender(session, Player(account), queue=queue,
                    destinations=places, version='1.2.3', garage=lambda: True,
                    refused_store=refused or os.path.join(tempfile.mkdtemp(), 'refused.json'))
    return session, sender


def check_report_sender_targets():
    _, sender = _sender(_queue())
    targets = sender.targets()
    check('the linked site is the one destination', [target.url for target in targets] == [HERE])
    check('it is owed the modes it asked for', targets[0].modes == ('ranked', ))
    check('it is proven by the secret drawn for it', targets[0].headers == {'X-Mod-Secret': SECRET})

    # An unlinked client sends nothing: a report proven by nobody could name
    # anybody, and its battles are not kept for it either.
    _, unlinked = _sender(_queue(), secret=None)
    check('an unlinked site is owed nothing', unlinked.targets() == [])
    check('so no mode is owed anywhere', unlinked.owed()['ranked'] == [])

    _, paused = _sender(_queue(), _places(_destination(enabled=False)))
    check('a paused site is owed nothing', paused.targets() == [])

    # The rule the capture keeps has to be the rule here, or the mod would keep
    # battles nobody wants, or throw away battles somebody does.
    check('a ranked battle is owed to the site', sender.owed()['ranked'] == [HERE])
    check('a random battle to nobody', sender.owed()['random'] == [])


def check_report_sender_payload():
    from battle_conquest.report_sender import wire

    queue = _queue(count=1)
    _, sender = _sender(queue)
    body = json.loads(sender.payload(queue.all()))

    check('the batch names its contract version', body['schema'] == 1)
    check('and which mod sent it', body['client']['mod'] == 'battle-conquest-mod' and body['client']['version'] == '1.2.3')
    # An integer, as the contract asks: the account id is small enough for one
    # and a string there would be a second shape to accept.
    check('the account travels as a number', body['account']['id'] == int(ACCOUNT))
    check('with the realm this client plays on', body['account']['region'] in
          ('eu', 'na', 'asia'))
    check('one battle makes one entry', len(body['battles']) == 1)

    battle = body['battles'][0]
    # The whole reason the capture keeps it as a string: past 2^53 a JSON number
    # comes back a float with its low-order digits gone.
    check('the arena id stays a string of digits', battle['arena_unique_id'] == '1')
    check('the counters ride along as they were captured', battle['metrics']['xp'] == 1420)
    check('survival is a real boolean', battle['survived'] is True)

    # The queue keeps two things of its own; neither is the site's business.
    kept = dict(queue.all()[0], sent=[HERE])
    check('which account played it does not travel', 'account' not in wire(kept))
    check('nor does where else it was sent', 'sent' not in wire(kept))
    check('and what does is exactly the contract',
          sorted(wire(kept)) == ['arena_unique_id', 'finished_at', 'metrics', 'mode',
                                 'outcome', 'owner', 'survived'])
    # Optional, so absent above: when the capture read a tank, it travels too.
    check('the tank played travels when it is known',
          wire(dict(kept, vehicle={'tank_id': 8721}))['vehicle'] == {'tank_id': 8721})


def check_report_sender_delivery():
    store = os.path.join(tempfile.mkdtemp(), 'q.json')
    queue = _queue(store=store, count=2)
    # Two destinations, although the mod only ever has one: the sender settles a
    # battle once every destination owed it has taken it, and that rule is only
    # visible with two.
    session, sender = _sender(queue, _places(_destination(), _destination(url=THERE)))

    sender.drain()
    check('a drain sends to the first destination', len(session.sent) == 1)
    first = _answer(session, 200, _took(2))
    check('it posts', first['method'] == 'POST')
    check('to the battles endpoint', first['url'] == HERE)
    check('and carries both battles', len(first['body']['battles']) == 2)

    check('the next destination is sent to once the first has answered', len(session.sent) == 1)
    second = _answer(session, 200, _took(2))
    check('and it is sent the same two battles', len(second['body']['battles']) == 2)
    check('the two destinations are not the same one', first['url'] != second['url'])

    check('a battle every destination has taken leaves the queue', queue.all() == [])
    check('and it is gone from the file too', _queue(store=store, count=0).all() == [])
    check('a second drain has nothing to send', sender.drain() is None and session.sent == [])

    # A rejection is as final as an acceptance: asking again would only ask the
    # same question, and the answer is stored on the far side either way.
    rejected = _queue(count=1)
    session, sender = _sender(rejected)
    sender.drain()
    _answer(session, 200, _took(1, rejected=1))
    check('a rejected battle is not offered again', rejected.all() == [])

    # 200 means the batch was processed, whatever the body turns out to be.
    unreadable = _queue(count=1)
    session, sender = _sender(unreadable)
    sender.drain()
    _answer(session, 200, body='<html>a proxy said hello</html>')
    check('an answer we cannot read retains the batch', len(unreadable.all()) == 1)

    # A refusal must not be read as a withdrawal: unlike a site the player
    # paused, one that refused still wants the battles, so they stay queued.
    pending = _queue(count=1)
    session, sender = _sender(pending, _places(_destination(), _destination(url=THERE)))
    sender.drain()
    _answer(session, 404)
    _answer(session, 200, _took(1))
    check('a destination that refused is still owed its battles',
          any(HERE in urls for urls in sender.owed().values()))
    check('so a battle one destination took but the other refused stays queued',
          len(pending.all()) == 1)


def check_report_sender_account():
    queue = _queue(count=1)
    queue.add(owned({'arena_unique_id': '77', 'mode': 'ranked', 'account': OTHER_ACCOUNT,
               'finished_at': '2026-09-25T18:10:00Z', 'outcome': 'win',
               'survived': True, 'metrics': {'xp': 1}}))
    session, sender = _sender(queue)

    sender.drain()
    sent = _answer(session, 200, _took(1))
    # A machine two people play on holds both their battles. Sending one
    # account's under the other's proof is how a report lands on the wrong
    # player, which makes every number computed from it wrong rather than late.
    check('only the account logged in has its battles sent',
          [battle['arena_unique_id'] for battle in sent['body']['battles']] == ['1'])
    check('the other account keeps its own, waiting for its turn',
          [report['arena_unique_id'] for report in queue.all()] == ['77'])

    # Nothing to prove and nobody to attribute: a drain with no account logged
    # in must not send the queue under whoever is next to log in.
    session, nobody = _sender(_queue(count=1), account=None)
    nobody.drain()
    check('nothing is sent while nobody is logged in', session.sent == [])


def check_report_sender_refusals():
    from battle_conquest.report_sender import retry_later

    check('no answer at all is worth asking again', retry_later(None))
    check('so is a server that is down', retry_later(503))
    check('so is a quota', retry_later(429))
    # A player can renew a revoked secret without restarting the client, so this
    # one heals itself rather than waiting for a restart.
    check('a rejected secret is worth asking again later', retry_later(401))
    check('a payload it could not read is not', not retry_later(400))
    check('an endpoint that does not exist is not', not retry_later(404))

    # Kept, in every case: the battles are still true, and a link renewed or an
    # endpoint deployed makes them sendable again.
    for code in (500, 429, 401, 404, 400):
        queue = _queue(count=1)
        session, sender = _sender(queue)
        sender.drain()
        _answer(session, code)
        check('a batch refused with HTTP %d stays in the queue' % code, len(queue.all()) == 1)

    # What changes is how soon it is asked again.
    queue = _queue(count=1)
    session, sender = _sender(queue)
    sender.drain()
    _answer(session, 503)
    sender.drain()
    check('a destination that is down is left alone for a while', session.sent == [])

    queue = _queue(count=1)
    session, sender = _sender(queue)
    sender.drain()
    _answer(session, 404)
    sender.drain()
    check('a destination with no battle endpoint is not asked again this session',
          session.sent == [])

    # The refused batch on disk: the shape of a report is a contract between
    # this mod, a client nobody here controls and a server elsewhere, and the
    # batch is the only thing that says which of the three was wrong.
    refused = os.path.join(tempfile.mkdtemp(), 'refused.json')
    session, sender = _sender(_queue(count=1), refused=refused)
    sender.drain()
    _answer(session, 400)
    with open(refused) as handle:
        kept = json.load(handle)
    check('a batch it could not read is kept on disk', kept['code'] == 400)
    check('and what is kept is what was sent',
          kept['battles'][0]['arena_unique_id'] == '1' and 'account' not in kept['battles'][0])

    # A network failure is not a diagnosis, and overwriting the one file with it
    # would throw away the batch someone has to look at.
    absent = os.path.join(tempfile.mkdtemp(), 'none.json')
    session, sender = _sender(_queue(count=1), refused=absent)
    sender.drain()
    _answer(session, None)
    check('an unreachable destination writes no diagnosis', not os.path.exists(absent))

    # A missing endpoint never read the batch, so the batch says nothing about
    # which side was wrong. The queue already remembers the battles and the log
    # already names the fault; a copy of the player's battles on disk for an
    # address that does not answer is a copy nobody needs.
    for code in (404, 405, 410):
        missing = os.path.join(tempfile.mkdtemp(), 'none.json')
        session, sender = _sender(_queue(count=1), refused=missing)
        sender.drain()
        _answer(session, code)
        check('HTTP %d is about the address, so no batch is written down' % code,
              not os.path.exists(missing))


def check_report_sender_batching():
    from battle_conquest.report_sender import BATCH

    queue = _queue(count=BATCH + 5)
    session, sender = _sender(queue)
    sender.drain()
    check('a backlog is sent in batches, not in one request', len(session.sent) == 1)
    first = _answer(session, 200, _took(BATCH))
    check('and a batch is the contract\'s ceiling', len(first['body']['battles']) == BATCH)
    check('the rest follows once the first is answered', len(session.sent) == 1)
    rest = _answer(session, 200, _took(5))
    check('and it carries what was left', len(rest['body']['battles']) == 5)
    check('the whole backlog is settled', queue.all() == [])

    # A destination that stopped taking them must not hold up the next one.
    queue = _queue(count=BATCH + 5)
    session, sender = _sender(queue, _places(_destination(url=THERE), _destination()))
    sender.drain()
    _answer(session, 500)
    check('a failure stops the rest of that destination\'s backlog', len(session.sent) == 1)
    served = _answer(session, 200, _took(BATCH))
    check('but the next destination is still served', served['url'] == HERE)
    check('and its own backlog carries on', len(session.sent) == 1)


class _Event(object):
    """A client event, in the only shape the mod uses: `+=` and `-=`."""

    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def __isub__(self, handler):
        if handler in self.handlers:
            self.handlers.remove(handler)
        return self

    def fire(self):
        for handler in list(self.handlers):
            handler()


class _Account(object):
    def __init__(self, event):
        self.onAccountBecomePlayer = event


def check_report_sender_startup():
    """Battles left on disk leave at the next garage, not at the next timer.

    A client that was killed mid-session comes back with its queue on disk. The
    drain is skipped outside the garage and before the account is known, so the
    one shot 20s after start is a guess that a slow start loses -- and losing it
    used to mean five minutes with the battles sitting there. The event is the
    answer; the timers stay as the net under it.
    """
    from battle_conquest import report_sender as module

    event = _Event()
    before = module.service_hooks.account_events
    module.service_hooks.account_events = lambda: _Account(event)
    try:
        session, sender = _sender(_queue(count=2), places=_places(_destination()))
        sender.install()
        check('the sender follows the account becoming the player', len(event.handlers) == 1)
        check('and nothing is sent before it does', not session.sent)
        event.fire()
        check('the battles on disk leave as soon as it does', len(session.sent) == 1)
        check('and they are the ones that were waiting',
              len(session.sent[0]['body']['battles']) == 2)
    finally:
        module.service_hooks.account_events = before

    # A client that does not announce it must still send, on the tick alone.
    module.service_hooks.account_events = lambda: None
    try:
        session, sender = _sender(_queue(count=1), places=_places(_destination()))
        sender.install()
        check('a client with no such event still installs', sender is not None)
        check('and sends nothing until a tick', not session.sent)
    finally:
        module.service_hooks.account_events = before


def check_report_sender_status():
    """What the settings page reads off the sender: the last batch and the queue."""
    queue = _queue(count=2)
    queue.add(owned({'arena_unique_id': '77', 'mode': 'ranked', 'account': OTHER_ACCOUNT,
               'finished_at': '2026-09-25T18:10:00Z', 'outcome': 'win',
               'survived': True, 'metrics': {'xp': 1}}))
    session, sender = _sender(queue)
    changes = []
    sender.on_change(lambda: changes.append(1))

    check('nothing has been sent at first', sender.last_sent is None and sender.last_result is None)
    check('the battles waiting are those of the account logged in', sender.waiting() == 2)

    sender.drain()
    _answer(session, 200, {'schema': 1, 'accepted': 1, 'duplicates': 1, 'rejected': 0, 'results': [{'index': 0, 'status': 'accepted'}, {'index': 1, 'status': 'duplicate'}]})
    check('a batch answered is remembered', sender.last_sent is not None)
    check('with what the site made of it',
          sender.last_result == {'code': 200, 'battles': 2, 'accepted': 1, 'duplicates': 1,
                                 'rejected': 0})
    check('the page is told once the drain is over', changes == [1])
    check('and nothing of this account waits any more', sender.waiting() == 0)

    queue = _queue(count=1)
    session, sender = _sender(queue)
    sender.drain()
    _answer(session, 503)
    check('a refusal is remembered as well', sender.last_result == {'code': 503, 'battles': 1})
    check('and the battle still waits', sender.waiting() == 1)

    _, nobody = _sender(_queue(count=1), account=None)
    check('with nobody logged in, nothing is said to wait', nobody.waiting() == 0)
