"""Pure wire projection and response reading shared with the sender checks.

Kept separate so backlog ownership/lifecycle stays readable in report_sender.
The sender re-exports these helpers for its existing callers.
"""
import json

FIELDS = ('arena_unique_id', 'mode', 'finished_at', 'outcome', 'survived', 'vehicle', 'metrics', 'quest_details')


def wire(report):
    """One report as it travels: the contract's fields, and nothing else.

    The queue holds two things of its own alongside them -- which account
    played the battle, and which destinations have already taken it. Both are
    this machine's bookkeeping and neither is any destination's business.
    """
    return dict((field, report[field]) for field in FIELDS if field in report)


def account_number(value):
    """A Wargaming account id as the contract wants it, an integer, or None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def answer(response):
    """A destination's answer as a dict, or None when it cannot be read."""
    try:
        payload = json.loads(response.body)
    except (AttributeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def rejections(payload):
    """The distinct reasons a batch was rejected for, for one log line.

    The codes, never the messages: a reason is a stable machine code where the
    message beside it is written for whoever is reading a server log.
    """
    results = payload.get('results')
    if not isinstance(results, list):
        return []
    reasons = []
    for result in results:
        if not isinstance(result, dict) or result.get('status') != 'rejected':
            continue
        reason = result.get('reason') or 'unknown'
        if reason not in reasons:
            reasons.append(reason)
    return reasons


