import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from world import procedural_map as pm


def plan(seed=1, width=21, height=15, rooms=4, room_size=5):
    return {'schema':1,'seed':seed,'width':width,'height':height,'rooms':rooms,
            'room_size':room_size,'biome':'forest','points':['landmark','treasure','encounter']}

class GeneratedMapTests(unittest.TestCase):
    def test_many_seeds_produce_connected_nonoverlapping_maps(self):
        hashes=set()
        for seed in range(100):
            with self.subTest(seed=seed):
                result=pm.generate(plan(seed))
                self.assertTrue(pm.validate_generated(result))
                self.assertEqual(result,pm.generate(plan(seed)))
                hashes.add(result['sha256'])
                coords=[tuple(result['spawn']),tuple(result['exit'])]+[(x['x'],x['y']) for x in result['points']]
                self.assertEqual(len(coords),len(set(coords)))
        self.assertGreater(len(hashes),95)

    def test_max_dimensions_and_64_bit_seed(self):
        p=plan((1<<64)-1,63,63,12,7)
        r=pm.generate(p);self.assertTrue(pm.validate_generated(r))
        self.assertEqual((len(r['rows']),len(r['rows'][0])),(63,63))

    def test_strict_plan_rejects_unknowns_invalid_bounds_and_bool(self):
        cases=[{'schema':2},{'seed':True},{'seed':-1},{'seed':1<<64},
               {'width':8},{'width':10},{'height':65},{'rooms':13},{'room_size':4},
               {'biome':'ocean'},{'points':['script:evil']},{'points':['treasure']*9},
               {'unexpected':'data'}]
        for change in cases:
            with self.subTest(change=change),self.assertRaises(pm.PlanError):pm.generate({**plan(),**change})

    def test_tampering_rejected_even_when_hash_is_recomputed(self):
        original=pm.generate(plan())
        altered=copy.deepcopy(original);altered['rows'][0]='.'+altered['rows'][0][1:]
        altered['sha256']=pm._digest({k:v for k,v in altered.items() if k!='sha256'})
        with self.assertRaises(pm.PlanError):pm.validate_generated(altered)
        altered=copy.deepcopy(original);altered['points'][0]['x']=altered['spawn'][0];altered['points'][0]['y']=altered['spawn'][1]
        altered['sha256']=pm._digest({k:v for k,v in altered.items() if k!='sha256'})
        with self.assertRaises(pm.PlanError):pm.validate_generated(altered)
        altered=copy.deepcopy(original);altered['sha256']='0'*64
        with self.assertRaises(pm.PlanError):pm.validate_generated(altered)

    def test_alternate_connected_map_cannot_impersonate_seed(self):
        first=pm.generate(plan(1));second=pm.generate(plan(2));second['plan']['seed']=1
        second['sha256']=pm._digest({k:v for k,v in second.items() if k!='sha256'})
        with self.assertRaisesRegex(pm.PlanError,'does not match deterministic'):pm.validate_generated(second)
        self.assertNotEqual(first['rows'],second['rows'])

    def test_no_input_or_output_aliasing(self):
        p=plan();r=pm.generate(p);p['points'].append('treasure')
        self.assertEqual(len(r['plan']['points']),3)
        old=copy.deepcopy(r);pm.render_preview(r);self.assertEqual(r,old)

    def test_cross_process_canonical_output_and_preview(self):
        p=plan(42);r=pm.generate(p)
        self.assertEqual(r['sha256'],'8e3554a7461169cd139c8261fe8a6b35bd14db696f7499e7d03e238b8265af0c')
        code='import json,sys;from world.procedural_map import generate;print(json.dumps(generate(json.loads(sys.argv[1])),sort_keys=True))'
        other=json.loads(subprocess.check_output([sys.executable,'-c',code,json.dumps(p)],cwd=ROOT,text=True))
        self.assertEqual(r,other)
        preview=pm.render_preview(r);self.assertEqual(preview.count('S'),1);self.assertEqual(preview.count('X'),1)
        self.assertEqual(preview.count('T'),1)

    def test_untrusted_ai_grid_is_validated_as_inert_data(self):
        r=pm.generate(plan())
        proposal={'schema':1,'biome':'cave','rows':r['rows'],
                  'spawn':r['spawn'],'exit':r['exit'],'points':r['points']}
        clean=pm.accept_proposal(proposal)
        self.assertEqual(len(clean['sha256']),64)
        self.assertEqual(clean,pm.accept_proposal(proposal))
        proposal['rows'][0]='.'*len(proposal['rows'][0])
        self.assertTrue(clean['rows'][0].startswith('#'))
        with self.assertRaises(pm.PlanError):pm.accept_proposal(proposal)

    def test_rejects_unreachable_or_code_bearing_proposals(self):
        rows=['#########','#..######','#########','#########','####..###','#########','#########','#########','#########']
        proposal={'schema':1,'biome':'ruins','rows':rows,'spawn':[1,1],'exit':[5,4],'points':[]}
        with self.assertRaisesRegex(pm.PlanError,'unreachable'):pm.accept_proposal(proposal)
        valid=pm.generate(plan())
        clean={'schema':1,'biome':'forest','rows':valid['rows'],'spawn':valid['spawn'],'exit':valid['exit'],'points':valid['points']}
        for change in ({'script':'execute()'}, {'biome':'../../etc'}, {'points':[{'kind':'eval','x':1,'y':1}]}, {'schema':True}, {'rows':['x'*200]*200}):
            with self.subTest(change=change),self.assertRaises(pm.PlanError):pm.accept_proposal({**clean,**change})

    def test_bad_types_and_positions_fail_closed(self):
        r=pm.generate(plan());r['spawn']=[True,1]
        with self.assertRaises(pm.PlanError):pm.validate_generated(r)
        r=pm.generate(plan());r['points'][0]['x']=0
        with self.assertRaises(pm.PlanError):pm.validate_generated(r)
        with self.assertRaises(pm.PlanError):pm.validate_generated([])

if __name__=='__main__':unittest.main()
