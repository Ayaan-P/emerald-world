import json
import unittest
from world.shared_outdoor_palette import paint_biome, add_ponds, add_trail
from world.shared_cave import SharedCave


class SharedTrailTests(unittest.TestCase):
    def setUp(self):
        rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127]
        proposal={'rows':rows,'spawn':[1,1],'exit':[125,125]}
        self.blob,_=add_ponds(paint_biome(proposal,'grassland',32),32,5)

    def test_trail_changes_palette_not_collision(self):
        before=SharedCave(self.blob)
        out,steps,changed=add_trail(self.blob,'sand',3)
        self.assertEqual((out,steps,changed),add_trail(self.blob,'sand',3))
        after=SharedCave(out)
        self.assertGreater(steps,0); self.assertGreater(changed,0)
        self.assertEqual(before._rows,after._rows)
        self.assertEqual(after.version,17)
        self.assertEqual(after.palette[1*127+1],ord('.'))
        for i,b in enumerate(before.palette):
            if b in (ord('#'),ord('r')): self.assertEqual(after.palette[i],b)
        self.assertIn(ord('s'),after.palette)

    def test_bad_arguments_and_unreachable_are_rejected(self):
        for terrain,width in [('water',1),('sand',2),('grass',True)]:
            with self.assertRaises(ValueError): add_trail(self.blob,terrain,width)
        blocked=bytearray(self.blob); blocked[8+127+1]=ord('#')
        with self.assertRaises(ValueError): add_trail(bytes(blocked),'sand',1)

    def test_real_author_plan(self):
        import test_actor_runtime as fixture
        from world import actor_runtime as runtime
        case=fixture.ActorRuntimeTests(); case.setUp(); self.addCleanup(case.doCleanups)
        server=case.s;server.archive_generated_areas=True;server.persist_generated_cave=True
        blueprint=dict(rooms=[[3,3,20,18],[75,80,25,20]],links=[[0,1]],entrance_room=0,exit_room=1,style='rooms',seed=357,corridor_width=3)
        args=dict(label='Trail',layout='connected_shapes',blueprint=json.dumps(blueprint,separators=(',',':')),biome='meadow',seed=42,ponds=2,trail='sand',trail_width=3)
        case.apply(dict(id='trail',purpose='Create a route.',steps=[dict(id='create',tool='world.create_trailed_landscape',args=args,after=[])]))
        self.assertEqual(runtime.tick(server,now=10)['status'],'succeeded')
        self.assertEqual(server.shared_cave.version,17)
        self.assertIn(ord('s'),server.shared_cave.palette)

class NetworkTrailTests(unittest.TestCase):
    def test_actor_network_connects_all_landmarks(self):
        import test_actor_runtime as fixture
        from world import actor_runtime as runtime
        case=fixture.ActorRuntimeTests();case.setUp();self.addCleanup(case.doCleanups)
        server=case.s;server.archive_generated_areas=True;server.persist_generated_cave=True
        plan=dict(seed=11,landmarks=[dict(id='grove',x=20,y=90,radius=5),dict(id='pond',x=90,y=25,radius=5)],reservations=[],loops=0)
        args=dict(label='Crossroads',layout='clearings',blueprint=json.dumps(plan,separators=(',',':')),biome='meadow',seed=22,ponds=3,trail='sand',trail_width=1)
        case.apply(dict(id='network',purpose='Connect outdoor clearings.',steps=[dict(id='create',tool='world.create_landscape_network',args=args,after=[])]))
        self.assertEqual(runtime.tick(server,now=10)['status'],'succeeded')
        cave=server.shared_cave
        self.assertEqual(cave.version,17)
        for site in plan['landmarks']:
            self.assertTrue(cave.walkable(site['x'],site['y']))
            self.assertEqual(cave.palette[site['y']*127+site['x']],ord('s'))
        self.assertEqual(cave.palette[127+1],ord('.'))

    def test_invalid_endpoint_rejected(self):
        for p in [((-1,3),(1,1)),((True,3),(1,1)),((1,1),(126,1))]:
            with self.assertRaises(ValueError):add_trail(SharedTrailTests_blob(),'sand',1,endpoints=p)

def SharedTrailTests_blob():
    rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127]
    return paint_biome(dict(rows=rows,spawn=[1,1],exit=[125,125]),'meadow',1)
