from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import test_actor_geometry as fixture
from world import actor_runtime as runtime


class SpaceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.GeometryTests(); self.f.setUp()
        self.addCleanup(self.f.doCleanups); self.s = self.f.s

    def plan(self, actor='harbor_guide', reservations=None):
        state = deepcopy(self.s.module_state)
        c = state['world_characters'][actor]; c['version'] += 1
        blueprint = dict(seed=415, loops=0, landmarks=[dict(id='clearing', x=72,y=69,radius=2),
            dict(id='further', x=90,y=90,radius=2)], reservations=reservations or [])
        c['plan'] = dict(id='extend_place',purpose='Connect new usable space.',steps=[dict(id='build',
            tool='world.extend_space', args=dict(revision=self.s.shared_cave.identity,
            blueprint=json.dumps(blueprint,separators=(',',':'))),after=[])])
        self.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects))
        self.assertIsNone(self.s.module_error)

    def test_real_publication_preserves_floor_place_actors_restart(self):
        old=self.s.shared_cave; self.plan()
        self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
        new=self.s.shared_cave
        self.assertNotEqual(old.identity,new.identity)
        self.assertTrue(new.walkable(72,70))
        for y in range(127):
            for x in range(127):
                if old.walkable(x,y):self.assertTrue(new.walkable(x,y))
        self.assertEqual(self.s.memory.place(old.identity),self.s.memory.place(new.identity))
        self.assertTrue(all(o['region_revision']==new.identity for o in self.s.objects))
        saved=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE step='build'").fetchone()[0])
        self.assertGreater(saved['opened_tiles'],0)
        self.s.close(); self.f.f.f.f.f.server=self.f.f.f.f.f.open(); self.s=self.f.f.f.f.f.server
        self.assertEqual(self.s.shared_cave.identity,new.identity)
        self.assertIsNone(runtime.tick(self.s,now=20))

    def test_second_actor_and_reserved_existing_floor(self):
        self.plan('second', [[20,20,2,2]])
        old=self.s.shared_cave.identity
        self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
        self.assertEqual(self.s.shared_cave.identity,old)

    def test_second_actor_executes(self):
        self.plan('second')
        self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
        self.assertTrue(self.s.shared_cave.walkable(72,70))

    def test_occupied_refuses(self):
        self.plan();old=self.s.shared_cave.identity
        self.f.f.f.f.connect_shared_xl('Bob')
        self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
        self.assertEqual(self.s.shared_cave.identity,old)

    def test_atomic_receipt_failure(self):
        self.plan(); old=self.s.shared_cave.identity; original=runtime._receipt
        def fail(server,actor,row,plan,step,status,result):
            if status=='succeeded':raise ValueError('injected failure')
            return original(server,actor,row,plan,step,status,result)
        with patch.object(runtime,'_receipt',side_effect=fail):
            self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
        self.assertEqual(self.s.shared_cave.identity,old)
        self.assertTrue(all(o['region_revision']==old for o in self.s.objects))

    def test_extend_then_navigate_uses_committed_revision(self):
        self.plan()
        state=deepcopy(self.s.module_state)
        c=state['world_characters']['harbor_guide']; c['version']+=1
        c['plan']['id']='extend_and_go'
        c['plan']['steps'].append(dict(id='go',tool='world.navigate',
            args=dict(revision=dict(result='build',key='revision'),x=72,y=70),after=['build']))
        self.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects))
        self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
        self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending')
        nav=self.f.f.f; nav.f.candidate=self.s.candidate
        nav.advance(0,True)
        for tick in range(1,10):nav.advance(tick)
        self.assertEqual(runtime.tick(self.s,now=30)['status'],'succeeded')
        actor=next(o for o in self.s.objects if o['id']=='harbor_guide')
        self.assertEqual((actor['x'],actor['y']),(72,70))

    def test_sparse_place_gains_new_clearings_around_reserved_terrain(self):
        import hashlib
        from world.mechanics import Candidate
        rows=[]
        for y in range(127):
            rows.append(''.join('.' if 0<x<126 and 0<y<126 and
                (x in (1,2,124,125) or y in (1,2,70,71,124,125)) else '#'
                for x in range(127)))
        revision=self.s._replace_cave(b'EWGMAP0A'+''.join(rows).encode(),label='Sparse corridors')
        objects=[dict(o,region_revision=revision) for o in self.s.objects]
        state=deepcopy(self.s.module_state)
        for c in state['world_characters'].values():
            c['version']+=1;c['evidence']=[self.s.memory.history()['events'][-1]['seq']]
        source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects)+')\n'
        self.f.f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        self.f.f.f.f.commit(dict(state=state,tiles=[],objects=objects))
        self.assertIsNone(self.s.module_error)
        self.assertFalse(self.s.shared_cave.walkable(90,90))
        self.plan('second',[[80,80,4,4]])
        self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
        self.assertTrue(self.s.shared_cave.walkable(90,90))
        self.assertFalse(self.s.shared_cave.walkable(81,81))
        saved=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE step='build'").fetchone()[0])
        self.assertGreater(saved['opened_tiles'],100)
