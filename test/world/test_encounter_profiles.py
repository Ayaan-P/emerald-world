import unittest,json,sqlite3
import test_region_characters
from world import encounter_profiles as ep,actor_runtime,field_move_ui
from world.build_catalog import catalog_maps

class Profiles(unittest.TestCase):
 def setUp(self):
  self.f=test_region_characters.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.args=dict(map='Route102',selector=json.dumps({'types':['fire']}),accept=40,prefer_move_type=1,steps=80,pp=2)
 def test_actual_plan_publication_discovery_and_offer(self):
  c=dict(self.f.character,version=2,plan=dict(id='encounters',purpose='Offer voluntary move influence.',steps=[dict(id='set',tool='world.configure_encounter_profile',args=self.args,after=[])]))
  self.f.commit(dict(state={'world_characters':{'harbor_guide':c}},tiles=[],objects=[self.f.obj]))
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  self.assertEqual(ep.catalog(self.s)['profiles'][0]['accept'],40)
  coords=next(k for k,v in catalog_maps().items() if v['name']=='Route102');c={'state':list(coords)+[1,1]}
  self.assertIn('FM PROFILE 7',ep.offer(self.s,c,7,52))
  self.assertEqual(ep.offer(self.s,c,7,45),'FM PNONE 7\n')
  self.assertEqual(ep.offer(self.s,{'state':[0,0,1,1]},7,52),'FM PNONE 7\n')
 def test_restart_owner_and_bounds(self):
  with self.s.db:ep.configure(self.s,'harbor_guide',{},self.args)
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:self.assertEqual(ep.catalog(self.s)['profiles'][0]['steps'],80)
  finally:self.s.db=old;db.close()
  with self.assertRaises(ValueError):ep.configure(self.s,'other',{},self.args)
  for changes in [dict(accept=100),dict(accept=0),dict(pp=0),dict(steps=201),dict(prefer_move_type=True),dict(map='Route130'),dict(selector='[99999]')]:
   with self.assertRaises(ValueError):ep.configure(self.s,'harbor_guide',{},dict(self.args,**changes))
 def test_negotiation_requires_current_authenticated_channel(self):
  with self.s.db:ep.configure(self.s,'harbor_guide',{},self.args)
  coords=next(k for k,v in catalog_maps().items() if v['name']=='Route102');p={'id':'Alice','state':list(coords)+[1,1]};ch={'id':'Alice','presence':p}
  self.s.peers['Alice']=p;self.s.link_channels['Alice']=ch
  self.assertTrue(field_move_ui.handle(self.s,ch,b'FM PGET 3 52').startswith('FM PROFILE 3 '))
  self.assertEqual(field_move_ui.handle(self.s,dict(ch),b'FM PGET 3 52'),'FM FAIL 0\n')
