"""Expire cached objectives using the clock supplied with the snapshot."""
import calendar
import time


def utc_timestamp(value):
    if isinstance(value, basestring):
        try:
            return calendar.timegm(time.strptime(value, '%Y-%m-%d %H:%M:%S'))
        except (ValueError, OverflowError):
            pass
    return None


def deadlines(data):
    result = {}
    for row in data['choices']:
        deadline = utc_timestamp(row.get('expires_at'))
        if deadline is not None:
            result[row['key']] = deadline
    return result


def expire(data, pending, server_now):
    expired = {key for key, deadline in pending.iteritems() if deadline <= server_now}
    if not expired:
        return data

    for key in expired:
        del pending[key]
    shown = dict(data, choices=[row for row in data['choices'] if row['key'] not in expired])
    if data['config']['selection'] in expired:
        shown.update(selection_hidden=True, automatic_selection=None)
    if (data.get('selected') or {}).get('key') in expired:
        shown.update(selected=None, criteria=[], players=[], tracking=None, period=None)
    return shown
