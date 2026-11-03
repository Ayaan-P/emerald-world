import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest


class WorldTests(unittest.TestCase):
    def test_interaction_queries_use_selective_index_on_new_and_existing_worlds(self):
        from world.server import WorldServer
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            for reopening in (False, True):
                server = WorldServer(root + '/socket', root + '/state')
                try:
                    indexes = {row[1] for row in server.db.execute('PRAGMA index_list(events)')}
                    self.assertIn('events_kind_seq', indexes)
                    plan = server.db.execute("EXPLAIN QUERY PLAN SELECT seq,data FROM events WHERE kind='interaction' AND seq>? ORDER BY seq LIMIT 64", (0,)).fetchall()
                    self.assertIn('events_kind_seq', str(plan))
                    if not reopening:
                        server.db.execute('DROP INDEX events_kind_seq')
                        server.db.commit()
                finally:
                    server.close()

    def test_authenticated_peer_snapshots_and_durable_hashes(self):
        from world.server import WorldServer
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root + '/socket', root + '/state')
            a, b = server.create_identity('Alice'), server.create_identity('Bob')
            try:
                server.start()
                sockets = []
                streams = []
                for identity in (a, b):
                    sock = socket.socket(socket.AF_UNIX)
                    sock.settimeout(2)
                    sock.connect(root + '/socket')
                    sockets.append(sock)
                    stream = sock.makefile('rb')
                    streams.append(stream)
                    sock.sendall(('HELLO 1 {id} {token}\n'.format(**identity)).encode())
                    self.assertTrue(stream.readline().startswith(b'WELCOME 1 '))
                sockets[0].sendall(('STATE 1 0 1 10 12 2 7 1 ' + 'a'*16 + ' ' + 'b'*16 + '\n').encode())
                for _ in range(20):
                    line = streams[1].readline()
                    if line.startswith(b'PEER Alice '):
                        break
                self.assertEqual(line, b'PEER Alice 0 1 10 12 2 7 1\n')
                sockets[0].sendall(('STATE 1 0 1 10 12 2 7 1 ' + 'a'*16 + ' ' + 'b'*16 + '\n').encode())
                while True:
                    line = streams[0].readline()
                    if line.startswith(b'ERROR'):
                        break
                self.assertEqual(line, b'ERROR STALE\n')
            finally:
                for stream in locals().get('streams', []):
                    stream.close()
                for sock in locals().get('sockets', []):
                    sock.close()
                server.close()
            server = WorldServer(root + '/socket', root + '/state')
            self.assertEqual(server.db.execute('SELECT party_hash,bag_hash FROM identities WHERE id=?', ('Alice',)).fetchone(), ('a'*16, 'b'*16))
            self.assertGreater(server.db.execute('SELECT max(seq) FROM events').fetchone()[0], 0)
            server.close()

    def test_protocol_rejects_unauthenticated_duplicate_and_oversize(self):
        from world.server import WorldServer
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root + '/socket', root + '/state')
            identity = server.create_identity('Alice')
            server.start()
            def exchange(data):
                with socket.socket(socket.AF_UNIX) as sock:
                    sock.settimeout(2)
                    sock.connect(root + '/socket')
                    sock.sendall(data)
                    return sock.recv(4096).split(b'\n')[0]
            try:
                self.assertEqual(exchange(b'STATE 1\n'), b'ERROR AUTH')
                self.assertEqual(exchange(b'HELLO 1 Alice ' + b'0'*64 + b'\n'), b'ERROR AUTH')
                self.assertEqual(exchange(b'x'*1025), b'ERROR OVERSIZE')
                with socket.socket(socket.AF_UNIX) as sock:
                    sock.settimeout(2)
                    sock.connect(root + '/socket')
                    hello = ('HELLO 1 {id} {token}\n'.format(**identity)).encode()
                    sock.sendall(hello)
                    self.assertTrue(sock.recv(4096).startswith(b'WELCOME'))
                    self.assertEqual(exchange(hello), b'ERROR DUPLICATE')
            finally:
                server.close()

    def test_admin_inspect_and_confined_deploy(self):
        from world.server import WorldServer
        from world.client import admin_request
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root + '/socket', root + '/state')
            server.start()
            try:
                result = admin_request(root + '/socket', {'command': 'inspect'})
                self.assertTrue(result['ok'])
                self.assertEqual(result['tiles'], [])
                self.assertEqual(Path(root + '/socket.admin').stat().st_mode & 0o777, 0o600)
                result = admin_request(root + '/socket', {'command': 'deploy', 'source_path': '/etc/passwd'})
                self.assertFalse(result['ok'])
                self.assertIn('candidate', result['error'])
            finally:
                server.close()

    def test_deploy_ticks_rollback_and_restart_restore(self):
        from world.server import WorldServer
        from world.client import admin_request
        import time
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            state = Path(root) / 'state'
            (state / 'candidates').mkdir(parents=True)
            good = state / 'candidates/good.py'
            good.write_text("def update(context, state):\n return {'state': {'n': state.get('n', 0) + 1}, 'tiles': [{'group':0,'num':1,'x':2,'y':3,'metatile':4,'collision':1}]}\n")
            bad = state / 'candidates/bad.py'
            bad.write_text("def update(context, state):\n raise ValueError('broken')\n")
            server = WorldServer(root + '/socket', state)
            server.start()
            try:
                result = admin_request(root + '/socket', {'command':'deploy', 'source_path':str(good)})
                self.assertTrue(result['ok'], result)
                first = admin_request(root + '/socket', {'command':'inspect'})
                time.sleep(0.35)
                later = admin_request(root + '/socket', {'command':'inspect'})
                self.assertGreater(later['state']['n'], first['state']['n'])
                result = admin_request(root + '/socket', {'command':'deploy', 'source_path':str(bad)})
                self.assertFalse(result['ok'])
                after = admin_request(root + '/socket', {'command':'inspect'})
                self.assertEqual(after['module_hash'], first['module_hash'])
                self.assertTrue(after['error'])
                self.assertEqual(after['tiles'], [[0,1,2,3,4,1]])
            finally:
                server.close()
            good.unlink()
            server = WorldServer(root + '/socket', state)
            server.start()
            try:
                restored = admin_request(root + '/socket', {'command':'inspect'})
                self.assertEqual(restored['module_hash'], first['module_hash'])
                self.assertGreaterEqual(restored['state']['n'], later['state']['n'])
                self.assertEqual(restored['tiles'], [[0,1,2,3,4,1]])
            finally:
                server.close()

    def test_shared_npc_interaction_is_consumed_once_and_survives_restart(self):
        from world.server import WorldServer
        from world.client import WorldClient, admin_request
        import time
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            state = Path(root) / 'state'
            server = WorldServer(root + '/socket', state)
            identity = server.create_identity('Alice')
            obj = dict(id='guide', group=0, num=1, x=10, y=12, gfx=7, text='Welcome trainer!')
            source = state / 'candidates/guide.py'
            source.write_text("def update(context,state):\n s=dict(state)\n s['visits']=s.get('visits',0)+len(context.get('interactions',[]))\n return {'state':s,'tiles':[],'objects':" + repr([obj]) + '}\n')
            server.start()
            try:
                self.assertTrue(admin_request(root + '/socket', dict(command='deploy', source_path=str(source)))['ok'])
                with WorldClient(root + '/socket', 'Alice', identity['token']) as client:
                    self.assertEqual(client.snapshot()['objects'], [obj])
                    client.send_state(1, 0, 1, 10, 13, 2, 7, 1, 'a'*16, 'b'*16)
                    client.interact(2, 'guide')
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline and server.inspect()['state'].get('visits') != 1:
                        time.sleep(.02)
                    self.assertEqual(server.inspect()['state']['visits'], 1)
                    time.sleep(.3)
                    self.assertEqual(server.inspect()['state']['visits'], 1)
                    events = server.db.execute("SELECT data FROM events WHERE kind='interaction'").fetchall()
                    self.assertEqual(len(events), 1)
                    self.assertEqual(json.loads(events[0][0])['object'], 'guide')
                    self.assertFalse(Path(identity['save_path']).exists())
            finally:
                server.close()
            server = WorldServer(root + '/socket', state)
            try:
                self.assertEqual(server.inspect()['objects'], [obj])
                self.assertEqual(server.inspect()['state']['visits'], 1)
                self.assertEqual(server._context()['interactions'], [])
            finally:
                server.close()

    def test_failed_interaction_tick_retries_durable_batch_after_restart(self):
        from world.server import WorldServer
        from world.client import WorldClient, admin_request
        import time
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            state = Path(root) / 'state'
            server = WorldServer(root + '/socket', state)
            identity = server.create_identity('Alice')
            obj = dict(id='guide', group=0, num=1, x=10, y=12, gfx=8, text='Welcome trainer!')
            source = state / 'candidates/guide.py'
            source.write_text("def update(c,s):\n if c.get('interactions'): raise ValueError('retry me')\n return " + repr(dict(state={}, tiles=[], objects=[obj])))
            server.start()
            try:
                self.assertTrue(admin_request(root + '/socket', dict(command='deploy', source_path=str(source)))['ok'])
                with WorldClient(root + '/socket', 'Alice', identity['token']) as client:
                    client.snapshot()
                    client.send_state(1, 0, 1, 10, 13, 2, 7, 1, 'a'*16, 'b'*16)
                    client.interact(2, 'guide')
                    deadline = time.monotonic()+3
                    while time.monotonic() < deadline and not server.inspect()['error']:
                        time.sleep(.02)
                    self.assertIn('retry me', server.inspect()['error'])
                    self.assertEqual(server.interaction_cursor, 0)
                    self.assertEqual(server.inspect()['objects'], [obj])
                    self.assertEqual(len(server._context()['interactions']), 1)
            finally:
                server.close()
            server = WorldServer(root + '/socket', state)
            server.start()
            try:
                self.assertEqual(len(server._context()['interactions']), 1)
                source.write_text("def update(c,s):\n return {'state':{'seen':len(c['interactions'])},'tiles':[],'objects':" + repr([obj]) + '}')
                self.assertTrue(admin_request(root + '/socket', dict(command='deploy', source_path=str(source)))['ok'])
                self.assertEqual(server.inspect()['state'], {'seen':1})
                self.assertEqual(server._context()['interactions'], [])
                self.assertGreater(server.interaction_cursor, 0)
            finally:
                server.close()

    def test_interaction_rejects_wrong_map_facing_distance_unready_and_replay(self):
        from world.server import WorldServer
        from world.client import WorldClient
        import time
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root + '/socket', root + '/state')
            server.objects = [dict(id='guide', group=0, num=1, x=10, y=12, gfx=7, text='Hello!')]
            server.start()
            try:
                for index, values in enumerate(((0,0,10,13,2,7,1), (0,1,10,13,1,7,1),
                                               (0,1,10,14,2,7,1), (0,0,0,0,1,7,0))):
                    identity = server.create_identity('bad'+str(index))
                    with self.subTest(values=values), WorldClient(root+'/socket', identity['id'], identity['token']) as client:
                        client.snapshot()
                        client.send_state(1, *values, 'a'*16, 'b'*16)
                        client.interact(2, 'guide')
                        with self.assertRaisesRegex(ValueError, 'MALFORMED'):
                            while True: client.snapshot()
                self.assertEqual(server.db.execute("SELECT count(*) FROM events WHERE kind='interaction'").fetchone()[0], 0)
                identity = server.create_identity('good')
                with WorldClient(root+'/socket', 'good', identity['token']) as client:
                    client.snapshot()
                    client.send_state(1, 0,1,10,13,2,7,1, 'a'*16, 'b'*16)
                    client.interact(2, 'guide')
                    client.interact(2, 'guide')
                    with self.assertRaisesRegex(ValueError, 'STALE'):
                        while True: client.snapshot()
                self.assertEqual(server.db.execute("SELECT count(*) FROM events WHERE kind='interaction'").fetchone()[0], 1)
            finally:
                server.close()

    def test_invalid_persisted_objects_quarantine_whole_overlay(self):
        from world.server import WorldServer
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root + '/socket', root + '/state')
            server.db.execute("INSERT INTO module(singleton,source,sha256,state,tiles,objects) VALUES(1,?,?,?,?,?)",
                ('def update(c,s): return {}', '0'*64, '{"bad":true}', '[[0,1,1,1,1,0]]', '[{}]'))
            server.db.commit()
            server.close()
            server = WorldServer(root + '/socket', root + '/state')
            try:
                self.assertEqual(server.inspect()['tiles'], [])
                self.assertEqual(server.inspect()['objects'], [])
                self.assertEqual(server.inspect()['state'], {})
                self.assertIsNone(server.candidate)
                self.assertIn('invalid persisted module', server.module_error)
            finally:
                server.close()

    def test_authenticated_control_coexists_with_native_and_intent_is_idempotent(self):
        from world.server import WorldServer
        from world.client import WorldClient, IntentClient
        from world.runtime_gm import IntentQueue
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root+'/sock', root+'/state')
            identity = server.create_identity('Alice')
            other = server.create_identity('Bob')
            server.start()
            try:
                with WorldClient(root+'/sock', 'Alice', identity['token']) as native:
                    native.snapshot()
                    with IntentClient(root+'/sock', 'Alice', identity['token']) as control:
                        result = control.submit_intent('I would like a guide.', request_id='first')
                        self.assertTrue(result['ok'], result)
                        identifier = result['id']
                        self.assertEqual(control.submit_intent('I would like a guide.', request_id='first')['id'], identifier)
                        self.assertEqual(control.intent_status(identifier)['request']['player'], 'Alice')
                        self.assertEqual(control.intent_status(identifier)['request']['status'], 'queued')
                        self.assertFalse(control.submit_intent('different payload', request_id='first')['ok'])
                        self.assertFalse(control.submit_intent('too soon', request_id='second')['ok'])
                        with IntentClient(root+'/sock', 'Bob', other['token']) as bob:
                            self.assertFalse(bob.intent_status(identifier)['ok'])
                            self.assertTrue(bob.submit_intent('I want to explore.', request_id='first')['ok'])
                    native.send_state(1,0,1,10,13,2,7,1,'a'*16,'b'*16)
                    native.snapshot()
                    self.assertEqual([p['id'] for p in server.inspect()['players']], ['Alice'])
                queue = IntentQueue(root+'/state')
                try:
                    rows = queue.status()['requests']
                    self.assertEqual(len(rows), 2)
                    self.assertEqual({r['player'] for r in rows}, {'Alice','Bob'})
                    item = queue.claim()
                    self.assertEqual(item['id'], identifier)
                    queue.finish(identifier, 'succeeded', {'ok':True, 'source_path':'private host path'})
                finally:
                    queue.close()
                with IntentClient(root+'/sock', 'Alice', identity['token']) as control:
                    status = control.intent_status(identifier)
                    self.assertEqual(status['request']['status'], 'succeeded')
                    self.assertNotIn('private host path', json.dumps(status))
                    self.assertNotIn('save_path', json.dumps(status))
            finally:
                server.close()

    def test_control_role_cannot_spoof_player_deploy_or_exceed_bounds(self):
        from world.server import WorldServer
        from world.client import WorldClient, IntentClient
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root+'/sock', root+'/state')
            identity = server.create_identity('Alice')
            server.start()
            try:
                with self.assertRaisesRegex(ValueError, 'AUTH'):
                    IntentClient(root+'/sock', 'Alice', '0'*64)
                with IntentClient(root+'/sock', 'Alice', identity['token']) as control:
                    self.assertFalse(control._request(dict(command='intent', request_id='spoof', text='Hi', player='Bob'))['ok'])
                    self.assertFalse(control._request(dict(command='deploy', source_path='/etc/passwd'))['ok'])
                    for text, key in (('x'*2049,'huge'), ('','blank'), ('hi','x'*65), ('hi','../escape')):
                        self.assertFalse(control.submit_intent(text, request_id=key)['ok'])
                    self.assertFalse(control._request(dict(command='events_since', cursor=0))['ok'])
                    with IntentClient(root+'/sock', 'Alice', identity['token']) as second:
                        with self.assertRaisesRegex(ValueError, 'FULL'):
                            IntentClient(root+'/sock', 'Alice', identity['token'])
                        with WorldClient(root+'/sock', 'Alice', identity['token']) as native:
                            self.assertEqual(native.snapshot()['peers'], {})
                    self.assertTrue(control.submit_intent('I would like to explore.', request_id='valid')['ok'])
                self.assertEqual(server.inspect()['players'], [])
            finally:
                server.close()

    def test_control_queue_caps_persist_across_reconnect(self):
        from world.server import WorldServer
        from world.client import IntentClient
        from world.runtime_gm import IntentQueue
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root+'/sock', root+'/state')
            identity = server.create_identity('Alice')
            queue = IntentQueue(root+'/state')
            try:
                for i in range(8):
                    queue.submit('Alice', 'optional purpose '+str(i), 'trusted-'+str(i))
                with queue.db:
                    queue.db.execute('UPDATE requests SET created=0')
            finally:
                queue.close()
            server.start()
            try:
                with IntentClient(root+'/sock', 'Alice', identity['token']) as client:
                    self.assertIn('full', client.submit_intent('another purpose',request_id='new')['error'])
                with IntentClient(root+'/sock', 'Alice', identity['token']) as client:
                    self.assertIn('full', client.submit_intent('another purpose',request_id='new')['error'])
                queue = IntentQueue(root+'/state')
                try:
                    self.assertEqual(len(queue.status()['requests']), 8)
                finally:
                    queue.close()
            finally:
                server.close()

    def test_admin_events_since_is_durable_bounded_and_independent_of_mechanic_cursor(self):
        from world.server import WorldServer
        from world.client import admin_request
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root+'/sock', root+'/state')
            with server.db:
                server._event('join', 'Alice')
                server._event('interaction', dict(player='Alice', object='guide'))
                first = server.revision
                server._event('interaction', dict(player='Bob', object='guide'))
                second = server.revision
            server.interaction_cursor = second
            server.start()
            try:
                result = admin_request(root+'/sock', dict(command='events_since', cursor=0, limit=1))
                self.assertTrue(result['ok'], result)
                self.assertEqual(result['cursor'], first)
                self.assertTrue(result['has_more'])
                self.assertEqual(result['events'], [dict(seq=first, kind='interaction', data=dict(player='Alice',object='guide'))])
                result = admin_request(root+'/sock', dict(command='events_since', cursor=first, limit=1))
                self.assertEqual(result['cursor'], second)
                self.assertFalse(result['has_more'])
                self.assertFalse(admin_request(root+'/sock',dict(command='events_since',cursor=-1))['ok'])
            finally:
                server.close()
            server = WorldServer(root+'/sock', root+'/state')
            server.start()
            try:
                result = admin_request(root+'/sock',dict(command='events_since',cursor=0))
                self.assertEqual([e['seq'] for e in result['events']], [first,second])
            finally:
                server.close()

    def test_identity_helper_and_cli(self):
        from world.server import create_identity
        import subprocess
        import sys
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            token = create_identity(root, 'Alice', token='c'*64)
            self.assertEqual(token, 'c'*64)
            self.assertEqual(create_identity(root, 'Alice'), token)
            with self.assertRaises(ValueError):
                create_identity(root, 'Alice', token='d'*64)
            result = subprocess.run([sys.executable, '-m', 'world.server', '--state-dir', root, '--create-identity', 'Alice'], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['token'], token)

    def test_blocking_client_full_snapshots(self):
        from world.server import WorldServer
        from world.client import WorldClient, admin_request
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root + '/socket', root + '/state')
            a, b = server.create_identity('Alice'), server.create_identity('Bob')
            server.start()
            try:
                with WorldClient(root + '/socket', 'Alice', a['token']) as alice:
                    alice.snapshot()
                    with WorldClient(root + '/socket', 'Bob', b['token']) as bob:
                        bob.snapshot()
                        bob.send_state(1, 0, 1, 20, 30, 1, 7, 1, 'a'*16, 'b'*16)
                        for _ in range(5):
                            snapshot = alice.snapshot()
                            if snapshot['peers']:
                                break
                        self.assertEqual(snapshot['peers']['Bob']['x'], 20)
                        self.assertEqual(snapshot['tiles'], [])
                        result = admin_request(root + '/socket', {'command':'inspect'})
                        player = next(p for p in result['players'] if p['id'] == 'Bob')
                        self.assertEqual(player['party_hash'], 'a'*16)
                        self.assertEqual(player['bag_hash'], 'b'*16)
                    self.assertEqual(alice.snapshot()['peers'], {})
            finally:
                server.close()

    def test_capacity_bounds_and_fragmented_handshake(self):
        from world.server import WorldServer
        from world.client import WorldClient
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root + '/socket', root + '/state')
            ids = [server.create_identity('p' + str(i)) for i in range(9)]
            server.start()
            clients = []
            try:
                for identity in ids[:8]:
                    clients.append(WorldClient(root + '/socket', identity['id'], identity['token']))
                with self.assertRaisesRegex(ValueError, 'ERROR FULL'):
                    WorldClient(root + '/socket', ids[8]['id'], ids[8]['token'])
                self.assertEqual(len(server.inspect()['players']), 8)
                self.assertTrue(all(len(c['out']) <= 65536 for c in server.connections.values()))
            finally:
                for client in clients:
                    client.close()
                server.close()
            server = WorldServer(root + '/socket', root + '/state')
            server.start()
            try:
                with socket.socket(socket.AF_UNIX) as sock:
                    sock.settimeout(2)
                    sock.connect(root + '/socket')
                    hello = ('HELLO 1 {id} {token}\n'.format(**ids[0])).encode()
                    sock.sendall(hello[:8])
                    sock.sendall(hello[8:])
                    with sock.makefile('rb') as stream:
                        self.assertTrue(stream.readline().startswith(b'WELCOME 1 p0 '))
                        self.assertTrue(stream.readline().startswith(b'BEGIN '))
                        self.assertEqual(stream.readline(), b'END\n')
                        sock.sendall(('STATE 1 256 0 1 1 1 1 1 ' + 'a'*16 + ' ' + 'b'*16 + '\n').encode())
                        self.assertEqual(stream.readline(), b'ERROR MALFORMED\n')
            finally:
                server.close()

    def test_failed_tick_retains_overlay_and_network_stays_responsive(self):
        from world.server import WorldServer
        from world.client import admin_request
        import time
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            state = Path(root) / 'state'
            (state / 'candidates').mkdir(parents=True)
            path = state / 'candidates/one.py'
            path.write_text("def update(context, state):\n if state.get('n', 0):\n  while True: pass\n return {'state': {'n':1}, 'tiles':[{'group':0,'num':0,'x':1,'y':2,'metatile':3,'collision':0}]}\n")
            from world.mechanics import MechanicRuntime
            server = WorldServer(root + '/socket', state, mechanics=MechanicRuntime(state, timeout=0.25))
            server.start()
            try:
                result = admin_request(root + '/socket', {'command':'deploy', 'source_path':str(path)})
                self.assertTrue(result['ok'], result)
                time.sleep(0.16)
                before = time.monotonic()
                result = admin_request(root + '/socket', {'command':'inspect'})
                self.assertLess(time.monotonic() - before, 0.2)
                time.sleep(0.3)
                result = admin_request(root + '/socket', {'command':'inspect'})
                self.assertEqual(result['state'], {'n':1})
                self.assertEqual(result['tiles'], [[0,0,1,2,3,0]])
                self.assertIn('timeout', result['error'])
            finally:
                server.close()

    def test_tile_omission_removes_previous_overlay_and_bad_deploy_rolls_back(self):
        from world.server import WorldServer
        from world.client import WorldClient, admin_request
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            state = Path(root) / 'state'
            (state / 'candidates').mkdir(parents=True)
            good, empty, bad = [state / ('candidates/' + name + '.py') for name in ('good','empty','bad')]
            good.write_text("def update(context,state):\n return {'state': {},'tiles':[{'group':0,'num':0,'x':1,'y':2,'metatile':3,'collision':0}]}\n")
            empty.write_text("def update(context,state):\n return {'state': {},'tiles':[]}\n")
            bad.write_text("def update(context,state):\n return {'state': {'corrupt': True},'tiles':[{'group':0,'num':0,'x':1,'y':2,'metatile':1024,'collision':0}]}\n")
            server = WorldServer(root + '/socket', state)
            identity = server.create_identity('Alice')
            server.start()
            try:
                with WorldClient(root + '/socket', 'Alice', identity['token']) as client:
                    client.snapshot()
                    self.assertTrue(admin_request(root + '/socket', {'command':'deploy','source_path':str(good)})['ok'])
                    snapshot = client.snapshot()
                    self.assertEqual(snapshot['peers'], {})
                    self.assertEqual(snapshot['tiles'], [[0,0,1,2,3,0]])
                    before = admin_request(root + '/socket', {'command':'inspect'})
                    self.assertFalse(admin_request(root + '/socket', {'command':'deploy','source_path':str(bad)})['ok'])
                    after = admin_request(root + '/socket', {'command':'inspect'})
                    for key in ('module_hash','state','tiles','revision'):
                        self.assertEqual(before[key], after[key])
                    self.assertTrue(admin_request(root + '/socket', {'command':'deploy','source_path':str(empty)})['ok'])
                    self.assertEqual(client.snapshot()['tiles'], [])
            finally:
                server.close()

    def test_transport_directory_and_provision_while_running(self):
        from world.server import WorldServer, create_identity
        from world.client import WorldClient, admin_request
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            state = Path(root) / 'state'
            path = state / 'transport/world.sock'
            transport_inode = None
            for _ in range(2):
                server = WorldServer(path, state)
                try:
                    server.start()
                    self.assertEqual(server.admin_path, str(state / 'admin.sock'))
                    self.assertEqual(list(path.parent.iterdir()), [path])
                    self.assertEqual(Path(server.admin_path).stat().st_mode & 0o777, 0o600)
                    if transport_inode is not None:
                        self.assertEqual(path.parent.stat().st_ino, transport_inode)
                    transport_inode = path.parent.stat().st_ino
                    self.assertTrue(admin_request(path, {'command': 'inspect'})['ok'])
                    token = create_identity(state, 'late_joiner')
                    self.assertEqual(create_identity(state, 'late_joiner'), token)
                    with WorldClient(path, 'late_joiner', token) as client:
                        self.assertEqual(client.snapshot()['peers'], {})
                finally:
                    server.close()
                self.assertFalse(path.exists())
                self.assertFalse((state / 'admin.sock').exists())
                self.assertEqual(list(path.parent.iterdir()), [])

    def test_explicit_admin_socket_cli_and_stale_restart(self):
        from world.server import WorldServer
        from world.client import admin_request
        import subprocess
        import sys
        import time
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            state = Path(root) / 'state'
            path = state / 'transport/world.sock'
            admin = Path(root) / 'control/admin.sock'
            proc = subprocess.Popen([
                sys.executable, '-B', '-m', 'world.server', '--socket', str(path),
                '--state-dir', str(state), '--admin-socket', str(admin)],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 3
                while not admin.exists() and proc.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertIsNone(proc.poll())
                self.assertTrue(admin_request(path, {'command': 'inspect'}, admin_path=admin)['ok'])
                self.assertEqual(list(path.parent.iterdir()), [path])
                self.assertFalse((state / 'admin.sock').exists())
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.communicate(timeout=3)
            self.assertTrue(admin.exists())
            server = WorldServer(path, state, admin_path=admin)
            try:
                server.start()
                self.assertEqual(server.admin_path, str(admin))
                self.assertTrue(admin_request(path, {'command': 'inspect'}, admin_path=admin)['ok'])
                self.assertEqual(list(path.parent.iterdir()), [path])
            finally:
                server.close()
            self.assertFalse(admin.exists())
            self.assertFalse(path.exists())

    def test_exclusive_authority_and_stale_socket_recovery(self):
        from world.server import WorldServer
        from world.client import admin_request
        import os
        import signal
        import subprocess
        import sys
        import time
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            path, state = root + '/socket', root + '/state'
            proc = subprocess.Popen([sys.executable, '-m', 'world.server', '--socket', path, '--state-dir', state], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 3
                while not Path(path + '.admin').exists() and proc.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertIsNone(proc.poll())
                self.assertTrue(admin_request(path, {'command':'inspect'})['ok'])
                duplicate = WorldServer(root + '/other', state)
                try:
                    with self.assertRaisesRegex(RuntimeError, 'already in use'):
                        duplicate.start()
                finally:
                    duplicate.close()
            finally:
                proc.kill()
                proc.communicate(timeout=3)
            server = WorldServer(path, state)
            try:
                server.start()
                self.assertTrue(admin_request(path, {'command':'inspect'})['ok'])
            finally:
                server.close()

    def test_malformed_admin_cannot_kill_service(self):
        from world.server import WorldServer
        from world.client import admin_request
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root + '/socket', root + '/state')
            server.start()
            try:
                with socket.socket(socket.AF_UNIX) as sock:
                    sock.settimeout(2)
                    sock.connect(root + '/socket.admin')
                    sock.sendall(b'['*1024 + b'\n')
                    response = sock.recv(4096)
                    self.assertTrue(response, 'malformed JSON closed authority loop')
                    self.assertFalse(json.loads(response)['ok'])
                self.assertTrue(admin_request(root + '/socket', {'command':'inspect'})['ok'])
            finally:
                server.close()

    def test_identity_is_persistent_and_save_paths_are_isolated(self):
        self.assertIsNotNone(importlib.util.find_spec('world.server'), 'world service missing')
        from world.server import WorldServer
        with tempfile.TemporaryDirectory(prefix='ew-', dir='/home/ayaan/projects/emerald-world-research') as root:
            server = WorldServer(root + '/socket', root + '/state')
            a = server.create_identity('Alice')
            b = server.create_identity('Bob')
            self.assertRegex(a['token'], r'^[0-9a-f]{64}$')
            self.assertNotEqual(a['save_path'], b['save_path'])
            self.assertEqual(Path(a['save_path']).name, 'game.sav')
            self.assertTrue(Path(a['save_path']).parent.is_dir())
            with self.assertRaises(ValueError):
                server.create_identity('../escape')
            server.close()
            server = WorldServer(root + '/socket', root + '/state')
            self.assertEqual(a, server.create_identity('Alice'))
            server.close()


if __name__ == '__main__':
    unittest.main()
