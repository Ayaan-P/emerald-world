"""Isolated live Python mechanics. This module never executes candidate code.

stage() checks an empty-state baseline and optional tests, not every future
context. Callers must transactionally persist source, sha256, state and tiles
only after run() succeeds, retaining their last-good version on MechanicError.
"""
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time

from .build_catalog import validate_tile, validate_coords
import re


def validate_objects(objects):
    """Small static NPC catalog and literal text, never engine scripts or pointers."""
    if type(objects) is not list or len(objects) > 8:
        raise ValueError('objects must be a list of at most 8 entries')
    seen, locations = set(), set()
    for obj in objects:
        if type(obj) is not dict or set(obj) - {'region_revision','kind','portable'} != {'id', 'group', 'num', 'x', 'y', 'gfx', 'text'}:
            raise ValueError('invalid object fields')
        name, text = obj['id'], obj['text']
        if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', name) or name in seen:
            raise ValueError('invalid or duplicate object id')
        if any(type(obj[k]) is not int for k in ('group', 'num', 'x', 'y', 'gfx')):
            raise ValueError('object coordinates and graphics must be integers')
        from .build_catalog import catalog_maps
        generated=catalog_maps().get((obj['group'],obj['num']),{}).get('name','').startswith('GeneratedWorld_')
        revision=obj.get('region_revision')
        if generated != ('region_revision' in obj) or (generated and (type(revision) is not str or not re.fullmatch('[0-9a-f]{64}',revision))):
            raise ValueError('generated objects require immutable region_revision; native objects must omit it')
        if generated:
            if not 0<=obj['x']<127 or not 0<=obj['y']<127:raise ValueError('invalid generated object coordinates')
        else:validate_coords(obj['group'],obj['num'],obj['x'],obj['y'])
        if 'portable' in obj and (obj.get('kind')!='prop' or type(obj['portable']) is not bool):raise ValueError('Only props may declare explicit portable status')
        if obj.get('kind') is not None and (obj['kind']!='prop' or not generated):raise ValueError('Props require exact generated scope')
        if obj['gfx'] not in ((0,1) if obj.get('kind')=='prop' else (7,8)):
            raise ValueError('object graphics must be boy 1 (7) or girl 1 (8)')
        if (type(text) is not str or not re.fullmatch(r"[A-Za-z0-9 .,!?'-]+(?:\n[A-Za-z0-9 .,!?'-]+)?", text)
                or any(len(line) > 28 for line in text.split('\n'))):
            raise ValueError('object text needs one or two literal lines of at most 28 characters')
        location = tuple(obj[k] for k in ('group', 'num', 'x', 'y')) + (obj.get('region_revision'),)
        if location in locations:
            raise ValueError('duplicate object position')
        seen.add(name)
        locations.add(location)
    return objects


class MechanicError(ValueError):
    """A candidate, sandbox invocation, or result failed validation."""


@dataclass(frozen=True)
class Candidate:
    source: str
    sha256: str


class MechanicRuntime:
    """Linux/x86-64, bubblewrap-required runtime with no unsandboxed fallback.

    Each invocation gets 1 CPU second, 128 MiB address space, at most 192 KiB
    combined stdout/stderr, and a wall deadline (default 2 seconds, maximum 10).
    Sources/tests are UTF-8, at most 256 KiB each. State uses at most 64 KiB of
    compact ASCII-escaped JSON. JSON nesting is capped at 64 levels. The total
    context/state request is at most 256 KiB. This is a kernel sandbox, not a
    claim that arbitrary Python or the host kernel is free of vulnerabilities.
    """

    def __init__(self, root, *, timeout=2.0):
        self.root = Path(root).resolve()
        self.candidates = self.root / 'candidates'
        try:
            self.timeout = float(timeout)
        except (ValueError, TypeError, OverflowError) as exc:
            raise MechanicError('timeout must be in (0, 10] seconds') from exc
        if not 0 < self.timeout <= 10:
            raise MechanicError('timeout must be in (0, 10] seconds')

    def _read_source(self, path):
        directories = []
        try:
            path = Path(path)
            if not path.is_absolute():
                path = self.candidates / path
            path = path.resolve()
            if not path.is_relative_to(self.candidates) or path == self.candidates:
                raise MechanicError('source must be inside root/candidates')
            parts = path.relative_to(self.root).parts
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            directory = os.open(self.root, flags)
            directories.append(directory)
            # Open each directory through its held parent fd to defeat symlink
            # swaps between confinement checks and reading the staged snapshot.
            for part in parts[:-1]:
                directory = os.open(part, flags, dir_fd=directory)
                directories.append(directory)
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         dir_fd=directory)
            with os.fdopen(fd, 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise MechanicError('source must be a regular file')
                data = stream.read(262145)
            if len(data) > 262144:
                raise MechanicError('source exceeds 256 KiB')
            return data.decode('utf-8')
        except (OSError, UnicodeError, RuntimeError) as exc:
            raise MechanicError('cannot read candidate source') from exc
        finally:
            for directory in reversed(directories):
                os.close(directory)

    def stage(self, source_path, tests_path=None):
        """Compile and baseline-run source, then run optional isolated tests.

        Test files may define zero-argument test_* functions or unittest.TestCase
        subclasses. They receive update in their global namespace. Every result
        returned through that injected function is validated like a runtime tick.
        A supplied test file must contain at least one test. Paths are under
        root/candidates.
        """
        candidate = self.from_source(self._read_source(source_path))
        if tests_path is not None:
            tests = self._read_source(tests_path)
            request = self._json({'context': {'players': [], 'tick': 0, 'revision': 0, 'interactions': []},
                                  'state': {}, 'tests': tests})
            try:
                envelope = json.loads(self._invoke(candidate.source, request))
                if (type(envelope) is not dict or set(envelope) != {'baseline', 'test_results'}
                        or type(envelope['baseline']) is not str
                        or type(envelope['test_results']) is not list
                        or any(type(result) is not str for result in envelope['test_results'])):
                    raise MechanicError('invalid mechanic test envelope')
                self._decode_result(envelope['baseline'])
                for result in envelope['test_results']:
                    self._decode_result(result)
            except (ValueError, TypeError, RecursionError) as exc:
                raise MechanicError('invalid mechanic test result: ' + str(exc)) from exc
        return candidate

    def from_source(self, source, sha256=None):
        """Restore persisted source, optionally verifying its stored SHA-256.

        This performs the same empty-state baseline as stage. It does not mutate
        active mechanics or persisted state and does not replay optional tests.
        """
        if type(source) is not str:
            raise MechanicError('source must be text')
        try:
            encoded = source.encode('utf-8')
        except UnicodeError as exc:
            raise MechanicError('source must be UTF-8') from exc
        if len(encoded) > 262144:
            raise MechanicError('source exceeds 256 KiB')
        digest = hashlib.sha256(encoded).hexdigest()
        if sha256 is not None and sha256 != digest:
            raise MechanicError('invalid candidate hash')
        candidate = Candidate(source, digest)
        self.run(candidate, {'players': [], 'tick': 0, 'revision': 0, 'interactions': []}, {})
        return candidate

    def run(self, candidate, context, state):
        if not isinstance(candidate, Candidate) or type(candidate.source) is not str:
            raise MechanicError('invalid candidate')
        try:
            source_bytes = candidate.source.encode('utf-8')
        except UnicodeError as exc:
            raise MechanicError('source must be UTF-8') from exc
        if len(source_bytes) > 262144:
            raise MechanicError('source exceeds 256 KiB')
        if hashlib.sha256(source_bytes).hexdigest() != candidate.sha256:
            raise MechanicError('invalid candidate hash')
        if len(self._json(state)) > 65536:
            raise MechanicError('state exceeds 64 KiB')
        request = self._json({'context': context, 'state': state})
        if len(request) > 262144:
            raise MechanicError('request exceeds 256 KiB')
        return self._decode_result(self._invoke(candidate.source, request))

    def _decode_result(self, raw):
        try:
            result = json.loads(raw)
            if type(result) is not dict or not {'state', 'tiles'} <= set(result) or set(result) - {'state', 'tiles', 'objects'}:
                raise MechanicError('result must contain state and tiles')
            if len(self._json(result['state'])) > 65536:
                raise MechanicError('state exceeds 64 KiB')
            validate_objects(result.get('objects', []))
            tiles = result['tiles']
            if type(tiles) is not list or len(tiles) > 128:
                raise MechanicError('tiles must be a list of at most 128 entries')
            bounds = {'group': 255, 'num': 255, 'x': 1023, 'y': 1023,
                      'metatile': 1023, 'collision': 1}
            seen = set()
            for tile in tiles:
                if type(tile) is not dict or tile.keys() != bounds.keys():
                    raise MechanicError('invalid tile fields')
                for field, maximum in bounds.items():
                    if type(tile[field]) is not int or not 0 <= tile[field] <= maximum:
                        raise MechanicError('invalid tile ' + field)
                validate_tile([tile[field] for field in bounds])
                key = tuple(tile[field] for field in ('group', 'num', 'x', 'y'))
                if key in seen:
                    raise MechanicError('duplicate tile')
                seen.add(key)
            return result
        except (ValueError, TypeError, RecursionError) as exc:
            raise MechanicError('invalid mechanic result: ' + str(exc)) from exc

    @staticmethod
    def _json(value):
        def check(item, depth):
            if depth > 64:
                raise MechanicError('JSON nesting exceeds 64 levels')
            kind = type(item)
            if item is None or kind in (str, int, float, bool):
                return
            if kind is list:
                for child in item:
                    check(child, depth + 1)
            elif kind is dict and all(type(key) is str for key in item):
                for child in item.values():
                    check(child, depth + 1)
            else:
                raise MechanicError('value must have strict JSON types')
        try:
            check(value, 0)
            return json.dumps(value, allow_nan=False, separators=(',', ':')).encode('utf-8')
        except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
            raise MechanicError('value must be finite JSON') from exc

    def _invoke(self, source, request):
        worker = Path(__file__).with_name('mechanic_worker.py').read_bytes()
        fds = []
        proc = None
        try:
            command = ['/usr/bin/bwrap', '--unshare-all', '--clearenv',
                       '--die-with-parent', '--cap-drop', 'ALL', '--tmpfs', '/']
            for directory in ('/usr', '/lib', '/lib64'):
                if Path(directory).exists():
                    command += ['--ro-bind', directory, directory]
            command += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                        '--dir', '/app', '--chdir', '/tmp', '--setenv', 'HOME', '/nonexistent',
                        '--setenv', 'LANG', 'C.UTF-8']
            for name, data in [('worker.py', worker), ('candidate.py', source.encode('utf-8')), ('request.json', request)]:
                fd = os.memfd_create('mechanic-' + name, os.MFD_ALLOW_SEALING)
                fds.append(fd)
                os.write(fd, data)
                # Linux UAPI numbers are stable even when Python was built
                # against headers that omit the optional sealing constants.
                # Always read back the actual kernel seals. Never run unsealed.
                seals = 0x000F  # F_SEAL_SEAL | SHRINK | GROW | WRITE
                fcntl.fcntl(fd, getattr(fcntl, 'F_ADD_SEALS', 1033), seals)
                if fcntl.fcntl(fd, getattr(fcntl, 'F_GET_SEALS', 1034)) & seals != seals:
                    raise MechanicError('kernel did not enforce required memfd seals')
                os.lseek(fd, 0, os.SEEK_SET)
                command += ['--ro-bind-data', str(fd), '/app/' + name]
            command += ['--remount-ro', '/tmp', '--remount-ro', '/',
                        '--', '/usr/bin/python3', '-I', '-B', '/app/worker.py']
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, pass_fds=fds, start_new_session=True,
                                    env={}, close_fds=True)
            output = bytearray()
            errors = bytearray()
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ, output)
                selector.register(proc.stderr, selectors.EVENT_READ, errors)
                deadline = time.monotonic() + self.timeout
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise MechanicError('mechanic timeout')
                    for key, _ in selector.select(remaining):
                        chunk = os.read(key.fd, 8192)
                        if not chunk:
                            selector.unregister(key.fileobj)
                        else:
                            key.data.extend(chunk)
                            if len(output) + len(errors) > 196608:
                                raise MechanicError('mechanic output exceeds limit')
            remaining = deadline - time.monotonic()
            try:
                status = proc.wait(timeout=max(remaining, 0.001))
            except subprocess.TimeoutExpired as exc:
                raise MechanicError('mechanic timeout') from exc
            if status:
                raise MechanicError('mechanic worker failed: ' + errors.decode('utf-8', errors='replace')[:2048])
            return bytes(output)
        except OSError as exc:
            raise MechanicError('sandbox unavailable: ' + str(exc)) from exc
        finally:
            if proc is not None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
                proc.stdout.close()
                proc.stderr.close()
            for fd in fds:
                os.close(fd)
