"""Recovery on disposable worlds after real SQLite and filesystem failures."""
import fcntl
from pathlib import Path
import sqlite3
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

from world.server import WorldServer
from world.world_library import WorldActivityLock


class CloseFailureTests(unittest.TestCase):
    def test_listener_creation_failures_release_authority_and_allow_retry(self):
        # Adapt both frozen donor startup cases to real selectors/listeners.
        for fail_at in (1, 2):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state = root / 'world'
                server = WorldServer(root / 'socket', state)
                real_socket = socket.socket
                created = []
                calls = 0

                def fail_creation(*args, **kwargs):
                    nonlocal calls
                    calls += 1
                    if calls == fail_at:
                        raise OSError('listener allocation failed')
                    listener = real_socket(*args, **kwargs)
                    created.append(listener)
                    return listener

                try:
                    for _ in range(2):
                        calls = 0
                        with patch('world.server.socket.socket', side_effect=fail_creation):
                            with self.assertRaisesRegex(OSError, 'listener allocation failed'):
                                server.start()
                        self.assertIsNone(server.selector)
                        self.assertIsNone(server.authority_lock)
                        self.assertIsNone(server.thread)
                        self.assertTrue(all(listener.fileno() == -1 for listener in created))
                        with (state / 'world.lock').open('a+b') as other:
                            fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    # Constructor ownership remains with the caller, as in the
                    # donor. Retrying this instance must retain its activity lease.
                    with self.assertRaises(ValueError):
                        WorldActivityLock(state, exclusive=True)
                    server.start()
                    self.assertTrue(Path(server.socket_path).is_socket())
                finally:
                    server.close()
                with self.assertRaises(sqlite3.ProgrammingError):
                    server.db.execute('SELECT 1')
                with WorldActivityLock(state, exclusive=True):
                    pass

    def test_filesystem_start_failure_releases_authority_without_removing_foreign_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'world'
            path = root / 'socket'
            path.write_bytes(b'not a socket')
            server = WorldServer(path, state)
            try:
                with self.assertRaisesRegex(RuntimeError, 'non-owned socket path'):
                    server.start()
                self.assertIsNone(server.authority_lock)
                self.assertEqual(path.read_bytes(), b'not a socket')
                with (state / 'world.lock').open('a+b') as other:
                    fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                path.unlink()
                server.start()
            finally:
                server.close()

    def test_loop_failure_closes_real_clients_before_owner_cleanup(self):
        # The donor's loop regression through the real authority thread, with
        # real accepted sockets and a denied SQLite COMMIT.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = WorldServer(root / 'socket', root / 'world').start()
            errors = []
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client, \
                     patch('threading.excepthook', side_effect=errors.append):
                    client.settimeout(1)
                    client.connect(server.socket_path)
                    deadline = time.monotonic() + 2
                    while not server.connections and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertEqual(len(server.connections), 1)
                    accepted = next(iter(server.connections))
                    with server.lock:
                        server.pending_states['alice'] = dict(id='alice', seq=1,
                            state=[0, 1, 10, 12, 4, 7, 1], party_hash='a'*16, bag_hash='b'*16)
                        server.next_state_flush = 0
                        server.db.set_authorizer(lambda op, arg, *_: sqlite3.SQLITE_DENY
                            if op == sqlite3.SQLITE_TRANSACTION and arg == 'COMMIT' else sqlite3.SQLITE_OK)
                    server.thread.join(2)
                    self.assertFalse(server.thread.is_alive())
                    self.assertEqual(len(errors), 1)
                    self.assertIsInstance(errors[0].exc_value, sqlite3.Error)
                    self.assertEqual(client.recv(1), b'')
                    self.assertEqual(accepted.fileno(), -1)
                    self.assertTrue(server.stopping.is_set())
            finally:
                with self.assertRaises(sqlite3.Error):
                    server.close()
            with WorldActivityLock(root / 'world', exclusive=True):
                pass

    def test_close_path_failure_still_releases_database_and_both_locks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'world'
            server = WorldServer(root / 'socket', state).start()
            server.stopping.set()
            server.thread.join()
            # A real unlink failure after listener closure, not a mocked close.
            Path(server.admin_path).unlink()
            Path(server.admin_path).mkdir()
            with self.assertRaises(IsADirectoryError):
                server.close()
            with self.assertRaises(sqlite3.ProgrammingError):
                server.db.execute('SELECT 1')
            self.assertIsNone(server.authority_lock)
            with WorldActivityLock(state, exclusive=True):
                pass
            server.close()

    def test_start_after_close_cannot_reacquire_resources_without_activity_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = WorldServer(root / 'socket', root / 'world')
            server.close()
            try:
                with self.assertRaisesRegex(RuntimeError, 'closed'):
                    server.start()
            finally:
                # Also contain the pre-fix repro, whose idempotent close is a no-op.
                if server.thread is not None:
                    server.stopping.set()
                    server.thread.join()
                if server.selector is not None:
                    for key in list(server.selector.get_map().values()):
                        key.fileobj.close()
                    server.selector.close()
                if server.authority_lock is not None:
                    server.authority_lock.close()
            self.assertFalse(Path(server.socket_path).exists())
            with WorldActivityLock(root / 'world', exclusive=True):
                pass

    def test_constructor_sqlite_failure_releases_activity_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'world'
            state.mkdir(mode=0o700)
            database = state / 'world.sqlite3'
            database.write_bytes(b'not a database')
            with self.assertRaises(sqlite3.DatabaseError):
                WorldServer(root / 'socket', state)
            self.assertEqual(database.read_bytes(), b'not a database')
            with WorldActivityLock(state, exclusive=True):
                pass

    def test_failed_flush_closes_database_and_releases_world_lifecycle_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'world'
            server = WorldServer(root / 'socket', state)
            identity = server.create_identity('alice')
            # The donor's failure is at owner close, independently of _loop.
            server.authority_lock = (state / 'world.lock').open('a+b')
            fcntl.flock(server.authority_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            authority_handle = server.authority_lock
            save = Path(identity['save_path'])
            save.write_bytes(b'private-progress-unchanged')
            server.pending_states['alice'] = dict(id='alice', seq=1,
                state=[0, 1, 10, 12, 4, 7, 1], party_hash='a'*16, bag_hash='b'*16)
            revision = server.revision
            server.db.set_authorizer(lambda op, arg, *_: sqlite3.SQLITE_DENY
                if op == sqlite3.SQLITE_TRANSACTION and arg == 'COMMIT' else sqlite3.SQLITE_OK)
            with self.assertRaises(sqlite3.Error):
                server.close()
            with self.assertRaises(sqlite3.ProgrammingError):
                server.db.execute('SELECT 1')
            self.assertTrue(authority_handle.closed)
            self.assertIsNone(server.authority_lock)
            self.assertIsNone(server.activity.fd)
            self.assertEqual(server.pending_states['alice']['seq'], 1)
            self.assertEqual(server.revision, revision)
            server.close()
            with (state / 'world.lock').open('a+b') as new_lock:
                fcntl.flock(new_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with WorldActivityLock(state, exclusive=True):
                pass
            self.assertEqual(save.read_bytes(), b'private-progress-unchanged')
            replacement = WorldServer(root / 'socket', state)
            try:
                replacement.start()
                self.assertEqual(replacement.create_identity('alice'), identity)
                self.assertEqual(replacement.db.execute(
                    "SELECT count(*) FROM events WHERE kind='state'").fetchone()[0], 0)
                self.assertEqual(replacement.db.execute('PRAGMA synchronous').fetchone()[0], 2)
            finally:
                replacement.close()


if __name__ == '__main__':
    unittest.main()
