import unittest,json,time,sqlite3
import test_region_characters
from world import move_sensing as ms,field_move_ui,actor_runtime,spatial_signals
from world.build_catalog import catalog_maps
class Sensing(unittest.TestCase):
 def setUp(self):
  self.f=test_region_characters.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.args=dict(map='Route102',selector=json.dumps({'types':['psychic']}),radius=3,pp=1)
 def peer(self):
  coords=next(k for k,v in catalog_maps().items() if v['name']=='Route102');p=dict(id='Alice',state=[*coords,5,5,0,0,1],state_time=time.monotonic());c=dict(id='Alice',presence=p);self.s.peers['Alice']=p;self.s.link_channels['Alice']=c;return p,c
 def test_agent_authoring_restart_and_separate_share(self):
  c=dict(self.f.character,version=2,plan=dict(id='sensing',purpose='Offer optional sensing.',steps=[dict(id='set',tool='world.configure_move_sensing',args=self.args,after=[])]))
  self.f.commit(dict(state={'world_characters':{'harbor_guide':c}},tiles=[],objects=[self.f.obj]));self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:self.assertEqual(ms.catalog(self.s)['profiles'][0]['radius'],3)
  finally:self.s.db=old;db.close()
  p,ch=self.peer();spatial_signals.setup(self.s.db)
  self.assertTrue(field_move_ui.handle(self.s,ch,b'FM SGET 1 93').startswith('FM SENSOR 1 '))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM spatial_signals').fetchone()[0],0)
  self.assertEqual(field_move_ui.handle(self.s,ch,b'FM CLUE 1 6 5 93'),'FM SHARED 1\n')
  self.assertEqual(self.s.db.execute('SELECT source FROM spatial_signals').fetchone()[0],'player:Alice (reported clue)')
  self.assertEqual(field_move_ui.handle(self.s,ch,b'FM CLUE 1 6 5 93'),'FM FAIL 1\n')
 def test_bounds_ownership_stale_presence_and_claims(self):
  with self.s.db:ms.configure(self.s,'harbor_guide',{},self.args)
  with self.assertRaises(ValueError):ms.configure(self.s,'other',{},self.args)
  for change in [dict(radius=6),dict(pp=0),dict(map='Route130'),dict(selector='[99999]')]:
   with self.assertRaises(ValueError):ms.configure(self.s,'harbor_guide',{},dict(self.args,**change))
  p,ch=self.peer();self.assertEqual(field_move_ui.handle(self.s,ch,b'FM SGET 1 52'),'FM SNONE 1\n')
  field_move_ui.handle(self.s,ch,b'FM SGET 2 93');self.assertEqual(field_move_ui.handle(self.s,ch,b'FM CLUE 2 20 5 93'),'FM FAIL 2\n')
  field_move_ui.handle(self.s,ch,b'FM SGET 3 93');p['state'][2]+=1;self.assertEqual(field_move_ui.handle(self.s,ch,b'FM CLUE 3 6 5 93'),'FM FAIL 3\n')
  p['state_time']=0;self.assertEqual(field_move_ui.handle(self.s,ch,b'FM SGET 4 93'),'FM FAIL 4\n')
