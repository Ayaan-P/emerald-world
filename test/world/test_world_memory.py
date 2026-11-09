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

    def test_dormant_places_survive_and_can_be_inspected_without_activation(self):
        harbor = self.server._replace_cave(BLOB, label='Cedar Harbor')
        place = self.server.memory.place(harbor)
        revised = self.server._replace_cave(BLOB[:168]+b'#'+BLOB[169:],
                                            label='Cedar Harbor',previous_revision=harbor)
        forest = self.server._replace_cave(BLOB[:169]+b'#'+BLOB[170:],label='Pine Forest')
        self.server.close()
        self.server = self.open()
        before = self.server.memory.history()
        result = self.admin(dict(command='world_recall',through=before['through'],terms=['cedar']))
        saved = result['saved_places']
        self.assertEqual({p['revision'] for p in saved['revisions']},{harbor,revised})
        self.assertEqual({p['place_id'] for p in saved['revisions']},{place})
        self.assertTrue(all(not p['active'] for p in saved['revisions']))
        detail = self.admin(saved['revisions'][0]['inspect_request'])
        self.assertTrue(detail['ok'])
        self.assertEqual(detail['side'],31)
        self.assertEqual(detail['place_id'],place)
        self.assertEqual(len(detail['rows']),31)
        self.assertEqual(self.server.shared_cave.identity,forest)
        self.assertEqual(self.server.memory.history(),before)
        page = self.admin(dict(command='saved_places',limit=1))
        self.assertTrue(page['has_more'])
        second = self.admin(dict(command='saved_places',limit=1,after=page['cursor']))
        self.assertNotEqual(page['revisions'][0]['revision'],second['revisions'][0]['revision'])
        self.assertFalse(self.admin(dict(command='inspect_saved_place',revision='bad'))['ok'])
        self.assertFalse(self.admin(dict(command='saved_places',limit=100))['ok'])
        # Read-only discovery does not relax the existing multiplayer barrier.
        self.server.peers[1] = dict(state=[*self.server.cave_map,1,1],closing=False)
        with self.assertRaisesRegex(ValueError,'occupied'):
            self.server.activate_generated_area(harbor)
        self.server.peers.clear()
        self.server.activate_generated_area(harbor)
        self.assertEqual(self.server.memory.place(harbor),place)

    def test_dormant_destination_reaches_builder_after_restart(self):
        harbor = self.server._replace_cave(BLOB,label='Cedar Harbor')
        self.server._replace_cave(BLOB[:168]+b'#'+BLOB[169:],label='Pine Forest')
        self.server.close()
        self.server = self.open()
        proposals=[]
        def transport(_socket,request,timeout):
            if request['command']=='deploy':
                proposals.append(Path(request['source_path']).read_text())
                return dict(ok=False,error='proposal captured, sandbox not executed')
            return self.admin(request)
        def author(prompt):
            context=json.loads(prompt.split('Request and snapshot follow:\n',1)[1])['inspection']
            destination=next(p for p in context['recalled_history']['saved_places']['revisions'] if p['revision']==harbor)
            self.assertFalse(destination['active'])
            self.assertEqual(destination['label'],'Cedar Harbor')
            source="def update(context,state):\n    return {'state':state,'tiles':[], 'objects':[{'id':'archivist','group':0,'num':9,'x':9,'y':8,'gfx':8,'text':'Cedar Harbor is preserved in the archive.'}]}\n"
            return dict(source=source,tests="def test_archivist():\n    assert update({}, {})['objects'][0]['id']=='archivist'\n")
        with patch('world.gm.admin_request',side_effect=transport):
            report=gm.author_and_deploy(self.root/'controller',self.root/'socket','Build an archivist remembering Cedar Harbor',author)
        self.assertFalse(report['ok'])
        self.assertEqual(len(proposals),1)
        self.assertIn('Cedar Harbor',proposals[0])
        self.assertNotEqual(self.server.shared_cave.identity,harbor)

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

    def test_dormant_terrain_is_inspected_and_restored_per_revision(self):
        blob=test_shared_terrain_world.SharedTerrainWorld().blob()
        revision=self.server._replace_cave(blob,label='Garden')
        self.server.set_shared_terrain(revision,[dict(x=2,y=2,terrain='tall_grass')])
        self.server._replace_cave(BLOB,label='Other cave')
        self.server.close()
        self.server=self.open()
        before=self.server.memory.history()
        detail=self.admin(dict(command='inspect_saved_place',revision=revision))
        self.assertTrue(detail['ok'])
        self.assertFalse(detail['active'])
        self.assertEqual(detail['terrain_overrides'],[dict(x=2,y=2,before='original',after='tall_grass')])
        self.assertEqual(self.server.memory.history(),before)
        self.server.activate_generated_area(revision)
        self.assertEqual(self.server._active_terrain()[0],detail['terrain_revision'])

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
        from world import inspection_transfer
        conn = {}
        first = inspection_transfer.begin(conn, inspection)
        self.assertLess(len(json.dumps(first).encode()), 65536)
        def exchange(request):
            chunk = inspection_transfer.next_chunk(conn, request)
            self.assertLess(len(json.dumps(chunk).encode()), 65536)
            return chunk
        self.assertEqual(inspection_transfer.receive(first, exchange), json.loads(json.dumps(inspection)))
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

    def bury_bridge_history(self):
        bridge = dict(id='keeper',group=0,num=9,x=8,y=8,gfx=7,text='Cedar bridge repaired.')
        self.commit_mechanic([bridge], {'private':'not-for-recall'}, 'deploy')
        origin = self.server.memory.history()['events'][-1]['seq']
        bridge = dict(bridge,text='Cedar bridge closed.')
        self.commit_mechanic([bridge])
        closure = self.server.memory.history()['events'][-1]['seq']
        for n in range(35):
            other = dict(id='cityguide',group=0,num=0,x=8,y=8,gfx=8,text='City notice '+str(n)+'.')
            self.commit_mechanic([bridge,other], {'private':'not-for-recall','clock':n})
        return origin, closure

    def test_recall_old_changes_not_unchanged_snapshot_mentions(self):
        origin, closure = self.bury_bridge_history()
        inspection = self.server.inspect()
        self.assertNotIn(origin,[event['seq'] for event in inspection['world_memory']['recent']])
        query = world_memory.recall_request('Build a Cedar bridge memorial.',inspection)
        recalled = self.admin(query)
        self.assertTrue(recalled['ok'],recalled)
        matches = [event['seq'] for event in recalled['events'] if 'literal_text_match' in event['selected_by']]
        self.assertEqual(matches,[origin,closure])
        self.assertFalse(recalled['more_text_matches'])
        self.assertNotIn('not-for-recall',json.dumps(recalled))
        self.assertLess(len(json.dumps(recalled).encode()),65536)
        self.assertLess(len(json.dumps(query).encode()),1024)
        self.server.close()
        self.server = self.open()
        self.assertEqual(recalled,self.admin(query))
        # Same snapshot mentions the keeper 35 times, but only two changes at
        # that place belong to its journal.
        self.assertEqual([e['seq'] for e in self.server.memory.history(place_id='native:LittlerootTown')['events']], [origin,closure])

    def test_recall_cutoff_and_index_rebuild_preserve_original_evidence(self):
        self.server._replace_cave(BLOB,label='Ancient Harbor')
        before = self.server.memory.history()['events']
        through = before[-1]['seq']
        self.server._replace_cave(BLOB,label='Modern Harbor')
        query = dict(command='world_recall',through=through,terms=['harbor'])
        self.assertEqual([e['seq'] for e in self.admin(query)['events']],[through])
        with self.server.db:
            self.server.db.execute('DROP TABLE world_memory_place_events')
            self.server.db.execute('DROP TABLE world_memory_lookup')
        self.server.memory = world_memory.WorldMemory(self.server.db)
        self.assertEqual(before,self.server.memory.history(through=through)['events'])
        self.assertEqual([e['seq'] for e in self.admin(query)['events']],[through])
        for bad in (dict(terms=['x%']),dict(terms=['word']*7),dict(places=['p']*5),dict(through=999999)):
            self.assertFalse(self.admin(dict(query,**bad))['ok'])

    def test_rebuilt_native_references_do_not_follow_numeric_catalog_changes(self):
        origin, closure = self.bury_bridge_history()
        with self.server.db:
            self.server.db.execute('DROP TABLE world_memory_place_events')
            self.server.db.execute('DROP TABLE world_memory_lookup')
        with patch('world.world_memory.native_place',return_value='native:DifferentRegion'):
            self.server.memory = world_memory.WorldMemory(self.server.db)
        self.assertEqual([e['seq'] for e in self.server.memory.history(place_id='native:LittlerootTown')['events']], [origin,closure])
        self.assertEqual(self.server.memory.history(place_id='native:DifferentRegion')['events'],[])

    def test_search_projection_failure_rolls_back_world_and_evidence(self):
        identity = self.server._replace_cave(BLOB)
        history = self.server.memory.history()
        with patch.object(self.server.memory,'_index',side_effect=sqlite3.OperationalError('index write failed')):
            with self.assertRaises(ValueError):
                self.server._replace_cave(BLOB[:168]+b'#'+BLOB[169:],previous_revision=identity)
        self.assertEqual(self.server.shared_cave.identity,identity)
        self.assertEqual(self.server.memory.history(),history)
        self.assertFalse(self.admin(dict(command='world_recall',through=None))['ok'])

    def test_controller_builds_proposal_from_buried_evidence_after_restart(self):
        origin, closure = self.bury_bridge_history()
        self.server.close()
        self.server = self.open()
        proposals = []
        calls = []
        def transport(_socket, request, timeout):
            calls.append(request['command'])
            if request['command'] == 'deploy':
                proposals.append(Path(request['source_path']).read_text())
                # This fixture checks recall -> proposal only. It does not fake
                # a sandbox/gameplay acceptance result.
                return dict(ok=False,error='proposal captured; execution outside this fixture')
            return self.admin(request)
        def author(prompt):
            document = json.loads(prompt.split('Request and snapshot follow:\n',1)[1])
            context = document['inspection']
            evidence = context['recalled_history']['events']
            repair = next(e for e in evidence if e['seq']==origin)
            self.assertEqual(repair['after']['objects'][0]['text'],'Cedar bridge repaired.')
            self.assertIn(closure,[e['seq'] for e in evidence])
            # Preserve the *current* closed bridge, rather than restoring its
            # historical repaired state, and add an adjacent commemorative NPC.
            objects = context['objects'] + [dict(id='memorial',group=0,num=9,x=9,y=8,gfx=8,text='Cedar bridge remembered.')]
            source = "# Historical evidence seq %d; current inspection retained.\ndef update(context, state):\n    return {'state': state, 'tiles': [], 'objects': %r}\n" % (origin,objects)
            return dict(source=source,tests="def test_memorial():\n    assert update({}, {})['objects'][-1]['id'] == 'memorial'\n")
        with patch('world.gm.admin_request',side_effect=transport):
            report = gm.author_and_deploy(self.root/'controller',self.root/'socket',
                                          'Build a Cedar bridge memorial.',author)
        self.assertEqual(calls,['inspect','world_recall','deploy'])
        self.assertFalse(report['ok'])
        self.assertIn(origin,report['history_evidence']['sequences'])
        self.assertIn('Cedar bridge remembered.',proposals[0])
        self.assertIn('Cedar bridge closed.',proposals[0])
        self.assertNotIn('not-for-recall',proposals[0])
        self.assertNotIn('memorial',[obj['id'] for obj in self.server.objects])
        saved = json.loads(Path(report['context_path']).read_text())
        self.assertEqual(saved['recalled_history']['world_id'],self.server.memory.world_id)

    def test_recall_failure_stops_authoring_instead_of_guessing(self):
        self.server._replace_cave(BLOB)
        called = []
        def transport(_socket,request,timeout):
            if request['command']=='world_recall':
                return dict(ok=True,world_id='wrong-world',through=0,events=[])
            return self.admin(request)
        with patch('world.gm.admin_request',side_effect=transport):
            report = gm.author_and_deploy(self.root/'controller',self.root/'socket','Continue harbor',lambda prompt:called.append(prompt))
        self.assertFalse(report['ok'])
        self.assertEqual(report['stage'],'recall')
        self.assertEqual(called,[])

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
