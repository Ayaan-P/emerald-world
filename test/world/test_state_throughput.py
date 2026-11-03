"""Real SQLite transactions under a deterministic measured 69 ms COMMIT cost."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from world.server import WorldServer


class Clock:
    now = 0.0
    commits = 0

    def __call__(self):
        return self.now

    def trace(self, sql):
        if sql == 'COMMIT':
            self.commits += 1
            self.now += .069


class StateThroughputTests(unittest.TestCase):
    def test_steady_20hz_stream_has_bounded_backlog_and_latest_snapshot(self):
        clock = Clock()
        with tempfile.TemporaryDirectory() as root, patch('world.server.time.monotonic', clock):
            server = WorldServer(root + '/socket', root + '/state')
            peers = []
            for name in ('alice', 'bob'):
                server.create_identity(name)
                peer = dict(id=name, seq=-1, state=None, closing=False, out=bytearray(), sock=None)
                server.peers[name] = peer
                peers.append(peer)
            server.db.set_trace_callback(clock.trace)
            max_lag = 0
            try:
                # 60 simulated seconds, alternating moving trainers, not a burst
                # that an implementation could accidentally batch only at recv().
                for n in range(1200):
                    arrival = n / 20
                    clock.now = max(clock.now, arrival)
                    peer = peers[n % 2]
                    server._line(peer, (f'STATE {n} 0 1 {10 + n % 3} 12 2 7 1 '
                                        + 'a' * 16 + ' ' + 'b' * 16).encode())
                    peer['out'].clear()
                    max_lag = max(max_lag, clock.now - arrival)
                self.assertLess(max_lag, .25, 'fsync per STATE creates unbounded input backlog')
                self.assertLess(clock.commits, 150)
                self.assertFalse(server.db.in_transaction, 'do not hold a write transaction between packets')
            finally:
                server.close()
            with sqlite3.connect(Path(root) / 'state/world.sqlite3') as db:
                rows = db.execute("SELECT data FROM events WHERE kind='state' ORDER BY seq").fetchall()
                latest = {data['id']: data for (wire,) in rows for data in [json.loads(wire)]}
                self.assertEqual(latest['alice']['seq'], 1198)
                self.assertEqual(latest['bob']['seq'], 1199)
                self.assertLess(len(rows), 300)
                self.assertEqual(db.execute('PRAGMA synchronous').fetchone()[0], 2)


    def test_critical_interaction_and_changed_hashes_are_durable_before_reply(self):
        from world.client import WorldClient
        clock = Clock()
        with tempfile.TemporaryDirectory() as root, patch('world.server.time.monotonic', clock):
            server = WorldServer(root + '/socket', root + '/state')
            identity = server.create_identity('alice')
            save = Path(identity['save_path'])
            save.write_bytes(b'private trainer save must never be changed by STATE')
            server.objects = [dict(id='guide', group=0, num=1, x=10, y=11, gfx=7, text='Hi')]
            server.start()
            try:
                with WorldClient(root + '/socket', 'alice', identity['token']) as client:
                    client.snapshot()
                    client.send_state(1, 0, 1, 10, 12, 2, 7, 1, 'a'*16, 'b'*16)
                    client.snapshot()
                    client.send_state(2, 0, 1, 10, 12, 2, 7, 1, 'a'*16, 'b'*16)
                    client.snapshot()
                    self.assertEqual(server.pending_states['alice']['seq'], 2)
                    client.interact(3, 'guide')
                    client.snapshot()
                    with sqlite3.connect(Path(root) / 'state/world.sqlite3') as reader:
                        rows = reader.execute("SELECT data FROM events WHERE kind='interaction'").fetchall()
                        self.assertEqual(len(rows), 1)
                        self.assertEqual(json.loads(rows[0][0])['object'], 'guide')
                        client.send_state(4, 0, 1, 10, 12, 2, 7, 1, 'c'*16, 'd'*16)
                        client.snapshot()
                        self.assertEqual(reader.execute('SELECT party_hash,bag_hash FROM identities').fetchone(),
                                         ('c'*16, 'd'*16))
                        self.assertNotIn('alice', server.pending_states, 'old snapshots cannot overwrite newer hashes')
                        self.assertFalse(server.db.in_transaction)
                    self.assertEqual(save.read_bytes(), b'private trainer save must never be changed by STATE')
            finally:
                server.close()

    def test_flush_failure_keeps_pending_snapshot_and_committed_revision(self):
        clock = Clock()
        with tempfile.TemporaryDirectory() as root, patch('world.server.time.monotonic', clock):
            server = WorldServer(root + '/socket', root + '/state')
            server.create_identity('alice')
            peer = dict(id='alice', seq=-1, state=None, closing=False, out=bytearray(), sock=None)
            server.peers['alice'] = peer
            try:
                for seq in (1, 2):
                    server._line(peer, (f'STATE {seq} 0 1 10 12 2 7 1 ' + 'a'*16 + ' ' + 'b'*16).encode())
                revision = server.revision
                # Deny the actual SQLite COMMIT, rather than mocking flush().
                server.db.set_authorizer(lambda op, arg, *_:
                    sqlite3.SQLITE_DENY if op == sqlite3.SQLITE_TRANSACTION and arg == 'COMMIT'
                    else sqlite3.SQLITE_OK)
                with self.assertRaises(sqlite3.DatabaseError):
                    server._flush_states()
                self.assertEqual(server.pending_states['alice']['seq'], 2)
                self.assertEqual(server.revision, revision)
                # Python 3.10 does not support removing an authorizer with
                # None. Restore an explicit allow callback on both interpreters.
                server.db.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
                server._flush_states()
                self.assertEqual(server.pending_states, {})
            finally:
                # Python 3.10 does not support removing an authorizer with
                # None. Restore an explicit allow callback on both interpreters.
                server.db.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
                server.close()


if __name__ == '__main__':
    unittest.main()
