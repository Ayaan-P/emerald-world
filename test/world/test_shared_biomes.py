import unittest
from world.shared_outdoor_palette import paint_biome
from world.shared_cave import SharedCave

class SharedBiomeTests(unittest.TestCase):
    def setUp(self):
        rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127]
        self.proposal={'rows':rows,'spawn':[1,1],'exit':[125,125]}

    def test_biomes_are_deterministic_connected_shared_maps(self):
        outputs=[]
        for name in ('meadow','dunes','grassland','scrub'):
            blob=paint_biome(self.proposal,name,42)
            self.assertEqual(blob,paint_biome(self.proposal,name,42))
            cave=SharedCave(blob)
            self.assertEqual(cave.version,17)
            self.assertEqual(sum(row.count(ord('.')) for row in cave._rows),125*125)
            self.assertEqual(cave.palette[128],ord('.'))
            outputs.append(blob)
        self.assertEqual(len(set(outputs)),4)
        self.assertNotEqual(outputs[0],paint_biome(self.proposal,'meadow',43))

    def test_validation_rejects_bad_inputs(self):
        for biome,seed in [('ocean',1),('meadow',-1),('meadow',True),('meadow',2**32)]:
            with self.assertRaises(ValueError): paint_biome(self.proposal,biome,seed)

class AgentBiomeTests(unittest.TestCase):
    def test_agent_creates_shared_biome(self):
        import json
        import test_actor_runtime as fixture
        from world import actor_runtime as runtime
        case=fixture.ActorRuntimeTests(); case.setUp(); self.addCleanup(case.doCleanups)
        server=case.s
        server.archive_generated_areas=True; server.persist_generated_cave=True
        blueprint=dict(rooms=[[3,3,20,18],[75,80,25,20]],links=[[0,1]],entrance_room=0,exit_room=1,style='rooms',seed=357,corridor_width=3)
        args=dict(label='Dunes',layout='connected_shapes',blueprint=json.dumps(blueprint,separators=(',',':')),biome='dunes',seed=42)
        case.apply(dict(id='biome',purpose='Create a place.',steps=[dict(id='create',tool='world.create_biome_landscape',args=args,after=[])]))
        self.assertEqual(runtime.tick(server,now=10)['status'],'succeeded')
        self.assertEqual(server.shared_cave.version,17)
        self.assertIn(ord('s'),server.shared_cave.palette)
