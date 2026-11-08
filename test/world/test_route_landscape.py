"""Original terrain routing, with production map validation and persistence."""
import copy
import tempfile
import unittest
from pathlib import Path
from world.route_landscape import compile_plan
from world.shared_cave import SharedCave
from test_shared_generated_cave import MemoryAuthority


def plan():
    return dict(seed=18,loops=2,landmarks=[dict(id=n,x=x,y=y,radius=6) for n,x,y in
        [('camp',15,20),('orchard',30,95),('ruins',95,35),('lookout',105,105)]],
        reservations=[[50,12,14,75]])

class TerrainRouting(unittest.TestCase):
    def test_real_paths_detour_around_reserved_terrain_and_add_alternates(self):
        blob,report=compile_plan(plan())
        self.assertEqual(SharedCave(blob).version,16)
        self.assertEqual((blob,report),compile_plan(plan()))
        cells=blob[8:];protected={(x,y) for x in range(50,64) for y in range(12,87)}
        self.assertTrue(all(cells[y*127+x]==ord('#') for x,y in protected))
        for path in report['routes']:
            points=[tuple(p) for p in path['path']]
            self.assertFalse(set(points)&protected)
            self.assertTrue(all(cells[y*127+x]==ord('.') for x,y in points))
            self.assertTrue(all(abs(a[0]-b[0])+abs(a[1]-b[1])==1 for a,b in zip(points,points[1:])))
        alternate=[r for r in report['routes'] if r['kind']=='alternate']
        self.assertEqual(len(alternate),2)
        self.assertTrue(all(r['new_tiles']>4 for r in alternate))
        self.assertGreaterEqual(report['entry_to_exit_steps'],248)

    def test_custom_layouts_and_seed_change_real_template_bytes(self):
        revisions=set()
        for seed in range(8):
            p=plan();p['seed']=seed
            blob,report=compile_plan(p);revisions.add(report['revision'])
            self.assertEqual(len(blob),16137)
        self.assertGreater(len(revisions),4)
        p=plan();p['landmarks'][1]['x']=23
        self.assertNotEqual(compile_plan(p)[0],compile_plan(plan())[0])

    def test_unsatisfiable_plans_fail_instead_of_carving_reservations(self):
        p=plan();p['reservations']=[[50,1,2,125]]
        with self.assertRaisesRegex(ValueError,'disconnect'):compile_plan(p)
        p=plan();p['reservations']=[[1,1,2,2]]
        with self.assertRaisesRegex(ValueError,'overlaps'):compile_plan(p)
        p=plan();p['landmarks'][1]=copy.deepcopy(p['landmarks'][0])
        with self.assertRaises(ValueError):compile_plan(p)
        p=plan();p['loops']=5
        with self.assertRaises(ValueError):compile_plan(p)

    def test_existing_authority_persists_generated_map_and_place_identity(self):
        blob,report=compile_plan(plan())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            server=MemoryAuthority(root/'socket',root/'world',persist_generated_cave=True,archive_generated_areas=True)
            try:
                revision=server._replace_cave(blob,label='Orchard Divide')
                place=server.memory.place(revision)
                self.assertEqual(revision,report['revision'])
            finally:server.close()
            server=MemoryAuthority(root/'socket',root/'world',persist_generated_cave=True,archive_generated_areas=True)
            try:
                self.assertEqual(server.shared_cave.identity,revision)
                self.assertEqual(server.memory.place(revision),place)
                self.assertEqual(server.shared_cave.frames(),SharedCave(blob).frames())
            finally:server.close()

if __name__=='__main__':unittest.main()
