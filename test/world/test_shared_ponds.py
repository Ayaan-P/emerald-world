import json
import unittest
from world.shared_outdoor_palette import paint_biome,add_ponds
from world.shared_cave import SharedCave

class SharedPondTests(unittest.TestCase):
    def setUp(self):
        self.p={'rows':['#'*127]+['#'+'.'*125+'#']*125+['#'*127], 'spawn':[1,1], 'exit':[125,125]}
        self.base=paint_biome(self.p,'meadow',23)
    def test_seeded_ponds_are_shared_and_connected(self):
        blob,n=add_ponds(self.base,23,5)
        self.assertEqual((blob,n),add_ponds(self.base,23,5))
        self.assertEqual(n,5)
        c=SharedCave(blob); self.assertEqual(c.version,17)
        self.assertGreater(blob.count(b'#'),self.base.count(b'#'))
        self.assertTrue(c.walkable(1,1)); self.assertTrue(c.walkable(125,125))
        self.assertIn('XLPAINT',c.frames())
    def test_invalid_arguments(self):
        for seed,n in [(True,1),(-1,1),(1,True),(1,9)]:
            with self.assertRaises(ValueError): add_ponds(self.base,seed,n)
    def test_narrow_corridor_never_breaks_route(self):
        rows=[list('#'*127) for _ in range(127)]
        for y in range(1,126): rows[y][1]='.'
        for x in range(1,126): rows[125][x]='.'
        rows[124][125]='.'
        p={'rows':[''.join(row) for row in rows], 'spawn':[1,1], 'exit':[125,125]}
        base=paint_biome(p,'scrub',4); out,n=add_ponds(base,4,8)
        self.assertEqual(n,0); self.assertEqual(out,base); SharedCave(out)

class AgentPondTests(unittest.TestCase):
    def test_agent_activates_lakeside_area(self):
        import test_actor_runtime as fixture
        from world import actor_runtime as runtime
        case=fixture.ActorRuntimeTests();case.setUp();self.addCleanup(case.doCleanups)
        server=case.s;server.archive_generated_areas=True;server.persist_generated_cave=True
        blueprint=dict(rooms=[[3,3,20,18],[75,80,25,20]],links=[[0,1]],entrance_room=0,exit_room=1,style='rooms',seed=357,corridor_width=3)
        args=dict(label='Lake Path',layout='connected_shapes',blueprint=json.dumps(blueprint,separators=(',',':')),biome='meadow',seed=42,ponds=3)
        case.apply(dict(id='lake',purpose='Create a place.',steps=[dict(id='create',tool='world.create_lakeside_landscape',args=args,after=[])]))
        self.assertEqual(runtime.tick(server,now=10)['status'],'succeeded')
        self.assertEqual(server.shared_cave.version,17)
