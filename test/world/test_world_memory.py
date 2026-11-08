"""Exercise durable history at real authority commit points, without sockets."""
from concurrent.futures import Future
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from test_shared_generated_cave import MemoryAuthority, BLOB
import test_shared_terrain_world
from world import gm, world_memory
from world.mechanics import Candidate


class WorldMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.server = self.open()

    def open(self):
        return MemoryAuthority(self.root/'socket', self.root/'world',
                               persist_generated_cave=True, archive_generated_areas=True)

    def tearDown(self):
        self.server.close()
        self.tmp.cleanup()

    def admin(self, request):
        conn = dict(id=None, out=bytearray(), closing=False, sock=object())
        self.server._admin_line(conn, json.dumps(request).encode())
        return json.loads(conn['out'])

    def test_history_context_restart_and_noop(self):
        identity = self.server._replace_cave(BLOB)
        context = self.server.inspect()['world_memory']
        self.assertEqual(context['recent'][0]['event'], 'area_activated')
        self.assertEqual(context['active_area']['revision'], identity)
        self.server._replace_cave(BLOB)
        self.assertEqual(len(self.server.memory.history()['events']), 1)
        self.server.close()
        self.server = self.open()
        restored = self.server.inspect()['world_memory']
        self.assertEqual(context['world_id'], restored['world_id'])
        self.assertEqual(context['active_area'], restored['active_area'])
        self.assertEqual(context['recent'], restored['recent'])
        self.assertIn(context['world_id'], gm._prompt('Continue building', self.server.inspect()))
        self.assertIn('area_activated', gm._prompt('Continue building', self.server.inspect()))

    def test_explicit_continuation_stale_and_independent_places(self):
        old = self.server._replace_cave(BLOB)
        place = self.server.inspect()['world_memory']['active_area']['place_id']
        changed = BLOB[:168] + b'#' + BLOB[169:]
        new = self.server._replace_cave(changed, previous_revision=old)
        self.assertEqual(place, self.server.inspect()['world_memory']['active_area']['place_id'])
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.server._replace_cave(BLOB, previous_revision=old)
        self.assertEqual(self.server.shared_cave.identity, new)
        # Choosing another existing revision preserves its recorded logical place.
        self.server.activate_generated_area(old)
        self.assertEqual(place, self.server.inspect()['world_memory']['active_area']['place_id'])
        separate = BLOB[:169] + b'#' + BLOB[170:]
        other = self.server._replace_cave(separate)
        self.assertNotEqual(place, self.server.inspect()['world_memory']['active_area']['place_id'])
        with self.assertRaisesRegex(ValueError, 'another place'):
            self.server._replace_cave(BLOB, previous_revision=other)
        self.assertEqual(self.server.shared_cave.identity, other)

    def test_labels_are_history_not_identity(self):
        identity = self.server._replace_cave(BLOB, label='Old Harbor')
        place = self.server.inspect()['world_memory']['active_area']['place_id']
        self.server._replace_cave(BLOB, label='New Harbor')
        events = self.server.memory.history()['events']
        self.assertEqual(events[0]['label'], 'Old Harbor')
        self.assertEqual(events[1]['event'], 'area_named')
        self.assertEqual(events[1]['before'], 'Old Harbor')
        self.assertEqual(events[1]['after'], 'New Harbor')
        self.assertEqual(place, self.server.inspect()['world_memory']['active_area']['place_id'])
        self.server._replace_cave(BLOB, label='New Harbor')
        self.assertEqual(len(self.server.memory.history()['events']), 2)

    def test_atomic_terrain_and_readable_before_after(self):
        blob = test_shared_terrain_world.SharedTerrainWorld().blob()
        identity = self.server._replace_cave(blob)
        self.server.set_shared_terrain(identity, [dict(x=2, y=2, terrain='tall_grass')])
        event = self.server.memory.history()['events'][-1]
        self.assertEqual(event['event'], 'terrain_changed')
        self.assertEqual(event['tiles'], [dict(x=2, y=2, before='original', after='tall_grass')])
        before = self.server._active_terrain()
        count = self.server.db.execute('SELECT count(*) FROM events').fetchone()[0]
        with patch.object(self.server.memory, 'append', side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(ValueError):
                self.server.set_shared_terrain(identity, [dict(x=2, y=2, terrain='grass')])
        self.assertEqual(before, self.server._active_terrain())
        self.assertEqual(count, self.server.db.execute('SELECT count(*) FROM events').fetchone()[0])
        self.assertEqual(self.server.revision, event['seq'])
        self.server.close()
        self.server = self.open()
        self.assertEqual(before, self.server._active_terrain())
        self.assertEqual(event, self.server.memory.history()['events'][-1])

    def test_area_history_failure_rolls_back_actual_publication(self):
        identity = self.server._replace_cave(BLOB)
        with patch.object(self.server.memory, 'append', side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(ValueError):
                self.server._replace_cave(BLOB[:168] + b'#' + BLOB[169:], previous_revision=identity)
        self.assertEqual(self.server.shared_cave.identity, identity)
        self.assertEqual(self.server.db.execute('SELECT template FROM generated_cave').fetchone()[0], BLOB)
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM world_places').fetchone()[0], 1)

    def commit_mechanic(self, objects, state=None, kind='tick', tiles=None):
        source = 'def update(context, state):\n    return {"state": state, "tiles": []}\n'
        candidate = Candidate(source, hashlib.sha256(source.encode()).hexdigest())
        future = Future()
        future.set_result((candidate, dict(state=state or {}, tiles=tiles or [], objects=objects)))
        self.server.job = (future, kind, None, 0)
        self.server._poll_mechanics()

    def test_real_mechanic_commit_not_polling_diffs_and_private_state_excluded(self):
        npc = dict(id='keeper', group=0, num=9, x=8, y=8, gfx=7, text='Bridge opened.')
        self.commit_mechanic([npc], {'token':'never-in-history'}, 'deploy')
        first = self.server.memory.history()['events'][-1]
        self.assertEqual(first['event'], 'mechanic_changed')
        self.assertEqual(first['after']['objects'], [npc])
        self.assertEqual(first['places'], ['native:LittlerootTown'])
        self.assertNotIn('never-in-history', json.dumps(first))
        # Two confirmed changes between observations both survive.
        npc2 = dict(npc, text='Bridge closed.')
        self.commit_mechanic([npc2])
        self.commit_mechanic([npc])
        history = self.server.memory.history(place_id='native:LittlerootTown')['events']
        self.assertEqual(len(history), 3)
        self.assertEqual(history[1]['after']['objects'][0]['text'], 'Bridge closed.')
        self.commit_mechanic([dict(npc, x=9)], {'clock':42})
        self.assertEqual(len(self.server.memory.history()['events']), 3)
        self.assertEqual(self.server.objects[0]['x'], 9)

    def test_failed_mechanic_history_cannot_commit_module(self):
        self.commit_mechanic([], {}, 'deploy')
        before = self.server.db.execute('SELECT state FROM module').fetchone()[0]
        revision = self.server.revision
        with patch.object(self.server.memory, 'append', side_effect=sqlite3.OperationalError('disk full')):
            self.commit_mechanic([], {'new':True}, 'deploy')
        self.assertEqual(self.server.db.execute('SELECT state FROM module').fetchone()[0], before)
        self.assertEqual(self.server.revision, revision)
        self.assertEqual(len(self.server.memory.history()['events']), 1)

    def test_bounded_pagination_and_stable_cutoff(self):
        with self.server.db:
            for index in range(40):
                self.server.memory.append('test', dict(place_id='area:a', value=index))
        first = self.admin(dict(command='world_history', limit=7, place_id='area:a'))
        with self.server.db:
            self.server.memory.append('later', dict(place_id='area:a'))
        events = first['events'][:]
        page = first
        while page['has_more']:
            page = self.admin(dict(command='world_history', after=page['cursor'], through=first['through'], limit=7, place_id='area:a'))
            events.extend(page['events'])
        self.assertEqual([event['value'] for event in events], list(range(40)))
        self.assertEqual(page['cursor'], first['through'])
        self.assertEqual(self.server.memory.history(place_id='area:none')['events'], [])
        for bad in (dict(after=True), dict(limit=65), dict(after=-1), dict(through=-1)):
            self.assertFalse(self.admin(dict(command='world_history', **bad))['ok'])
        tail = self.server.inspect()['world_memory']
        self.assertTrue(tail['older_history_available'])
        self.assertEqual(len(tail['recent']), 16)

    def test_transport_budget_full_geometry_history_and_existing_state(self):
        from world import wilds_events
        rows = ['#'*63]+['#'+'.'*61+'#']*61+['#'*63]
        blob = wilds_events.encode({'rows':rows,'spawn':[1,1],'exit':[61,61]},
                                  [{'gfx':7,'text':'Hi!'}],
                                  {'initial':0,'rules':[{'state':0,'npc':1,'next':1,'text':'Hi!'}]})
        identity = self.server._replace_cave(blob)
        coords = [(x,y) for x in range(2,61) for y in range(2,61)][:512]
        changes = [dict(x=x,y=y,terrain='grass') for x,y in coords]
        for i in range(0,512,64):
            self.server.set_shared_terrain(identity, changes[i:i+64])
        self.server.set_shared_geometry(identity, [], replace=True)
        self.server.module_state = {'existing':'x'*32000}
        inspection = self.server.inspect()
        self.assertLess(len(json.dumps(inspection).encode()), 65536)
        page = self.admin(dict(command='world_history',limit=64))
        self.assertLess(len(json.dumps(page).encode()), 65536)
        self.assertTrue(page['has_more'])
        last = self.admin(dict(command='world_history', after=page['cursor'], through=page['through']))
        self.assertEqual(len(last['events'][-1]['tiles']),512)
        self.assertLess(len(json.dumps(last).encode()),65536)
        self.assertFalse(self.admin(dict(command='world_history',through=page['through']+1))['ok'])
        self.assertIsNone(self.server.module_error)

    def test_player_cannot_read_admin_history(self):
        identity = self.server.create_identity('Alice')
        conn = dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.server._line(conn, ('HELLO 1 Alice '+identity['token']).encode())
        conn['out'].clear()
        self.server._line(conn, b'{"command":"world_history"}')
        self.assertNotIn(self.server.memory.world_id.encode(), conn['out'])
        self.assertIn(b'ERROR',conn['out'])

    def test_existing_events_are_not_relabelled_or_given_fake_dates(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,kind TEXT,data TEXT)')
        db.execute("INSERT INTO events VALUES (1, 'interaction', '{}')")
        memory = world_memory.WorldMemory(db)
        self.assertEqual(memory.history()['events'], [])
        self.assertEqual(db.execute("SELECT value FROM world_memory_metadata WHERE key='coverage_start_seq'").fetchone()[0], '1')
        self.assertEqual(db.execute('SELECT data FROM events').fetchone()[0], '{}')
        db.close()

    def test_trainer_projection_is_private_explicit_and_allowlisted(self):
        view = world_memory.trainer_view(dict(ok=True, state=dict(frame=7, map=[0,9], pos=[8,8],
            party=[dict(slot=0,species=25,level=4,hp=10,moves=[dict(id=33,pp=30,token='secret')],token='secret')],
            token='secret', save_path='/private/save', other_players=[{'party':[1]}])))
        self.assertEqual(view['source'], 'live_native_observation')
        self.assertEqual(view['state']['party'][0]['species'],25)
        self.assertNotIn('secret',json.dumps(view))
        self.assertNotIn('other_players',json.dumps(view))
        self.assertIn('event_state',view['missing'])
        self.assertNotIn('party',world_memory.trainer_view(dict(ok=True,state={}))['state'])
        with self.assertRaises(ValueError):world_memory.trainer_view(dict(ok=False,state={}))

    def test_private_cli_exclusive_output(self):
        target = self.root/'trainer.json'
        with patch('world.player.PlayerClient') as client:
            client.return_value.__enter__.return_value.observe.return_value = dict(ok=True,state={'frame':1})
            world_memory.main(['trainer-view','--endpoint','private.sock','--output',str(target)])
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(target.read_text())['kind'],'private_trainer_view')
            with self.assertRaises(SystemExit):
                world_memory.main(['trainer-view','--endpoint','private.sock','--output',str(target)])
        self.assertEqual(self.server.memory.history()['events'], [])


if __name__ == '__main__':unittest.main()
