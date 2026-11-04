"""Private, cold hosted snapshots. Never stops a service or prints state/secrets."""
import argparse
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tarfile


MAX_BYTES = 4 * 1024**3
MAX_MEMBERS = 100000


def safe_path(value):
    """Reject symlinks in every existing component, including ancestors."""
    path = Path(value)
    if '..' in path.parts:
        raise ValueError('unsafe path')
    path = path.absolute()
    for part in reversed((path, *path.parents)):
        if part.is_symlink():
            raise ValueError('symlink refused')
    return path


def regular(path):
    path = safe_path(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('regular unlinked file required')
    return path


def lock_file(stack, path):
    # Existing locks only: never invent an authority root or replace a lock inode.
    path = regular(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    handle = stack.enter_context(os.fdopen(fd, 'rb'))
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise ValueError('authority is live; cold snapshot refused') from None


def backup(root, cert, key, archive):
    root, archive = safe_path(root), safe_path(archive)
    cert, key = regular(cert), regular(key)
    if not root.is_dir() or archive.is_relative_to(root):
        raise ValueError('unsafe snapshot paths')
    if not (root/'hosting.sqlite3').is_file():
        raise ValueError('existing hosting root required')
    created = False
    with ExitStack() as stack:
        lock_file(stack, root/'hosting.lock')
        # Also exclude standalone WorldServer processes using any managed root.
        for path in sorted(root.glob('worlds/*/world.lock')):
            lock_file(stack, path)
        entries = []
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in sorted(dirs + files):
                path = safe_path(Path(directory)/name)
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    continue
                relative = path.relative_to(root)
                if stat.S_ISSOCK(info.st_mode) and (
                        len(relative.parts) == 4 and relative.parts[0] == 'worlds'
                        and relative.parts[2:] == ('transport', 'world.sock')
                        or len(relative.parts) == 3 and relative.parts[0] == 'worlds'
                        and relative.parts[2] == 'admin.sock'):
                    continue
                regular(path)
                entries.append((path, 'root/'+relative.as_posix()))
        entries.extend(((cert, 'tls/cert.pem'), (key, 'tls/key.pem')))
        if len(entries) > MAX_MEMBERS or sum(p.stat().st_size for p, _ in entries) > MAX_BYTES:
            raise ValueError('snapshot exceeds bounded archive limits')
        try:
            fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            created = True
            with os.fdopen(fd, 'wb') as output:
                with tarfile.open(fileobj=output, mode='w') as bundle:
                    for path, name in entries:
                        info = bundle.gettarinfo(str(path), arcname=name)
                        info.uid = info.gid = 0
                        info.uname = info.gname = ''
                        info.mode = 0o600
                        # Recheck before opening. Operator must exclude other filesystem writers.
                        regular(path)
                        with path.open('rb') as source:
                            bundle.addfile(info, source)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            if created:
                archive.unlink()
            raise
    return {'ok': True, 'kind': 'cold-hosted-backup', 'files': len(entries)}


def restore(archive, destination):
    archive, destination = regular(archive), safe_path(destination)
    if destination.exists():
        raise ValueError('restore requires a NEW destination')
    with tarfile.open(archive, 'r:') as bundle:
        members = []
        names = set()
        size = 0
        for item in bundle:
            path = PurePosixPath(item.name)
            if (len(members) >= MAX_MEMBERS or not item.isfile() or path.is_absolute()
                    or '..' in path.parts or item.name != path.as_posix()
                    or len(path.parts) < 2 or path.parts[0] not in ('root', 'tls')
                    or (path.parts[0] == 'tls' and item.name not in ('tls/cert.pem', 'tls/key.pem'))
                    or item.name in names or item.size < 0):
                raise ValueError('unsafe archive')
            size += item.size
            if size > MAX_BYTES:
                raise ValueError('archive exceeds bounded restore limit')
            names.add(item.name)
            members.append(item)
        if not {'root/hosting.sqlite3', 'root/hosting.lock', 'tls/cert.pem', 'tls/key.pem'} <= names:
            raise ValueError('incomplete hosted archive')
        destination.mkdir(mode=0o700)
        try:
            for item in members:
                target = destination/item.name
                parent = destination
                for part in PurePosixPath(item.name).parts[:-1]:
                    parent = parent/part
                    parent.mkdir(mode=0o700, exist_ok=True)
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                source = bundle.extractfile(item)
                if source is None:
                    os.close(fd)
                    raise ValueError('missing archive file')
                with os.fdopen(fd, 'wb') as output, source:
                    shutil.copyfileobj(source, output)
            for path in (destination/'root').rglob('*.sqlite3'):
                with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
                    if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                        raise ValueError('SQLite integrity failure')
        except BaseException:
            shutil.rmtree(destination)
            raise
    return {'ok': True, 'kind': 'hosted-restore', 'files': len(members)}


def health(root):
    """Sample existing private admin inspect sockets. Never starts an authority."""
    import re
    from .client import admin_request
    root = safe_path(root)
    database = regular(root/'hosting.sqlite3')
    with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as db:
        ids = [row[0] for row in db.execute('SELECT id FROM worlds')]
        endpoint = json.loads(db.execute("SELECT value FROM config WHERE key='endpoint'").fetchone()[0])
    if len(ids) > 16 or any(not isinstance(i, str) or not re.fullmatch('[0-9a-f]{16}', i) for i in ids):
        raise ValueError('invalid hosted registry')
    running = False
    with regular(root/'hosting.lock').open('rb') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            running = True
    connected = capacity = unavailable = 0
    for world_id in ids:
        try:
            socket = safe_path(root/'worlds'/world_id/'admin.sock')
            report = admin_request(root/'worlds'/world_id/'transport/world.sock',
                                   {'command': 'inspect'}, timeout=2, admin_path=socket)
            players = report['players']
            limit = report['capacity']['players']
            if report.get('ok') is not True or not isinstance(players, list) or type(limit) is not int:
                raise ValueError('invalid inspect response')
            connected += len(players)
            capacity += limit
        except (OSError, ValueError, KeyError, TypeError):
            unavailable += 1
    return dict(ok=running and unavailable == 0, authority_locked=running,
                registered_worlds=len(ids), port_capacity=endpoint[3]-endpoint[2]+1,
                connected_players=connected, player_capacity=capacity,
                unavailable_worlds=unavailable)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    command = actions.add_parser('backup')
    for name in ('root', 'cert', 'key', 'archive'):
        command.add_argument('--'+name, required=True)
    command = actions.add_parser('restore')
    command.add_argument('--archive', required=True)
    command.add_argument('--destination', required=True)
    command = actions.add_parser('health')
    command.add_argument('--root', required=True)
    args = vars(parser.parse_args(argv))
    action = args.pop('action')
    try:
        result = {'backup': backup, 'restore': restore, 'health': health}[action](**args)
    except (OSError, ValueError, TypeError, KeyError, IndexError, sqlite3.Error, tarfile.TarError):
        print(json.dumps({'ok': False, 'error': 'operation refused or failed'}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
