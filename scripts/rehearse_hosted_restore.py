#!/usr/bin/env python3
"""Private, offline activation-archive rehearsal. Never installs a service."""
import argparse
import hashlib
import json
import shlex
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import threading
import time
import stat
import tarfile

MAX_ENTRIES = 100000
MAX_BYTES = 4 * 1024**3
PREFIXES = ('var/lib/emerald-hosted', 'var/lib/emerald-world',
            'etc/systemd/system/emerald-hosted.service',
            'etc/systemd/system/emerald-hosted.service.d',
            'etc/systemd/system/emerald-world.service',
            'etc/systemd/system/emerald-world.service.d',
            'etc/emerald-hosted.conf', 'etc/apparmor.d/emerald-bwrap')


def safe_path(path):
    """Reject symlink ancestors, including a dangling final link."""
    path = Path(path).absolute()
    if '..' in path.parts:
        raise ValueError('unsafe local path')
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('symlink local path')
    return path


def extract_private(archive, destination, expected_sha256=None):
    archive, destination = safe_path(archive), safe_path(destination)
    parent = destination.parent
    if destination.parts[1] in ('var', 'etc', 'opt', 'usr', 'proc', 'sys', 'dev', 'run'):
        raise ValueError('live destination forbidden')
    if destination.exists() or not parent.is_dir():
        raise ValueError('destination must be fresh')
    metadata = parent.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ValueError('parent must be owned and mode 0700')
    fd = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as source:
        metadata = os.fstat(source.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600):
            raise ValueError('archive must be private owned regular file')
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError('archive hash mismatch')
        source.seek(0)
        with tarfile.open(fileobj=source, mode='r:*') as tar:
            entries, names, total = [], {}, 0
            for entry in tar:
                name = entry.name
                parts = name.split('/')
                if (name.startswith('/') or any(p in ('', '.', '..') for p in parts)
                        or '\\' in name or '\x00' in name
                        or not any(name == prefix or name.startswith(prefix + '/') for prefix in PREFIXES)
                        or name in names or not (entry.isfile() or entry.isdir())
                        or entry.issparse() or entry.size < 0):
                    raise ValueError('unsafe archive member')
                names[name] = entry
                entries.append(entry)
                total += entry.size
                if len(entries) > MAX_ENTRIES or total > MAX_BYTES:
                    raise ValueError('archive exceeds limits')
            for name in names:
                if any(str(p) in names and not names[str(p)].isdir()
                       for p in PurePosixPath(name).parents):
                    raise ValueError('archive path collision')
            destination.mkdir(mode=0o700)
            count = 0
            try:
                for entry in entries:
                    target = destination / entry.name
                    directories = entry.name if entry.isdir() else str(PurePosixPath(entry.name).parent)
                    current = destination
                    for component in PurePosixPath(directories).parts:
                        current = current / component
                        current.mkdir(mode=0o700, exist_ok=True)
                    if entry.isfile():
                        stream = tar.extractfile(entry)
                        if stream is None:
                            raise ValueError('missing member body')
                        out = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                        with os.fdopen(out, 'wb') as output, stream:
                            shutil.copyfileobj(stream, output, 1024 * 1024)
                        count += 1
            except BaseException:
                shutil.rmtree(destination)
                raise
    return {'files': count, 'archive_sha256': digest, 'archive_entries': len(entries)}


def mapped(root, original):
    """Map only explicit archive-relative configuration paths, never live paths."""
    path = PurePosixPath(original)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('invalid configuration path')
    target = root / str(path).lstrip('/')
    safe_path(target)
    if not target.exists():
        raise ValueError('configuration target missing from archive')
    return target


def topology(root, service):
    """Accept only an explicit metadata grammar, not arbitrary systemd semantics."""
    try:
        return _topology(root, service)
    except (ValueError, KeyError, OSError, UnicodeError):
        raise ValueError('unsupported service topology metadata') from None


def endpoint(value):
    host, port = value.rsplit(':', 1)
    if not host or not all(c.isalnum() or c in '.-_' for c in host):
        raise ValueError('invalid endpoint')
    if not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError('invalid endpoint')
    return host, int(port)


def _topology(root, service):
    prefixes = {'emerald-hosted': ['/usr/bin/python3', '-m', 'world.hosting', 'start'],
                'emerald-world': ['/usr/bin/python3', '-m', 'world.server']}
    prefix = prefixes[service]
    unit = root / 'etc/systemd/system' / (service + '.service')
    paths = [unit] + sorted(unit.with_name(unit.name + '.d').glob('*.conf'))
    # These describe launch policy only. The rehearsal does not replay it.
    allowed = {'Unit': {'Description', 'After', 'Wants', 'Requires'},
               'Install': {'WantedBy'},
               'Service': {'Type', 'User', 'Group', 'WorkingDirectory', 'ExecStart',
                           'EnvironmentFile', 'Restart', 'RestartSec', 'TimeoutStopSec',
                           'UMask', 'StateDirectory', 'StateDirectoryMode',
                           'NoNewPrivileges', 'PrivateTmp', 'ProtectSystem', 'ProtectHome',
                           'ReadWritePaths', 'RestrictAddressFamilies', 'LimitNOFILE', 'TasksMax'}}
    seen, values = set(), {}
    for path in paths:
        section = None
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith(('#', ';')):
                continue
            if any(c in line for c in ('\\', '%', '\x00')):
                raise ValueError('unsupported escaping or substitution')
            if line.startswith('[') and line.endswith(']'):
                section = line[1:-1]
                if section not in allowed:
                    raise ValueError('unsupported section')
                continue
            key, value = line.split('=', 1)
            if section not in allowed or key not in allowed[section] or not value:
                raise ValueError('unsupported assignment')
            identity = section, key
            if identity in seen:
                raise ValueError('repeated or overridden assignment')
            seen.add(identity)
            if section == 'Service':
                values[key] = value
    if values.get('Type', 'simple') != 'simple':
        raise ValueError('unsupported service type')
    cwd = values['WorkingDirectory']
    if not cwd.startswith('/opt/emerald-world/') or any(p in ('', '.', '..') for p in cwd.split('/')[1:]):
        raise ValueError('invalid deployment reference')
    env = {}
    if 'EnvironmentFile' in values:
        if service != 'emerald-hosted' or values['EnvironmentFile'] != '/etc/emerald-hosted.conf':
            raise ValueError('unsupported environment file')
        for line in mapped(root, values['EnvironmentFile']).read_text().splitlines():
            if not line.strip() or line.startswith('#'):
                continue
            key, value = line.split('=', 1)
            if key != 'EMERALD_HOST' or key in env:
                raise ValueError('unsupported environment assignment')
            tokens = shlex.split(value)
            if len(tokens) != 1:
                raise ValueError('unsupported environment value')
            # ${NAME} is one systemd argument, not shell word splitting.
            # Only a literal hostname is supported, so substitution cannot
            # manufacture a different option vector in this bounded parser.
            endpoint(tokens[0] + ':1')
            env[key] = tokens[0]
    command = values['ExecStart']
    if '${EMERALD_HOST}' in command:
        command = command.replace('${EMERALD_HOST}', env['EMERALD_HOST'])
    if any(c in command for c in ('$', ';', '\n')):
        raise ValueError('unsupported command substitution')
    tokens = shlex.split(command)
    if tokens[:len(prefix)] != prefix:
        raise ValueError('unsupported command')
    required = {'--cert', '--key'}
    if service == 'emerald-hosted':
        required |= {'--root', '--advertise-host', '--port-start', '--port-end', '--max-worlds',
                     '--management-advertise', '--listen'}
        optional = {'--game-listen-host'}
        flags = set()
    else:
        required |= {'--state-dir', '--listen', '--advertise'}
        optional = {'--max-players', '--max-controls', '--connection-headroom'}
        flags = {'--require-existing-state'}
    options = {}
    args = iter(tokens[len(prefix):])
    for key in args:
        if key in options or key not in required | optional | flags:
            raise ValueError('unsupported or repeated option')
        value = True if key in flags else next(args, '')
        if not value or (isinstance(value, str) and value.startswith('-')):
            raise ValueError('missing option value')
        options[key] = value
    if not required <= options.keys():
        raise ValueError('missing required option')
    for key in ('--cert', '--key', '--root', '--state-dir'):
        if key in options:
            value = options[key]
            base = '/var/lib/emerald-hosted/' if service == 'emerald-hosted' else '/var/lib/emerald-world/'
            if not value.startswith(base) or any(p in ('', '.', '..') for p in value.split('/')[1:]):
                raise ValueError('unsupported state path')
    bounds = {'--port-start': (1, 65535), '--port-end': (1, 65535), '--max-worlds': (1, 16),
              '--max-players': (1, 64), '--max-controls': (0, 128), '--connection-headroom': (2, 64)}
    for key, (low, high) in bounds.items():
        if key in options:
            value = options[key]
            if not value.isascii() or not value.isdecimal() or not low <= int(value) <= high:
                raise ValueError('invalid numeric option')
    for key in ('--listen', '--advertise', '--management-advertise'):
        if key in options:
            endpoint(options[key])
    if service == 'emerald-hosted':
        start, end = int(options['--port-start']), int(options['--port-end'])
        if start > end or end - start + 1 > 16 or int(options['--max-worlds']) > end - start + 1:
            raise ValueError('invalid port capacity')
        endpoint(options['--advertise-host'] + ':1')
        if options.get('--game-listen-host', '127.0.0.1') not in ('127.0.0.1', '0.0.0.0'):
            raise ValueError('unsupported listen host')
        if ('--listen' in options) != ('--management-advertise' in options):
            raise ValueError('incomplete management endpoint')
        if '--listen' in options and endpoint(options['--listen'])[1] != endpoint(options['--management-advertise'])[1]:
            raise ValueError('conflicting management port')
    elif endpoint(options['--listen'])[1] != endpoint(options['--advertise'])[1]:
        raise ValueError('conflicting standalone port')
    values['options'] = options
    return values


def connect_ro(path):
    return sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)


def tls_pin(cert, key):
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        return hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
    except Exception:
        raise ValueError('TLS identity validation failed') from None


def verify_offline(root):
    """Validate restored bytes without importing or executing restored content."""
    root = safe_path(root)
    if (len(root.parts) < 3 or root.parts[1] in
            ('var', 'etc', 'opt', 'usr', 'proc', 'sys', 'dev', 'run')):
        raise ValueError('live root forbidden')
    if root.stat().st_uid != os.getuid() or stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise ValueError('restored root must be private and owned')
    for path in root.rglob('*'):
        if path.is_symlink() or (path.is_file() and path.stat().st_nlink != 1):
            raise ValueError('restored tree contains links')
    try:
        databases = list(root.rglob('*.sqlite3'))
        if not databases:
            raise ValueError('no SQLite state')
        for path in databases:
            with connect_ro(path) as db:
                if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError('SQLite integrity failed')
                if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
                    raise ValueError('SQLite foreign key check failed')
        hosted = topology(root, 'emerald-hosted')
        solo = topology(root, 'emerald-world')
        opts = hosted['options']
        state = mapped(root, opts['--root'])
        cert, key = mapped(root, opts['--cert']), mapped(root, opts['--key'])
        pin = tls_pin(cert, key)
        registry_endpoint = [opts['--advertise-host'], pin, int(opts['--port-start']), int(opts['--port-end'])]
        with connect_ro(state / 'hosting.sqlite3') as db:
            stored = json.loads(db.execute("SELECT value FROM config WHERE key='endpoint'").fetchone()[0])
            if stored != registry_endpoint:
                raise ValueError('TLS or endpoint registry mismatch')
            worlds = db.execute('SELECT id, port FROM worlds').fetchall()
            members = db.execute('SELECT world, trainer, token FROM members').fetchall()
            if len(worlds) > int(opts['--max-worlds']):
                raise ValueError('world capacity mismatch')
            for world, port in worlds:
                if not (len(world) == 16 and all(c in '0123456789abcdef' for c in world)
                        and registry_endpoint[2] <= port <= registry_endpoint[3]):
                    raise ValueError('world topology mismatch')
                path = state / 'worlds' / world / 'world.sqlite3'
                if not path.is_file():
                    raise ValueError('registered world missing')
                with connect_ro(path) as world_db:
                    for wid, trainer, token in members:
                        if wid == world and world_db.execute(
                                'SELECT token FROM identities WHERE id=?', (trainer,)).fetchone() != (token,):
                            raise ValueError('world credential mismatch')
        sopts = solo['options']
        standalone_state = mapped(root, sopts['--state-dir'])
        standalone_db = standalone_state / 'world.sqlite3'
        if not standalone_state.is_dir() or not standalone_db.is_file():
            raise ValueError('standalone state database missing')
        with connect_ro(standalone_db) as db:
            db.execute('SELECT id, token FROM identities LIMIT 1').fetchall()
        solo_port = endpoint(sopts['--listen'])[1]
        management_port = endpoint(opts.get('--listen', '127.0.0.1:8766'))[1]
        if (registry_endpoint[2] <= solo_port <= registry_endpoint[3]
                or registry_endpoint[2] <= management_port <= registry_endpoint[3]
                or solo_port == management_port):
            raise ValueError('service port collision')
        if len({port for _, port in worlds}) != len(worlds) or len({wid for wid, _ in worlds}) != len(worlds):
            raise ValueError('duplicate world topology')
        tls_pin(mapped(root, sopts['--cert']), mapped(root, sopts['--key']))
        metadata = sorted((root / 'etc').rglob('*'))
        digest = hashlib.sha256()
        for path in metadata:
            if path.is_file():
                digest.update(str(path.relative_to(root)).encode())
                digest.update(path.read_bytes())
        # References are not source code. This archive excludes /opt entirely.
        return dict(sqlite_integrity_checks=len(databases), foreign_keys_consistent=True,
                    hosted_worlds=len(worlds), hosted_members=len(members),
                    tls_registry_pin_consistent=True, standalone_tls_key_matches=True,
                    service_topology_consistent=True, configuration_sha256=digest.hexdigest(),
                    original_source_bundled=False,
                    source_references_sha256=hashlib.sha256(json.dumps(
                        [hosted['WorkingDirectory'], solo['WorkingDirectory']]).encode()).hexdigest())
    except (KeyError, IndexError, TypeError, sqlite3.Error, OSError):
        raise ValueError('offline state or topology validation failed') from None


def authenticate(root, port, pin, trainer, token, index):
    import socket
    from world.transport import ClientBroker
    broker = ClientBroker(root / ('c' + str(index)) / 'world.sock',
                          ('127.0.0.1', port), fingerprint=pin).start()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(5)
            client.connect(str(broker.socket_path))
            # Full current rules support preserves operator policy. Never disable
            # rules or remove admission restrictions to make a rehearsal pass.
            client.sendall(f'HELLO 1 {trainer} {token} SOCIALRULES3\n'.encode('ascii'))
            with client.makefile('rb') as stream:
                welcome = stream.readline(1025)
            fields = welcome.decode('ascii').strip().split()
            if (not welcome.endswith(b'\n') or len(welcome) > 1024
                    or len(fields) != 4 or fields[:3] != ['WELCOME', '1', trainer]):
                raise ValueError('restored credential authentication failed')
    finally:
        broker.close()


def authority_child(root, original_namespace):
    """Run local service code, never archived service executables.

    Restored persisted mechanics may execute through the existing bubblewrap
    runtime during ticks. They are not covered by the local service-code hash.
    """
    if os.readlink('/proc/self/ns/net') == original_namespace:
        raise ValueError('refusing active network namespace')
    import socket
    if {name for _, name in socket.if_nameindex()} != {'lo'}:
        raise ValueError('namespace has non-loopback interfaces')
    if any(line.strip() and not line.startswith('Iface')
           for line in Path('/proc/self/net/route').read_text().splitlines()):
        raise ValueError('namespace has external routes')
    subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True, capture_output=True)
    # Validate before starting any authority, even in an isolated namespace.
    root = safe_path(root)
    verify_offline(root)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from world.hosting import HostedWorldManager
    from world.server import WorldServer
    from world.transport import HostBroker
    hosted, solo = topology(root, 'emerald-hosted'), topology(root, 'emerald-world')
    ho, so = hosted['options'], solo['options']
    # Additional copies let runtime migrations affect only a disposable private tree.
    with tempfile.TemporaryDirectory(prefix='er-') as temp:
        temp = Path(temp)
        hroot, sroot = temp / 'h', temp / 's'
        shutil.copytree(mapped(root, ho['--root']), hroot)
        shutil.copytree(mapped(root, so['--state-dir']), sroot)
        cert, key = mapped(root, ho['--cert']), mapped(root, ho['--key'])
        with connect_ro(hroot / 'hosting.sqlite3') as db:
            credentials = db.execute('SELECT world, trainer, token FROM members').fetchall()
            ports = dict(db.execute('SELECT id, port FROM worlds').fetchall())
            account_count = db.execute('SELECT count(*) FROM accounts').fetchone()[0]
        with connect_ro(sroot / 'world.sqlite3') as db:
            standalone_credentials = db.execute('SELECT id, token FROM identities').fetchall()
        manager = HostedWorldManager(hroot, cert=cert, key=key,
            advertise_host=ho['--advertise-host'], listen_host='127.0.0.1',
            port_start=int(ho['--port-start']), port_end=int(ho['--port-end']),
            max_worlds=int(ho['--max-worlds']))
        try:
            if len(manager.running) != len(ports):
                raise ValueError('not all registered worlds restored')
            for i, (wid, trainer, token) in enumerate(credentials):
                authenticate(temp, ports[wid], manager.pin, trainer, token, i)
            scert, skey = mapped(root, so['--cert']), mapped(root, so['--key'])
            standalone = WorldServer(sroot / 'transport/world.sock', sroot,
                persist_generated_cave=True, archive_generated_areas=True,
                max_players=int(so.get('--max-players', 8)),
                max_controls=int(so.get('--max-controls', 16)),
                connection_headroom=int(so.get('--connection-headroom', 4)))
            broker = None
            try:
                standalone.start()
                port = int(so['--listen'].rsplit(':', 1)[1])
                broker = HostBroker(standalone.socket_path, scert, skey, ('127.0.0.1', port))
                broker.start()
                spin = tls_pin(scert, skey)
                for i, (trainer, token) in enumerate(standalone_credentials, len(credentials)):
                    authenticate(temp, port, spin, trainer, token, i)
            finally:
                if broker:
                    broker.close()
                standalone.close()
        finally:
            manager.close()
    digest = hashlib.sha256()
    code_root = Path(__file__).resolve().parents[1]
    for file in sorted((code_root / 'world').rglob('*.py')):
        digest.update(str(file.relative_to(code_root)).encode())
        digest.update(file.read_bytes())
    return dict(isolated_network_namespace=True, no_external_network=True,
                loopback_only_listeners=True, hosted_worlds_started=len(ports),
                hosted_credentials_authenticated=len(credentials),
                standalone_credentials_authenticated=len(standalone_credentials),
                restored_accounts_retained=account_count,
                implementation_source_sha256=digest.hexdigest(),
                implementation_source='local-reviewed-checkout-not-archived-release',
                management_https_replayed=False, standalone_authority_started=True)


def stop_authority(proc):
    """Kill namespace init first, so the waiting unshare reaps it.

    Linux tears down every descendant in its PID namespace, including setsid
    descendants. Killing only a process group cannot provide that guarantee.
    """
    children = Path('/proc') / str(proc.pid) / 'task' / str(proc.pid) / 'children'
    deadline = time.monotonic() + 5
    while proc.poll() is None:
        try:
            pids = children.read_text().split()
        except FileNotFoundError:
            pids = []
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        if pids:
            # unshare waits for init. The kernel reaps namespace descendants
            # before init becomes waitable, so this also bounds their lifetime.
            proc.wait(timeout=5)
            return
        if time.monotonic() >= deadline:
            # Covers a failed/stuck supervisor before its init exists. Its
            # --kill-child contract also closes the concurrent-fork race.
            proc.kill()
            proc.wait(timeout=5)
            return
        time.sleep(.01)


def prove_authority(root):
    """Fail closed if Linux namespace isolation cannot be established."""
    command = ['unshare', '--user', '--map-root-user', '--net', '--pid', '--fork',
               '--kill-child=SIGKILL',
               sys.executable, str(Path(__file__).resolve()), '--internal-authority',
               str(root), '--original-namespace', os.readlink('/proc/self/ns/net')]
    previous, spawn_mask = None, None
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    if threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGTERM, interrupted)
        # Defer asynchronous cancellation until Popen's handle is owned. In
        # particular, an interrupt during its exec-error-pipe wait must not
        # strand a successfully spawned supervisor before proc is assigned.
        spawn_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
    proc = None
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        try:
            if spawn_mask is not None:
                signal.pthread_sigmask(signal.SIG_SETMASK, spawn_mask)
            stdout, _ = proc.communicate(timeout=180)
        finally:
            # Includes TimeoutExpired, KeyboardInterrupt and SIGTERM. Do not
            # let repeated cancellation interrupt termination/reaping.
            prior_int = None
            if previous is not None:
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                prior_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
            try:
                stop_authority(proc)
            finally:
                if previous is not None:
                    signal.signal(signal.SIGINT, prior_int)
        if proc.returncode:
            raise ValueError('isolated authority rehearsal failed; no active-network fallback')
        result = json.loads(stdout)
        if not result.get('ok'):
            raise ValueError('isolated authority proof failed')
        return result['authority']
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        raise ValueError('isolation unavailable; offline proof only') from None
    finally:
        if proc is not None:
            for stream in (proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()
        if previous is not None:
            try:
                if spawn_mask is not None:
                    signal.pthread_sigmask(signal.SIG_SETMASK, spawn_mask)
            finally:
                signal.signal(signal.SIGTERM, previous)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--authority-proof', action='store_true')
    parser.add_argument('--internal-authority', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--original-namespace', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    result, stage = {}, 'isolation' if args.internal_authority else 'extraction'
    try:
        if args.internal_authority:
            if not args.original_namespace:
                raise ValueError('namespace guard required')
            result = {'authority': authority_child(args.internal_authority, args.original_namespace)}
        else:
            if not args.archive or not args.destination or not args.sha256:
                parser.error('--archive, --destination and --sha256 are required')
            result = extract_private(args.archive, args.destination, args.sha256)
            stage = 'offline_validation'
            result['offline'] = verify_offline(args.destination)
            if args.authority_proof:
                stage = 'isolated_authority'
                result['authority'] = prove_authority(args.destination)
        print(json.dumps(dict(ok=True, **result), sort_keys=True))
        return 0
    except Exception:
        # Archive-derived paths, trainer names, SQL errors and tokens stay private.
        print(json.dumps(dict(ok=False, failure_stage=stage, **result,
                              error='rehearsal failed; private copy retained if extracted')))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
