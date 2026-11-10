import unittest,json,time,sqlite3
import test_region_characters
from world import move_weather as mw,field_move_ui,actor_runtime
from world.build_catalog import catalog_maps
class Weather(unittest.TestCase):
 def setUp(self):
  self.f=test_region_characters.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.args=dict(map='Route102',selector=json.dumps({'types':['water']}),weather='rain',frames=600,pp=1)
 def peer(self):
  coords=next(k for k,v in catalog_maps().items() if v['name']=='Route102');p=dict(id='Alice',state=[*coords,5,5,0,0,1],state_time=time.monotonic());ch=dict(id='Alice',presence=p);self.s.peers['Alice']=p;self.s.link_channels['Alice']=ch;return p,ch
 def test_real_plan_and_durable_config_not_activation(self):
  c=dict(self.f.character,version=2,plan=dict(id='weather',purpose='Offer optional weather.',steps=[dict(id='set',tool='world.configure_move_weather',args=self.args,after=[])]))
  self.f.commit(dict(state={'world_characters':{'harbor_guide':c}},tiles=[],objects=[self.f.obj]));self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:self.assertEqual(mw.catalog(self.s)['profiles'][0]['weather'],'rain')
  finally:self.s.db=old;db.close()
  p,ch=self.peer();self.assertTrue(field_move_ui.handle(self.s,ch,b'FM WGET 1 55').endswith(' 55 3 600 1\n'))
  self.assertEqual(field_move_ui.handle(self.s,ch,b'FM WGET 2 52'),'FM WNONE 2\n')
  # There is deliberately no activation-report or shared-climate mutation route.
  self.assertEqual(field_move_ui.handle(self.s,ch,b'FM WEATHER 1 55'),'FM FAIL 1\n')
 def test_bounds_ownership_and_presence(self):
  with self.s.db:mw.configure(self.s,'harbor_guide',{},self.args)
  with self.assertRaises(ValueError):mw.configure(self.s,'other',{},self.args)
  for change in [dict(frames=599),dict(frames=3601),dict(pp=0),dict(weather='thunderstorm'),dict(map='Route130'),dict(selector='[99999]')]:
   with self.assertRaises(ValueError):mw.configure(self.s,'harbor_guide',{},dict(self.args,**change))
  p,ch=self.peer();p['state_time']=0;self.assertEqual(field_move_ui.handle(self.s,ch,b'FM WGET 1 55'),'FM FAIL 1\n')
  p['state_time']=time.monotonic();p['state'][6]=0;self.assertEqual(field_move_ui.handle(self.s,ch,b'FM WGET 1 55'),'FM FAIL 1\n')
  p['state'][6]=1;self.s.link_channels.clear();self.assertEqual(field_move_ui.handle(self.s,ch,b'FM WGET 1 55'),'FM FAIL 0\n')
