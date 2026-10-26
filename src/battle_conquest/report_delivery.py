"""Bounded delivery events; listeners never own or settle the report queue."""
import logging


class Delivery(object):
    def __init__(self):
        self.listeners = []

    def on_change(self, callback):
        self.listeners.append(callback)

    def emit(self, stage, target, batch, payload=None):
        event = {'stage': stage, 'url': target.url, 'account': batch[0].get('account'),
                 'proof': (target.headers or {}).get('X-Mod-Secret'),
                 'arenas': [report['arena_unique_id'] for report in batch], 'results': {}}
        if isinstance(payload, dict) and isinstance(payload.get('results'), list):
            for result in payload['results']:
                if not isinstance(result, dict):
                    continue
                index, status = result.get('index'), result.get('status')
                if (isinstance(index, (int, long)) and not isinstance(index, bool)
                        and 0 <= index < len(batch) and status in ('accepted', 'duplicate', 'rejected')):
                    event['results'][batch[index]['arena_unique_id']] = status
        for callback in list(self.listeners):
            try:
                callback(event)
            except Exception:
                logging.getLogger('battle_conquest.report_sender').exception('delivery listener failed')
