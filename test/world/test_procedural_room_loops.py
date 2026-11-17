import json, unittest
from world.procedural_regions import generate
from world.cave_blueprint import proposal_from_blueprint
from world.shared_cave import SharedCave

def spec(**changes):
    data=dict(places=2,rooms=3,loops=0,branching=1,style='maze',seed=23,corridor_width=1)
    data.update(changes)
    return json.dumps(data,separators=(',',':'))

class RoomLoopTests(unittest.TestCase):
    def test_old_inputs_match_explicit_zero(self):
        self.assertEqual(generate('Cove',spec()),generate('Cove',spec(room_loops=0)))
    def test_cycles_are_deterministic_and_compile_to_connected_caves(self):
        for style in ('rooms','rounded','organic','maze'):
            for seed in range(12):
                raw=spec(style=style,seed=seed,room_loops=1)
                doc=generate('Cove',raw)
                self.assertEqual(doc,generate('Cove',raw))
                for place in doc['places']:
                    b=place['blueprint']; self.assertEqual(len(b['links']),len(b['rooms']))
                    proposal=proposal_from_blueprint(b)
                    cave=SharedCave(b'EWGMAP01'+''.join(proposal['rows']).encode())
                    self.assertTrue(cave.walkable(1,1)); self.assertTrue(cave.walkable(29,29))
    def test_no_impossible_or_malformed_loop_request(self):
        for options in ({'rooms':2,'room_loops':1},{'room_loops':True},{'room_loops':2},{'room_loops':-1}):
            with self.subTest(options=options),self.assertRaises(ValueError): generate('Cove',spec(**options))
    def test_room_and_region_topology_are_independent(self):
        a=generate('Cove',spec(room_loops=0));b=generate('Cove',spec(room_loops=1))
        self.assertEqual(a['links'],b['links'])
        self.assertEqual(len(a['places'][0]['blueprint']['links'])+1,len(b['places'][0]['blueprint']['links']))
if __name__=='__main__': unittest.main()
