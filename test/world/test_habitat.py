"""Living grass driven by real accepted presence, with durable retry semantics."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_shared_generated_cave import MemoryAuthority
import test_shared_terrain_world
from world import shared_terrain, habitat_control


class HabitatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.blob = test_shared_terrain_world.SharedTerrainWorld().blob()
        self.server = self.open()
        self.server._replace_cave(self.blob)
        self.identity = self.server.shared_cave.identity

    def tearDown(self):
        self.server.close()
        self.temp.cleanup()

    def open(self):
        return MemoryAuthority(self.root/'socket', self.root/'world', persist_generated_cave=True,
                               archive_generated_areas=True, cave_template=self.blob)

    def owner(self, action='status', **kwargs):
        conn = dict(id=None, out=bytearray(), closing=False, sock=object())
        self.server._admin_line(conn, json.dumps(dict(command='habitat', action=action,
                                identity=self.identity, **kwargs)).encode())
        return json.loads(conn['out'])

    def configure(self, **kwargs):
        options = dict(tiles=[dict(x=1,y=2)], wear_steps=2, rest_steps=4)
        options.update(kwargs)
        result = self.owner('configure', **options)
        self.assertTrue(result['ok'], result)
        return result

    def connect(self, name='Alice', suffix='CAVE9T'):
        identity = self.server.create_identity(name)
        conn = dict(id=None, out=bytearray(), closing=False, state=None, seq=0, sock=object())
        self.server._line(conn, f'HELLO 1 {name} {identity["token"]} SOCIALTRAVELCHATRALLY{suffix}'.encode())
        self.server._line(conn, b'CAVE GET')
        self.server._line(conn, f'CAVE ACK {self.identity}'.encode())
        self.assertIn(b'CAVE OK', conn['out'])
        conn['out'].clear()
        return conn

    def step(self, conn, x, y, ready=1, sequence=None):
        g,n = self.server.wilds_map
        sequence = conn['seq'] + 1 if sequence is None else sequence
        self.server._line(conn, f'FIELD {sequence} {g} {n} {x} {y} 1 7 {ready} aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb'.encode())

    def terrain(self):
        return shared_terrain.validate(self.server.shared_cave, self.server._active_terrain()[1])[(1,2)]

    def test_real_steps_wear_and_regrow_for_both_clients(self):
        self.configure()
        alice = self.connect()
        bob = self.connect('Bob')
        self.step(alice,1,1) # Arrival is not a footstep.
        self.step(alice,1,2)
        self.step(alice,1,1)
        self.step(alice,1,2)
        self.assertTrue(self.owner()['habitat']['pending'])
        alice['out'].clear(); bob['out'].clear()
        self.server.habitats.flush(force=True)
        self.assertEqual(self.terrain(), 0)
        self.assertIn(b'CAVE TERRAIN', alice['out'])
        self.assertEqual(alice['out'], bob['out'])
        for point in ((2,2),(3,2),(2,2),(3,2)):
            self.step(alice,*point)
        self.server.habitats.flush(force=True)
        self.assertEqual(self.terrain(),1)
        self.assertEqual(self.owner()['habitat']['steps'],7)

    def test_idle_stale_unready_and_teleport_do_not_advance(self):
        self.configure()
        alice = self.connect()
        self.step(alice,1,1)
        self.step(alice,1,1)
        self.step(alice,1,2,sequence=alice['seq'])
        self.step(alice,3,2)
        self.step(alice,2,2,ready=0)
        self.step(alice,1,2)
        self.assertEqual(self.owner()['habitat']['steps'],0)
        self.assertEqual(self.terrain(),1)

    def test_restart_preserves_pressure_and_pending_changes(self):
        self.configure()
        alice = self.connect()
        for point in ((1,1),(1,2),(1,1),(1,2)):
            self.step(alice,*point)
        self.server.close(); self.server = self.open()
        self.assertTrue(self.owner()['habitat']['pending'])
        self.server.habitats.flush(force=True)
        self.assertEqual(self.terrain(),0)
        self.assertFalse(self.owner()['habitat']['pending'])
        self.assertEqual(self.owner()['habitat']['cells'][0]['wear'],2)

    def test_busy_delivery_retries_and_crash_ack_is_idempotent(self):
        with patch.object(self.server,'set_shared_terrain',side_effect=ValueError('trainer connection is busy')):
            result = self.configure()
        self.assertTrue(result['habitat']['pending'])
        self.assertEqual(result['error'],'trainer connection is busy')
        # Simulate crash after terrain committed but before acknowledgement saved.
        with patch.object(self.server.habitats,'_save',side_effect=__import__('sqlite3').OperationalError('disk full')):
            self.server.habitats.flush(force=True)
        revision = self.server._active_terrain()[0]
        self.assertTrue(self.owner()['habitat']['pending'])
        self.server.habitats.flush(force=True)
        self.assertEqual(self.server._active_terrain()[0],revision)
        self.assertFalse(self.owner()['habitat']['pending'])

    def test_invalid_requests_are_atomic_and_disable_preserves_surface(self):
        self.configure()
        original = self.owner()['habitat']
        for options in (dict(tiles=[dict(x=1,y=1)], wear_steps=2,rest_steps=4),
                        dict(tiles=[dict(x=1,y=2)]*2, wear_steps=2,rest_steps=4),
                        dict(tiles=[dict(x=1,y=2)], wear_steps=True,rest_steps=4)):
            self.assertFalse(self.owner('configure',**options)['ok'])
            self.assertEqual(self.owner()['habitat'],original)
        self.assertTrue(self.owner('disable')['terrain_preserved'])
        self.assertEqual(self.terrain(),1)
        self.assertFalse(self.owner()['enabled'])
        self.server.close(); self.server = self.open()
        self.assertFalse(self.owner()['enabled'])

    def test_repeated_configuration_does_not_reset_pressure(self):
        self.configure()
        alice = self.connect()
        self.step(alice,1,1); self.step(alice,1,2)
        self.assertEqual(self.configure()['habitat']['cells'][0]['wear'],1)

    def test_legacy_occupant_blocks_paint_without_losing_habitat(self):
        legacy = self.connect(suffix='CAVE9')
        self.step(legacy,1,1)
        result = self.configure()
        self.assertTrue(result['habitat']['pending'])
        self.assertEqual(result['error'],'incompatible trainer is inside')
        legacy['in_generated_cave'] = False
        legacy['state'] = None
        self.server.habitats.flush(force=True)
        self.assertFalse(self.owner()['habitat']['pending'])
        self.assertEqual(self.terrain(),1)

    def test_ecology_write_failure_does_not_reject_movement(self):
        self.configure()
        alice = self.connect()
        self.step(alice,1,1)
        with patch.object(self.server.habitats,'_save',side_effect=__import__('sqlite3').OperationalError('disk full')):
            self.step(alice,1,2)
        self.assertEqual(alice['state'][2:4],[1,2])
        self.assertNotIn(b'MALFORMED',alice['out'])
        self.assertEqual(self.owner()['habitat']['steps'],0)
        self.assertIn('persisted',self.owner()['error'])

    def test_absent_area_pauses_and_status_is_in_agent_inspection(self):
        self.configure()
        self.assertTrue(self.server.inspect()['habitat']['enabled'])
        original = self.server.shared_cave
        self.server.shared_cave = None
        try:
            self.server.habitats.flush(force=True)
            self.assertIsNone(self.server.inspect()['habitat'])
        finally:
            self.server.shared_cave = original
        self.assertEqual(self.owner()['habitat']['steps'],0)

    def test_trainer_control_cannot_configure_habitat(self):
        conn = dict(id='Alice', out=bytearray(), closing=False, sock=object())
        self.server._control_line(conn, json.dumps(dict(command='habitat',action='configure',
            identity=self.identity,tiles=[dict(x=1,y=2)],wear_steps=2,rest_steps=4)).encode())
        self.assertFalse(json.loads(conn['out'])['ok'])
        self.assertFalse(self.owner()['enabled'])

    def test_owner_control_uses_admin_socket(self):
        with patch('world.habitat_control.admin_request',return_value={'ok':True}) as send:
            habitat_control.request('/owner',self.identity)
        self.assertEqual(send.call_args.kwargs,dict(admin_path='/owner'))


if __name__ == '__main__':
    unittest.main()
