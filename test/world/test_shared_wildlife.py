"""Real authority and client parsing, in-memory delivery; no sockets or saves."""
import io
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from world.server import WorldServer
from world.client import WorldClient as Client
from world.shared_wildlife import catalogue, parse_snapshot


class SharedWildlifeTests(unittest.TestCase):
    def setUp(self):
        guard = patch('socket.socket', side_effect=AssertionError('no sockets'))
        guard.start(); self.addCleanup(guard.stop)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.server = WorldServer(root / 'socket', root / 'world')
        self.addCleanup(self.server.close)
        self.server._queue = lambda conn, text: conn.setdefault('messages', []).append(text)
        self.a = self.peer('a'); self.b = self.peer('b'); self.legacy = self.peer('legacy')
        self.row = dict(group=0, num=16, x=5, y=5, species=25, level=5)
        # Route 101, selected from the actual map catalogue, not a synthetic map.
        from world.build_catalog import catalog_maps
        key = next(k for k, v in catalog_maps().items() if v['name'] == 'Route101')
        self.row.update(group=key[0], num=key[1])
        for conn in self.server.peers.values():
            conn['state'] = [*key, 5, 4, 1, 7, 1]
        view = self.server.inspect_shared_wildlife()
        self.view = self.server.replace_shared_wildlife(view['epoch'], view['revision'], [self.row])
        self.spawn = self.view['spawns'][0]['id']; self.epoch = self.view['epoch']
        self.subscribe(self.a); self.subscribe(self.b)

    def peer(self, name):
        conn = dict(id=name, closing=False, social=True, state=None, seq=0, state_time=time.monotonic(), messages=[])
        self.server.peers[name] = conn
        return conn

    def subscribe(self, conn):
        self.server._line(conn, ('WILDLIFE SUBSCRIBE ' + catalogue()[1]).encode())
        self.assertFalse(conn.get('closing', False))

    def send(self, conn, text):
        self.server._line(conn, text.encode())
        self.assertFalse(conn.get('closing', False), conn['messages'])

    def snapshot(self, conn):
        client = Client.__new__(Client)
        client.control = False; client.social = True; client.trainer_id = conn['id']
        client.shared_wildlife = conn.get('shared_wildlife', False)
        client.wildlife_battles = conn.get('wildlife_version') == 2
        client.stream = io.BytesIO(self.server._snapshot(conn).encode())
        return client.snapshot()

    def claim(self, conn, seq=1):
        self.send(conn, f'WILDLIFE CLAIM {seq} {self.epoch} {self.spawn}')

    def commit(self):
        self.send(self.a, 'WILDLIFE SUBSCRIBE ' + catalogue()[1] + ' 2')
        self.claim(self.a)
        lease = self.snapshot(self.a)['wildlife']['lease']['lease']
        self.a['state'][6] = 0  # Native input lock while awaiting admission.
        self.send(self.a, f'WILDLIFE COMMIT 2 {self.epoch} {self.spawn} {lease}')
        return lease

    def test_committed_battle_is_private_and_never_reoffered(self):
        lease = self.commit()
        own = self.snapshot(self.a)['wildlife']
        self.assertEqual(own['battle']['lease'], lease)
        self.assertIsNone(own['lease'])
        self.assertEqual(own['spawns'], [])
        self.assertIsNone(self.snapshot(self.b)['wildlife']['battle'])
        self.server.wildlife.expire(time.monotonic() + 1000)
        self.claim(self.b)
        self.assertFalse(self.server.wildlife.claims)
        self.assertIn(self.spawn, self.server.wildlife.consumed)

    def test_commit_ack_exact_owner_replay_and_disconnect(self):
        lease = self.commit()
        before = self.server.wildlife.revision
        self.send(self.a, f'WILDLIFE COMMIT 3 {self.epoch} {self.spawn} {lease}')
        self.assertEqual(self.server.wildlife.revision, before)
        self.assertFalse(self.server.wildlife.acknowledge(self.b, self.epoch, self.spawn, lease))
        self.assertFalse(self.server.wildlife.acknowledge(self.a, self.epoch, self.spawn, '0'*32))
        self.send(self.a, f'WILDLIFE ACK 4 {self.epoch} {self.spawn} {lease}')
        self.assertFalse(self.server.wildlife.commits)
        self.assertIn(self.spawn, self.server.wildlife.consumed)
        self.send(self.a, f'WILDLIFE COMMIT 5 {self.epoch} {self.spawn} {lease}')
        self.assertFalse(self.server.wildlife.commits)
        self.server.wildlife.drop(self.a)
        self.claim(self.b)
        self.assertFalse(self.server.wildlife.claims)

    def test_disconnect_discards_receipt_not_consumption(self):
        self.commit()
        self.assertTrue(self.server.wildlife.drop(self.a))
        self.assertFalse(self.server.wildlife.commits)
        self.assertIn(self.spawn, self.server.wildlife.consumed)
        self.assertEqual(self.snapshot(self.b)['wildlife']['spawns'], [])

    def test_commit_requires_current_position_freshness_and_lease(self):
        self.claim(self.a)
        lease = self.snapshot(self.a)['wildlife']['lease']['lease']
        now = time.monotonic()
        self.assertFalse(self.server.wildlife.commit(self.b, self.epoch, self.spawn, lease, now))
        self.assertFalse(self.server.wildlife.commit(self.a, self.epoch, self.spawn, '0'*32, now))
        self.a['state'][2] += 1
        self.assertFalse(self.server.wildlife.commit(self.a, self.epoch, self.spawn, lease, now))
        self.a['state'][2] -= 1
        self.assertFalse(self.server.wildlife.commit(self.a, self.epoch, self.spawn, lease, now+3))
        self.assertFalse(self.server.wildlife.commits)

    def test_python_commit_commands_and_receipt_parser_guards(self):
        client = Client.__new__(Client)
        client.control = False; client.social = True; client.sock = Mock()
        with self.assertRaises(ValueError):
            client.commit_wildlife(1, self.epoch, self.spawn, 'c'*32)
        client.subscribe_wildlife(battles=True)
        client.commit_wildlife(1, self.epoch, self.spawn, 'c'*32)
        self.assertEqual(client.sock.sendall.call_args.args[0],
                         f'WILDLIFE COMMIT 1 {self.epoch} {self.spawn} {"c"*32}\n'.encode())
        client.commit_wildlife(2, self.epoch, self.spawn, 'c'*32, acknowledge=True)
        self.assertTrue(client.sock.sendall.call_args.args[0].startswith(b'WILDLIFE ACK 2 '))
        header = ['WILDLIFE2', self.epoch, '1', '0']
        battle = ['WILDBATTLE',self.spawn,'c'*32,*map(str,[self.row[k] for k in ('group','num','x','y','species','level')])]
        self.assertEqual(parse_snapshot(header,[],None,battle)['battle']['species'],25)
        with self.assertRaises(ValueError):
            parse_snapshot(header,[],['WILDLEASE',self.spawn,'c'*32],battle)
        with self.assertRaises(ValueError):
            parse_snapshot(['WILDLIFE',*header[1:]],[],None,battle)
        with self.assertRaises(ValueError):
            client.commit_wildlife(True,self.epoch,self.spawn,'c'*32)

    def test_explicit_prebattle_abort_returns_spawn_with_new_lease(self):
        lease = self.commit()
        self.assertFalse(self.server.wildlife.abort(self.b,self.epoch,self.spawn,lease))
        self.assertFalse(self.server.wildlife.abort(self.a,self.epoch,self.spawn,'0'*32))
        self.send(self.a,f'WILDLIFE ABORT 3 {self.epoch} {self.spawn} {lease}')
        self.assertFalse(self.server.wildlife.commits)
        self.assertNotIn(self.spawn,self.server.wildlife.consumed)
        self.assertEqual(self.snapshot(self.b)['wildlife']['spawns'][0]['status'],'available')
        self.a['state'][6] = 1
        self.claim(self.a,4)
        new_lease = self.snapshot(self.a)['wildlife']['lease']['lease']
        self.assertNotEqual(lease,new_lease)
        self.send(self.a,f'WILDLIFE COMMIT 5 {self.epoch} {self.spawn} {lease}')
        self.assertFalse(self.server.wildlife.commits)
        self.send(self.a,f'WILDLIFE COMMIT 6 {self.epoch} {self.spawn} {new_lease}')
        self.send(self.a,f'WILDLIFE ABORT 7 {self.epoch} {self.spawn} {lease}')
        self.assertIn(self.spawn,self.server.wildlife.commits)
        self.send(self.a,f'WILDLIFE ACK 8 {self.epoch} {self.spawn} {new_lease}')
        self.send(self.a,f'WILDLIFE ABORT 9 {self.epoch} {self.spawn} {new_lease}')
        self.assertIn(self.spawn,self.server.wildlife.consumed)

    def test_legacy_cannot_commit(self):
        self.claim(self.a)
        lease = self.snapshot(self.a)['wildlife']['lease']['lease']
        with self.assertRaises(ValueError):
            text = f'WILDLIFE COMMIT 2 {self.epoch} {self.spawn} {lease}'
            self.server._wildlife_line(self.a, text.encode(), text.split())
        self.assertFalse(self.server.wildlife.commits)

    def test_same_spawn_identity_and_legacy_isolation(self):
        self.assertEqual(self.snapshot(self.a)['wildlife'], self.snapshot(self.b)['wildlife'])
        self.assertNotIn('wildlife', self.snapshot(self.legacy))
        self.b['state'][1] += 1
        self.assertEqual(self.snapshot(self.b)['wildlife']['spawns'], [])
        self.assertEqual(self.snapshot(self.a)['wildlife']['spawns'][0]['id'], self.spawn)

    def test_atomic_two_player_race_one_private_lease(self):
        barrier = threading.Barrier(2)
        errors = []
        def run(conn):
            try:
                barrier.wait(); self.claim(conn)
            except BaseException as exc:
                errors.append(exc)
        threads = [threading.Thread(target=run, args=(conn,)) for conn in (self.a, self.b)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        a, b = self.snapshot(self.a)['wildlife'], self.snapshot(self.b)['wildlife']
        self.assertEqual(a['spawns'], b['spawns'])
        self.assertEqual(a['spawns'][0]['status'], 'reserved')
        self.assertEqual(sum(v['lease'] is not None for v in (a, b)), 1)
        self.assertEqual(len(self.server.wildlife.claims), 1)

    def test_release_exact_owner_and_receipt_and_replay(self):
        self.claim(self.a)
        lease = self.snapshot(self.a)['wildlife']['lease']['lease']
        before = self.server.wildlife.revision
        self.claim(self.a)  # Duplicate request returns current state, no new lease.
        self.assertEqual(self.server.wildlife.revision, before)
        self.send(self.b, f'WILDLIFE RELEASE 1 {self.epoch} {self.spawn} {lease}')
        self.assertIn(self.spawn, self.server.wildlife.claims)
        self.send(self.a, f'WILDLIFE RELEASE 2 {self.epoch} {self.spawn} {"0" * 32}')
        self.assertIn(self.spawn, self.server.wildlife.claims)
        self.send(self.a, f'WILDLIFE RELEASE 3 {self.epoch} {self.spawn} {lease}')
        self.assertEqual(self.snapshot(self.b)['wildlife']['spawns'][0]['status'], 'available')
        self.claim(self.b, 2)
        self.send(self.a, f'WILDLIFE RELEASE 4 {self.epoch} {self.spawn} {lease}')
        self.assertIs(self.server.wildlife.claims[self.spawn][0], self.b)

    def test_stale_busy_remote_and_wrong_facing_cannot_reserve(self):
        original = self.a['state'][:]
        for index, value in ((2, 12), (4, 2), (6, 0), (0, 33)):
            self.a['state'] = original[:]; self.a['state'][index] = value
            self.claim(self.a, self.a['seq'] + 1)
            self.assertFalse(self.server.wildlife.claims)
        self.a['state'] = original
        self.a['state_time'] = time.monotonic() - 3
        self.claim(self.a, self.a['seq'] + 1)
        self.assertFalse(self.server.wildlife.claims)
        self.a['state_time'] = time.monotonic() + 1
        self.claim(self.a, self.a['seq'] + 1)
        self.assertFalse(self.server.wildlife.claims)

    def test_expiry_and_exact_session_disconnect(self):
        self.claim(self.a)
        old_lease = self.snapshot(self.a)['wildlife']['lease']['lease']
        replacement = dict(self.a)
        self.assertFalse(self.server.wildlife.drop(replacement))
        deadline = self.server.wildlife.claims[self.spawn][2]
        self.server._poll_presence(deadline + 1)
        self.assertFalse(self.server.wildlife.claims)
        self.claim(self.b)
        self.send(self.a, f'WILDLIFE RELEASE 2 {self.epoch} {self.spawn} {old_lease}')
        self.assertIs(self.server.wildlife.claims[self.spawn][0], self.b)
        self.assertTrue(self.server.wildlife.drop(self.b))

    def test_publish_validates_all_rows_before_mutation_and_cas(self):
        before = self.server.inspect_shared_wildlife()
        for rows in ([dict(self.row, species=65535)], [dict(self.row, level=True)],
                     [self.row, self.row], [dict(self.row, x=9999)], [dict(self.row, x=5, y=4)]):
            with self.assertRaises(ValueError):
                self.server.replace_shared_wildlife(self.epoch, before['revision'], rows)
            self.assertEqual(self.server.inspect_shared_wildlife(), before)
        with self.assertRaises(ValueError):
            self.server.replace_shared_wildlife(self.epoch, 0, [])
        self.claim(self.a)
        with self.assertRaisesRegex(ValueError, 'reservations'):
            self.server.replace_shared_wildlife(self.epoch, self.server.wildlife.revision, [])

    def test_old_epoch_and_changed_publication_cannot_claim(self):
        old = self.spawn
        view = self.server.replace_shared_wildlife(self.epoch, self.view['revision'], [self.row])
        self.assertNotEqual(old, view['spawns'][0]['id'])
        self.claim(self.a)
        self.assertFalse(self.server.wildlife.claims)
        self.send(self.a, f'WILDLIFE CLAIM 2 {"0" * 32} {view["spawns"][0]["id"]}')
        self.assertFalse(self.server.wildlife.claims)

    def test_capability_auth_and_parser_fail_closed(self):
        impostor = dict(self.a)
        with self.assertRaises(ValueError):
            self.server._wildlife_line(impostor, b'WILDLIFE SUBSCRIBE bad', ['WILDLIFE', 'SUBSCRIBE', 'bad'])
        with self.assertRaises(ValueError):
            self.server._wildlife_line(self.legacy, b'WILDLIFE SUBSCRIBE bad', ['WILDLIFE', 'SUBSCRIBE', 'bad'])
        header = ['WILDLIFE', self.epoch, '1', '1']
        row = ['WILDMON', self.spawn, *map(str, [self.row[k] for k in ('group','num','x','y','species','level')]), 'available']
        self.assertEqual(parse_snapshot(header, [row], None)['spawns'][0]['id'], self.spawn)
        for bad_header, rows in ((header, []), (header, [row, row]), (['WILDLIFE','bad','1','1'], [row])):
            with self.assertRaises(ValueError): parse_snapshot(bad_header, rows, None)
        bad = row[:]; bad[-1] = 'caught'
        with self.assertRaises(ValueError): parse_snapshot(header, [bad], None)

    def test_real_auth_dispatch_cannot_publish_or_subscribe_before_login(self):
        before = self.server.inspect_shared_wildlife()
        unauthenticated = dict(id=None, closing=False, messages=[])
        self.server._line(unauthenticated, ('WILDLIFE SUBSCRIBE ' + catalogue()[1]).encode())
        self.assertTrue(unauthenticated['closing'])
        self.assertNotIn('shared_wildlife', unauthenticated)
        self.server._line(self.legacy, b'WILDLIFE PUBLISH 1 anything')
        self.assertTrue(self.legacy['closing'])
        self.assertEqual(self.server.inspect_shared_wildlife(), before)

    def test_python_client_sends_only_explicit_bounded_commands(self):
        client = Client.__new__(Client)
        client.control = False; client.social = True; client.sock = Mock()
        client.subscribe_wildlife()
        self.assertEqual(client.sock.sendall.call_args.args[0],
                         ('WILDLIFE SUBSCRIBE ' + catalogue()[1] + '\n').encode())
        client.reserve_wildlife(1, self.epoch, self.spawn)
        self.assertEqual(client.sock.sendall.call_args.args[0],
                         f'WILDLIFE CLAIM 1 {self.epoch} {self.spawn}\n'.encode())
        before = client.sock.sendall.call_count
        for seq, epoch, spawn in ((True, self.epoch, self.spawn), (2, 'bad', self.spawn),
                                  (2, self.epoch, 'bad'), (-1, self.epoch, self.spawn)):
            with self.assertRaises(ValueError): client.reserve_wildlife(seq, epoch, spawn)
        self.assertEqual(client.sock.sendall.call_count, before)

    def test_real_drop_hook_releases_exact_presence_without_socket(self):
        self.claim(self.a)
        self.a['sock'] = Mock()
        self.server.connections[self.a['sock']] = self.a
        selector = self.server.selector
        self.server.selector = Mock()
        self.server._flush_states = Mock()
        try:
            self.server._drop(self.a)
        finally:
            self.server.selector = selector
        self.assertNotIn('a', self.server.peers)
        self.assertFalse(self.server.wildlife.claims)
        self.assertEqual(self.snapshot(self.b)['wildlife']['spawns'][0]['status'], 'available')

    def test_restart_is_empty_new_epoch_not_restored_reservations(self):
        self.claim(self.a)
        root = Path(self.tmp.name)
        self.server.close()
        restored = WorldServer(root / 'other', root / 'world')
        try:
            view = restored.inspect_shared_wildlife()
            self.assertNotEqual(view['epoch'], self.epoch)
            self.assertEqual(view['spawns'], [])
            self.assertEqual(view['revision'], 0)
        finally:
            restored.close()

    def test_one_reservation_per_presence_and_immutable_publish_result(self):
        second = dict(self.row, x=6)
        view = self.server.replace_shared_wildlife(self.epoch, self.view['revision'], [self.row, second])
        first_id, second_id = [row['id'] for row in view['spawns']]
        view['spawns'][0]['species'] = 99999
        self.assertEqual(self.server.wildlife.spawns[0]['species'], 25)
        self.spawn = first_id
        self.claim(self.a)
        self.a['state'][2] = 6
        self.send(self.a, f'WILDLIFE CLAIM 2 {self.epoch} {second_id}')
        self.assertEqual(list(self.server.wildlife.claims), [first_id])

    def test_admin_scope_and_session_only_no_save_or_event_writes(self):
        changes = self.server.db.total_changes
        admin = dict(messages=[])
        self.server._admin_line(admin, b'{"command":"inspect_shared_wildlife"}')
        self.assertIn('"persistent": false', admin['messages'][-1])
        self.claim(self.a)
        self.assertEqual(self.server.db.total_changes, changes)
        self.assertFalse((Path(self.tmp.name) / 'world' / 'test.sav').exists())


if __name__ == '__main__': unittest.main()
