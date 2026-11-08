"""Inhabited construction: actual commits, authored ticks and exact scoped wire."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

import test_frontier_outposts as frontier
from world.mechanics import Candidate
from world.shared_cave import SharedCave
from world.character_chapters import compile_plan, chapter_step
from test_character_chapters import plan as chapter_plan


class Rebinding(unittest.TestCase):
    def setUp(self):
        self.f = frontier.FrontierAuthority(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.server = self.f.server
        # Widen the native approach so a standing NPC does not seal a route.
        rows = [bytearray(row) for row in self.server.shared_cave._rows]
        for y in range(5, 11):
            for x in range(1, 6): rows[y][x] = ord('.')
        self.blob = b'EWGMAP0A' + b''.join(rows)
        self.old = self.server._replace_cave(self.blob, label='Inhabited Frontier')
        self.f.old = self.old
        p = chapter_plan(); p['chapters'] = [p['chapters'][0]]
        obj = p['chapters'][0]['object']
        obj.update(group=self.server.wilds_map[0], num=self.server.wilds_map[1], x=3, y=7, region_revision=self.old)
        self.p = p
        source = compile_plan(p, self.server.inspect())
        definition = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()
        result = chapter_step(p, definition, self.server.memory.context(self.server)['through'],
                              self.server._context(), dict(state={}, tiles=[], objects=[]))
        self.commit(Candidate(source, hashlib.sha256(source.encode()).hexdigest()), result)
        self.initial_state = deepcopy(self.server.module_state)
        self.initial_objects = deepcopy(self.server.objects)
        self.original_source = self.server.candidate.source

    def commit(self, candidate, result):
        future = Future(); future.set_result((candidate, result))
        self.server.job = (future, 'tick', None, self.server.interaction_cursor)
        self.server.next_tick = float('inf'); self.server._poll_mechanics()
        self.assertIsNone(self.server.module_error)

    def build(self, plan=None):
        request = self.f.request(); request['previous_revision'] = self.server.shared_cave.identity
        if plan is not None: request['plan'] = plan
        return self.f.f.admin(request)

    def tick_fixture(self):
        # Only this test-authored source executes here. Production uses the
        # unchanged kernel-sandboxed mechanic runtime, not this fixture boundary.
        scope = {}; exec(self.server.candidate.source, scope)
        result = scope['update'](self.server._context(), deepcopy(self.server.module_state))
        self.commit(self.server.candidate, result)

    def send(self, conn, line):
        conn['out'].clear(); self.server._line(conn, line.encode()); return conn['out'].decode()

    def state(self, conn, group, num, x, y):
        return self.send(conn, f'STATE {conn["seq"]+1} {group} {num} {x} {y} 4 7 1 ' + 'a'*16 + ' ' + 'b'*16)

    def connect(self):
        token = self.server.create_identity('Traveler')['token']
        conn = dict(id=None, out=bytearray(), closing=False, state=None, seq=0, sock=object())
        self.assertIn('WELCOME', self.send(conn, f'HELLO 1 Traveler {token} SOCIALCAVE16CHAR1CHARQUEST1CHARREG1'))
        self.state(conn, 0, 9, 8, 8)
        self.assertIn('XLWILDS', self.send(conn, 'CAVE GET'))
        self.assertIn('CAVE OK', self.send(conn, 'CAVE ACK '+self.server.shared_cave.identity))
        self.state(conn, *self.server.wilds_map, 2, 7)
        return conn

    def test_rebind_preserves_identity_team_history_and_survives_authored_ticks_restart(self):
        history = self.server.memory.history()['events']
        result = self.build(); self.assertTrue(result['ok'], result)
        new = result['revision']; identity = self.p['id']
        self.assertEqual(result['rebound_characters'], [identity])
        self.assertEqual(self.server.module_state, self.initial_state)
        self.assertEqual(self.server.objects, [dict(self.initial_objects[0], region_revision=new)])
        self.assertEqual(self.server.memory.history()['events'][:len(history)], history)
        self.tick_fixture()
        self.assertEqual(self.server.objects[0]['region_revision'], new)
        self.assertEqual(self.server.module_state['world_characters'], self.initial_state['world_characters'])
        self.server.close(); self.f.f.server = self.f.f.open(); self.server = self.f.f.server; self.f.server = self.server
        self.assertIsNone(self.server.module_error)
        self.tick_fixture()
        self.assertEqual(self.server.objects[0]['region_revision'], new)
        second = self.build(dict(frontier.plan(), x=35, y=40)); self.assertTrue(second['ok'], second)
        self.tick_fixture()
        self.assertEqual(self.server.objects[0]['region_revision'], second['revision'])
        conn = self.connect()
        self.assertIn('REGION_OBJECT '+second['revision']+' '+identity, self.server._snapshot(conn))
        version = self.server.module_state['world_characters'][identity]['version']
        self.assertIn('CHARACTER_REJECT', self.send(conn, f'CHARACTER_CHALLENGE_REGION {conn["seq"]+1} {identity} {version} {self.old}'))
        reply = self.send(conn, f'CHARACTER_CHALLENGE_REGION {conn["seq"]+1} {identity} {version} {second["revision"]}')
        self.assertIn(f'{identity} {version} 1 ', reply)

    def test_other_archived_place_and_old_revision_do_not_show_or_admit_migrated_actor(self):
        result = self.build(); self.assertTrue(result['ok'], result)
        conn = self.connect(); self.state(conn, 0, 9, 8, 8)
        self.server.activate_generated_area(self.old)
        with patch('world.server.time.monotonic', return_value=conn['cave_next']+.01): self.send(conn, 'CAVE GET')
        self.send(conn, 'CAVE ACK '+self.old); self.state(conn, *self.server.wilds_map, 2, 7)
        self.assertNotIn(self.p['id'], self.server._snapshot(conn))
        version = self.initial_state['world_characters'][self.p['id']]['version']
        self.assertIn('CHARACTER_REJECT', self.send(conn, f'CHARACTER_CHALLENGE_REGION {conn["seq"]+1} {self.p["id"]} {version} {result["revision"]}'))

    def test_module_write_failure_rolls_back_map_source_actors_and_history(self):
        before = self.server.memory.history()
        self.server.db.execute("CREATE TRIGGER fail_rebind BEFORE UPDATE ON module BEGIN SELECT RAISE(ABORT,'fail'); END")
        result = self.build(); self.assertFalse(result['ok'])
        self.assertEqual(self.server.shared_cave.identity, self.old)
        self.assertEqual(self.server.objects, self.initial_objects)
        self.assertEqual(self.server.candidate.source, self.original_source)
        self.assertEqual(self.server.memory.history(), before)
        self.assertEqual(len(self.server.list_generated_areas()), 2)

    def test_pending_work_and_immutable_region_refuse(self):
        before = self.server.memory.history()
        self.server.job = (Future(), 'tick', None, 0)
        try: self.assertFalse(self.build()['ok'])
        finally: self.server.job = None
        self.server.deployment = ('pending',)
        try: self.assertFalse(self.build()['ok'])
        finally: self.server.deployment = None
        self.server.peers['busy'] = dict(character_pending={'id':self.p['id']})
        try: self.assertFalse(self.build()['ok'])
        finally: self.server.peers.clear()
        self.server.db.execute('INSERT INTO world_region_revisions VALUES (?,?)', (self.server.memory.place(self.old), self.old)); self.server.db.commit()
        result = self.build(); self.assertFalse(result['ok']); self.assertIn('immutable', result['error'])
        self.assertEqual(self.server.memory.history(), before)

    def test_new_access_trail_cannot_attach_through_a_standing_actor(self):
        obj = dict(self.initial_objects[0], x=5)
        result = dict(state=self.initial_state, tiles=[], objects=[obj])
        source = 'def update(context,state):\n return '+repr(result)+'\n'
        self.commit(Candidate(source, hashlib.sha256(source.encode()).hexdigest()), result)
        before = self.server.memory.history()
        outcome = self.build(dict(frontier.plan(), y=4))
        self.assertFalse(outcome['ok']); self.assertIn('blocks region routes', outcome['error'])
        self.assertEqual(self.server.shared_cave.identity, self.old)
        self.assertEqual(self.server.objects, [obj])
        self.assertEqual(self.server.memory.history(), before)

    def test_unrelated_actor_on_other_revision_is_preserved_without_rebinding(self):
        blob, _ = frontier.compile_outpost(self.blob, dict(frontier.plan(), x=60, y=50))
        other = self.server._replace_cave(blob, label='Other place')
        self.server.activate_generated_area(self.old)
        state = deepcopy(self.initial_state)
        actor = deepcopy(next(iter(state['world_characters'].values())))
        actor.update(object_id='other_guide', name='Other Guide')
        state['world_characters']['other_guide'] = actor
        other_obj = dict(self.initial_objects[0], id='other_guide', region_revision=other)
        result = dict(state=state, tiles=[], objects=self.initial_objects+[other_obj])
        source = 'def update(context,state):\n return '+repr(result)+'\n'
        self.commit(Candidate(source, hashlib.sha256(source.encode()).hexdigest()), result)
        outcome = self.build(); self.assertTrue(outcome['ok'], outcome)
        self.assertEqual(outcome['rebound_characters'], [self.p['id']])
        self.tick_fixture()
        self.assertEqual(self.server.objects[1], other_obj)
        conn = self.connect()
        snapshot = self.server._snapshot(conn)
        self.assertIn(self.p['id'], snapshot); self.assertNotIn('other_guide', snapshot)

    def test_old_source_location_change_requires_explicit_reauthor(self):
        self.assertTrue(self.build()['ok'])
        source = self.server.candidate.source
        # Replace only the test-authored source body, retaining its trusted
        # continuation wrapper, to simulate a later chapter on obsolete terrain.
        prefix = 'def update(context,state):\n return '+repr(dict(state=self.initial_state, tiles=[], objects=[dict(self.initial_objects[0], x=4)]))+'\n'
        wrapper = source[source.rfind('\ndef update(context, state, _previous=update):'):]
        scope = {}; exec(prefix+wrapper, scope)
        with self.assertRaisesRegex(ValueError, 'obsolete geometry'): scope['update']({}, {})


if __name__ == '__main__': unittest.main()
