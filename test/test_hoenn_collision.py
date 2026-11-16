import copy,importlib.util,json,pathlib,shutil,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hoenn_collision',ROOT/'world/hoenn_collision.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Collision(unittest.TestCase):
 def setUp(self):
  self.c=json.loads((ROOT/'world/hoenn_collision_catalog.json').read_text());self.row=m.checked_map(self.c,'Route102')
  cells=m.static_cells(self.row,3)
  self.start,self.target=next((p,(p[0]+1,p[1])) for p in sorted(cells) if (p[0]+1,p[1]) in cells)
  self.sessions={'a','b'};self.views=[dict(session=s,map=self.row['map'],elevation=3,movement='walk',map_digest=self.row['digest'],epoch=8,revision=2,observed_at=10,complete=True,walkable=[list(p) for p in sorted(cells)],blocked=[]) for s in sorted(self.sessions)]
 def plan(self,views=None):return m.plan(self.c,'Route102',self.start,self.target,views=self.views if views is None else views,sessions=self.sessions,epoch=8,now=11)
 def test_seven_real_maps_and_raw_facts(self):
  self.assertEqual(set(self.c['maps']),set(m.MAPS))
  for name,row in self.c['maps'].items():
   m.checked_map(self.c,name)
   self.assertEqual(len(row['facts']),row['height'])
   for y,line in enumerate(row['candidates']):
    self.assertEqual(len(line),row['width'])
    for x,value in enumerate(line):
     if value=='0':continue
     self.assertEqual(row['facts'][y]['collision'][x],'0')
     self.assertEqual(value,row['facts'][y]['elevation'][x]);self.assertNotIn(value,'01f')
     self.assertNotIn([x,y],row['reserved']);self.assertTrue(0<x<row['width']-1 and 0<y<row['height']-1)
  self.assertIn('setmetatile',self.c['maps']['Route103']['dynamic_script_indicators'])
 def test_real_route_preview_is_not_execution(self):
  p=m.preview(self.c,'Route102',self.start,self.target)
  self.assertEqual(p['status'],'static_preview_not_executable');self.assertEqual(p['path'],[list(self.start),list(self.target)])
  with self.assertRaises(ValueError):m.revalidate_step(self.c,p,0,views=self.views,sessions=self.sessions,epoch=8,now=11)
 def test_private_save_views_intersect(self):
  self.assertEqual(self.plan()['status'],'planned_not_executed')
  self.views[1]['blocked']=[list(self.target)]
  with self.assertRaises(ValueError):self.plan()
  self.views[1]['blocked']=[];self.views[1]['walkable'].remove(list(self.target))
  with self.assertRaises(ValueError):self.plan()
 def test_no_missing_or_stale_observations(self):
  for changes in [dict(observed_at=8),dict(observed_at=12),dict(complete=False),dict(map_digest='wrong'),dict(epoch=7),dict(revision=True),dict(elevation=4),dict(movement='surf'),dict(map=[0,99])]:
   views=copy.deepcopy(self.views);views[0].update(changes)
   with self.subTest(changes=changes),self.assertRaises(ValueError):self.plan(views)
  for views in [[],self.views[:1],[self.views[0],self.views[0]]]:
   with self.assertRaises(ValueError):self.plan(views)
 def test_next_step_revision_and_epoch_binding(self):
  p=self.plan();self.assertEqual(m.revalidate_step(self.c,p,0,views=self.views,sessions=self.sessions,epoch=8,now=11),self.target)
  self.views[0]['revision']+=1
  with self.assertRaises(ValueError):m.revalidate_step(self.c,p,0,views=self.views,sessions=self.sessions,epoch=8,now=11)
  with self.assertRaises(ValueError):m.revalidate_step(self.c,p,0,views=self.views,sessions=self.sessions,epoch=9,now=11)
 def test_elevation_warps_and_bounds(self):
  for elevation in [0,1,15,True]:
   with self.assertRaises(ValueError):m.preview(self.c,'Route102',self.start,self.target,elevation=elevation)
  with self.assertRaises(ValueError):m.preview(self.c,'Route102',[0,0],self.target)
  for row in self.c['maps'].values():
   for x,y in row['triggers']:
    if 0<=x<row['width'] and 0<=y<row['height']:self.assertEqual(row['candidates'][y][x],'0')
  self.row['candidates'][self.start[1]]='0'*self.row['width']
  with self.assertRaises(ValueError):self.plan()
 def test_long_route_and_replanning_around_new_obstacle(self):
  cells=m.static_cells(self.row,3)
  # Choose a real connected route with at least three steps, then invalidate its
  # first destination in one observer's current collision image.
  for target in sorted(cells):
   try:p=m.plan(self.c,'Route102',self.start,target,views=self.views,sessions=self.sessions,epoch=8,now=11)
   except ValueError:continue
   if len(p['path'])>=4:break
  self.assertGreaterEqual(len(p['path']),4)
  self.views[0]['blocked']=[p['path'][1]]
  with self.assertRaises(ValueError):m.revalidate_step(self.c,p,0,views=self.views,sessions=self.sessions,epoch=8,now=11)
 def test_rebuild_exact_native_sources_and_corruption(self):
  root=ROOT/'inputs'
  if not root.exists():root=ROOT/'engines/expansion-native'
  if not (root/'data/layouts/Route102/map.bin').exists():self.skipTest('Exact native source checkout not available')
  manifest=json.loads((ROOT/'world/hoenn_collision_sources.json').read_text())
  self.assertEqual(m.build(root,manifest),self.c)
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d)
   for path in manifest['files']:
    dest=d/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/path,dest)
   bad=d/'data/layouts/Route102/map.bin';bad.write_bytes(bad.read_bytes()[:-1])
   with self.assertRaisesRegex(ValueError,'Source hash differs'):m.build(d,manifest)
if __name__=='__main__':unittest.main()
