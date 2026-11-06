"""Versioned world gameplay policy, separate from all trainer saves."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import uuid

NAMES = ('partyEXP', 'reusableTMs', 'modernSplit', 'megaEvolution', 'expandedRoster')
MANIFEST = 'world-rules.json'


def settings(value):
    if type(value) is dict and set(value) == set(NAMES[:-1]):
        value = dict(value, expandedRoster=False)
    if type(value) is not dict or set(value) != set(NAMES) or any(type(v) is not bool for v in value.values()):
        raise ValueError('world rules require boolean settings with no unknown fields')
    if value['megaEvolution'] and not value['modernSplit']:
        raise ValueError('Mega Evolution requires modernSplit (modern physical/special split)')
    return dict(value)


def make(world_id=None, version=1, rules=None):
    rules = settings(dict.fromkeys(NAMES, False) if rules is None else rules)
    payload = dict(schema=1, world_id=world_id or uuid.uuid4().hex, version=version,
                   rules=rules, mask=sum(1 << i for i, k in enumerate(NAMES) if rules[k]))
    payload['digest'] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('ascii')).hexdigest()
    return payload


def validate(value):
    if (type(value) is not dict or set(value) != {'schema','world_id','version','rules','mask','digest'}
            or type(value['schema']) is not int or value['schema'] != 1
            or type(value['version']) is not int or not 1 <= value['version'] <= 2147483647
            or type(value['world_id']) is not str or not re.fullmatch('[0-9a-f]{32}', value['world_id'])
            or type(value['mask']) is not int):
        raise ValueError('invalid world rules manifest')
    expected = make(value['world_id'], value['version'], value['rules'])
    if value != expected:
        raise ValueError('world rules digest or mask mismatch')
    return expected


def publish(root, value):
    value = validate(value)
    root = Path(root)
    if root.resolve() != root:
        raise ValueError('world rules directory cannot contain symlinks')
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    target = root / MANIFEST
    if target.is_symlink():
        raise ValueError('world rules manifest cannot be a symlink')
    fd, temporary = tempfile.mkstemp(prefix='.rules-', dir=root)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(value, output, sort_keys=True, separators=(',', ':'))
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return value


def read(root, *, create=False):
    target = Path(root) / MANIFEST
    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        if not create:
            return None
        # Constructors may race before the single running authority acquires
        # its socket lock. Serialize migration so they all load one identity.
        import fcntl
        root = Path(root)
        if root.resolve() != root:
            raise ValueError('world rules directory cannot contain symlinks')
        root.mkdir(parents=True, mode=0o700, exist_ok=True)
        lock = os.open(root / '.world-rules.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(lock)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('invalid world rules lock')
            fcntl.flock(lock, fcntl.LOCK_EX)
            existing = read(root)
            return existing if existing is not None else publish(root, make())
        finally:
            os.close(lock)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 4096:
            raise ValueError('invalid world rules file')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate world rules field')
                result[key] = value
            return result
        return validate(json.loads(stream.read(4097), object_pairs_hook=unique))


def wire(value):
    value = validate(value)
    return f"{value['version']}:{value['mask']}:{value['digest']}"
