"""Replace local JSON only after a complete write, keeping the previous copy."""
import errno
import json
import os


def save_json(path, payload):
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    temporary = path + '.tmp'
    with open(temporary, 'wb') as handle:
        json.dump(payload, handle)
        handle.flush()
        os.fsync(handle.fileno())
    # Python 2 on Windows cannot rename over an existing file. A backup keeps
    # the previous complete copy recoverable if the process stops in between.
    backup = path + '.bak'
    if os.path.exists(path):
        if os.path.exists(backup):
            os.remove(backup)
        os.rename(path, backup)
    os.rename(temporary, path)


def load_json(path):
    try:
        with open(path, 'rb') as handle:
            return json.load(handle)
    except (IOError, OSError) as problem:
        if getattr(problem, 'errno', None) != errno.ENOENT:
            raise
        with open(path + '.bak', 'rb') as handle:
            return json.load(handle)
