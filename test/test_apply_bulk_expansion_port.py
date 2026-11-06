import importlib.util,json,tempfile,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('port',root/'scripts/apply_bulk_expansion_port.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class Maps(unittest.TestCase):
 def test_groups_and_layouts_keep_world_identity(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'data/maps').mkdir(parents=True);(p/'data/layouts').mkdir(parents=True)
   gp=p/'data/maps/map_groups.json';lp=p/'data/layouts/layouts.json';gp.write_text(json.dumps({'group_order':['g'+str(i) for i in range(75)]}));lp.write_text(json.dumps({'layouts':[{'id':'L_EXISTING'}]}))
   mod.merge_maps(p);g=json.loads(gp.read_text());l=json.loads(lp.read_text())
   self.assertEqual(g['group_order'][34],'gMapGroup_GeneratedWorld');self.assertEqual(g['group_order'][35],'g34');self.assertEqual(len(l['layouts']),3);self.assertEqual(l['layouts'][-1]['layout_version'],'emerald')
   with self.assertRaises(ValueError):mod.merge_maps(p)
