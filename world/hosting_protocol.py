"""Small shared hosted-API values; no host authority or platform-only imports."""
import json


class HostingError(Exception):
    """Fixed public error, independent of paths and submitted credentials."""
    def __init__(self, status=400, code='invalid_request'):
        self.status, self.code = status, code
        super().__init__(code)


def _json_object(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate key')
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique)
    if type(value) is not dict:
        raise ValueError('expected object')
    return value
