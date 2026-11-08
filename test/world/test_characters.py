"""Exercise real authority persistence and public history without live sockets."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from test_shared_generated_cave import MemoryAuthority, BLOB
from world.characters import records
from world.mechanics import Candidate


class CharacterLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.server = self.open()
        self.server._replace_cave(BLOB, label='Cedar expedition')
        self.evidence = self.server.memory.history()['events'][0]['seq']
        self.npc = dict(id='may', group=0, num=9, x=9, y=8, gfx=8, text='Let us explore Cedar.')
        self.character = dict(version=1, name='May', role='Travelling field researcher',
            goals=['Explore Cedar'], relationships={}, team=[dict(species=277, level=12)],
            status='active', object_id='may', evidence=[self.evidence], reason='Responds to the new Cedar expedition area')

    def open(self):
        return MemoryAuthority(self.root/'socket', self.root/'world',
            persist_generated_cave=True, archive_generated_areas=True)

    def tearDown(self):
        self.server.close()
        self.tmp.cleanup()

    def commit(self, character, npc=None, kind='deploy'):
        # Prepared results stand in for isolated author execution, not a fake
        # sandbox/native pass. _poll_mechanics is the real atomic commit path.
        source = 'def update(context,state):\n    return {}\n'
        candidate = Candidate(source, hashlib.sha256(source.encode()).hexdigest())
        state = {'unrelated': {'keep': True}, 'world_characters': character}
        future = Future()
        future.set_result((candidate, dict(state=state, tiles=[], objects=[] if npc is None else [npc])))
        self.server.job = (future, kind, None, self.server.interaction_cursor)
        self.server.next_tick = float('inf')
        self.server._poll_mechanics()
        return self.server.module_error

    def test_character_visible_persistent_and_evolves_from_history(self):
        self.assertIsNone(self.commit({'may': self.character}, self.npc))
        self.assertEqual(self.server.objects[0]['id'], 'may')
        self.server.close()
        self.server = self.open()
        self.assertEqual(self.server.module_state['world_characters']['may'], self.character)
        self.assertEqual(self.server.objects, [self.npc])
        self.assertIn('world_history', self.server._context())
        revised = deepcopy(self.character)
        revised.update(version=2, goals=['Study the restored trail'],
            team=[dict(species=278, level=18)], reason='Author chose a stronger partner for Cedar exploration')
        npc = dict(self.npc, text='Our journey continues.', x=10)
        self.assertIsNone(self.commit({'may': revised}, npc, 'tick'))
        self.assertEqual(self.server.objects[0]['x'], 10)
        event = self.server.memory.history()['events'][-1]
        self.assertEqual(event['event'], 'character_changed')
        self.assertEqual(event['before']['team'][0]['level'], 12)
        self.assertEqual(event['after']['team'][0]['level'], 18)
        self.assertEqual(event['interpretation'], 'agent_authored_transition_not_proof_of_battle_or_catch')
        before = self.server.memory.history()
        self.commit({'may': revised}, npc, 'tick')
        self.assertEqual(before, self.server.memory.history())
        self.assertEqual(self.server.module_state['unrelated'], {'keep': True})

    def test_drop_stale_or_fabricated_evidence_preserves_last_good(self):
        self.commit({'may': self.character}, self.npc)
        for change in ({}, {'may': dict(self.character, version=3)},
                       {'may': dict(self.character, version=2, evidence=[999999])}):
            self.assertIsNotNone(self.commit(change, self.npc))
            self.assertEqual(self.server.module_state['world_characters']['may'], self.character)
        self.assertIsNotNone(self.commit({'may': self.character}))
        self.assertEqual(self.server.objects, [self.npc])

    def test_history_failure_rolls_back_character_and_overlay(self):
        self.commit({'may': self.character}, self.npc)
        updated = dict(self.character, version=2, status='away')
        append = self.server.memory.append
        def fail(event, data):
            if event == 'character_changed':
                raise sqlite3.OperationalError('fixture history failure')
            return append(event, data)
        before = self.server.memory.history()
        with patch.object(self.server.memory, 'append', side_effect=fail):
            self.assertIsNotNone(self.commit({'may': updated}))
        self.assertEqual(self.server.memory.history(), before)
        self.assertEqual(self.server.objects, [self.npc])
        self.server.close()
        self.server = self.open()
        self.assertEqual(self.server.module_state['world_characters']['may'], self.character)

    def test_retirement_is_explicit_and_identity_cannot_be_reused(self):
        self.commit({'may': self.character}, self.npc)
        retired = dict(self.character, version=2, status='retired')
        self.assertIsNone(self.commit({'may': retired}))
        self.assertEqual(self.server.objects, [])
        self.assertIsNotNone(self.commit({'may': dict(self.character, version=3)}, self.npc))
        self.assertEqual(self.server.module_state['world_characters']['may']['status'], 'retired')

    def peer(self, name='Alice', role='SOCIALCHAR1'):
        identity = self.server.create_identity(name)
        conn = dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.server._line(conn, ('HELLO 1 %s %s %s' % (identity['id'], identity['token'], role)).encode())
        self.assertIn(b'WELCOME', conn['out'])
        conn['out'].clear()
        conn['state'] = [0,9,8,8,4,7,1]
        conn['state_time'] = time.monotonic()
        return conn

    def send(self, conn, line):
        self.server._line(conn, line.encode())
        result = conn['out'].decode()
        conn['out'].clear()
        return result

    def test_authenticated_explicit_challenge_freezes_team_and_result_is_private(self):
        self.commit({'may': self.character}, self.npc)
        conn = self.peer()
        snapshot = self.server._snapshot(conn)
        self.assertIn('CHARACTER may 1', snapshot)
        self.assertIn('CHARACTER_BATTLE_V1 1 may 1 1 277 12',
                      self.send(conn, 'CHARACTER_CHALLENGE 1 may 1'))
        revised = dict(self.character, version=2, team=[dict(species=278,level=18)])
        self.commit({'may': revised}, self.npc)
        self.assertEqual(conn['character_pending']['team'], self.character['team'])
        self.assertIn('CHARACTER_REJECT', self.send(conn, 'CHARACTER_CHALLENGE 2 may 2'))
        other = self.peer('Bob')
        self.assertIn('CHARACTER_REJECT', self.send(other, 'CHARACTER_RESULT 1 may 1 1'))
        before = self.server.memory.history()['events']
        self.assertIn('CHARACTER_RESULT_ACK 1 may 1', self.send(conn, 'CHARACTER_RESULT 1 may 1 1'))
        self.assertEqual(self.server.memory.history()['events'], before)
        self.assertNotIn('character_pending', conn)
        self.assertIn('CHARACTER_REJECT', self.send(conn, 'CHARACTER_RESULT 1 may 1 1'))

    def test_old_clients_stale_location_or_version_cannot_start_battle(self):
        self.commit({'may': self.character}, self.npc)
        old = self.peer('Legacy', 'SOCIAL')
        self.assertNotIn('CHARACTER ', self.server._snapshot(old))
        self.assertIn('CHARACTER_REJECT', self.send(old, 'CHARACTER_CHALLENGE 1 may 1'))
        conn = self.peer()
        self.assertIn('CHARACTER_REJECT', self.send(conn, 'CHARACTER_CHALLENGE 1 may 2'))
        conn['state_time'] -= 6
        self.assertIn('CHARACTER_REJECT', self.send(conn, 'CHARACTER_CHALLENGE 1 may 1'))
        conn['state_time'] = time.monotonic()
        conn['state'][2] = 1
        self.assertIn('CHARACTER_REJECT', self.send(conn, 'CHARACTER_CHALLENGE 1 may 1'))
        self.assertNotIn('character_pending', conn)


    def test_private_relationships_invalid_species_and_boolean_level_rejected(self):
        for change in (dict(relationships={'human-trainer': 'friend'}),
                       dict(team=[dict(species=999999, level=12)]),
                       dict(team=[dict(species=277, level=True)])):
            with self.assertRaises(ValueError):
                records({'world_characters': {'may': dict(self.character, **change)}})


if __name__ == '__main__':
    unittest.main()
