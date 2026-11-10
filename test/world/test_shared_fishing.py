import json,unittest,sqlite3,pathlib,importlib.util,tempfile,subprocess,os
from unittest.mock import patch
import test_region_characters as fixture
from world import shared_fishing as fishing,actor_runtime
from world.build_catalog import catalog_maps

class FishingTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.rods={'old':[['MAGIKARP',5,10],['GOLDEEN',5,10]],'good':[['MAGIKARP',10,20],['GOLDEEN',10,20],['CORPHISH',10,20]],'super':[['CORPHISH',20,30]]*5}
  self.args=dict(map='Route102',rods=json.dumps(self.rods),minutes=60)
 def peer(self,name='Alice',cap=True):
  token=self.s.create_identity(name)['token'];p=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.assertIn('WELCOME',self.f.send(p,f'HELLO 1 {name} {token} SOCIAL'+('CHAR1CHARPK1OUTBREAK1CONTEST1RENTALS1WORLDTV1CHARFORM1FISHING1' if cap else '')))
  group,num=next(k for k,m in catalog_maps().items() if m['name']=='Route102')
  self.f.state(p,group,num,1,1);return p
 def test_agent_configures_real_snapshot_and_native_fishing(self):
  p=self.peer();old=self.peer('Old',False)
  c=dict(self.f.character,version=2,plan=dict(id='fishery',purpose='Author local rod populations.',steps=[dict(id='set',tool='world.configure_fishing',args=self.args,after=[])]))
  self.f.commit(dict(state={'world_characters':{'harbor_guide':c}},tiles=[],objects=[self.f.obj]))
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  wire=[x for x in self.s._snapshot(p).splitlines() if x.startswith(('WILD_FISHERY','FISH_SLOT'))]
  self.assertEqual(len(wire),11);self.assertNotIn('WILD_FISHERY',self.s._snapshot(old))
  self.assertIn('MAGIKARP',str(fishing.command(self.s,p,['Route102'])))
  self.assertTrue(self.s.guild_chat.handle(p,'/guild fishing Route102'))
  source=pathlib.Path(os.environ.get('EW_FISHING_NATIVE_SOURCE','../native-shared-fishing'))/'tests/test_fishing.py'
  if not source.exists():self.skipTest('Matched native fishing fixture unavailable')
  spec=importlib.util.spec_from_file_location('native_fishing',source.resolve());mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  with tempfile.TemporaryDirectory() as d:subprocess.run([str(mod.build(d,wire))],check=True,capture_output=True)
 def test_restart_expiry_ownership_and_map_scope(self):
  p=self.peer()
  with patch('world.shared_fishing.time.time',return_value=1000),self.s.db:fishing.configure(self.s,'harbor_guide',{},self.args)
  with patch('world.shared_fishing.time.time',return_value=1100):
   self.assertEqual(len(fishing.lines(self.s,p)),11)
   with self.assertRaises(ValueError):fishing.configure(self.s,'other',{},self.args)
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   fishing.setup(db)
   with patch('world.shared_fishing.time.time',return_value=1200):self.assertEqual(len(fishing.lines(self.s,p)),11)
   with patch('world.shared_fishing.time.time',return_value=4601):self.assertEqual(fishing.lines(self.s,p),[])
  finally:self.s.db=old;db.close()
  with self.s.db:fishing.configure(self.s,'harbor_guide',{},self.args)
  p['state'][:2]=[0,0];self.assertEqual(fishing.lines(self.s,p),[])
  with self.s.db:fishing.configure(self.s,'harbor_guide',{},dict(self.args,minutes=0))
  self.assertEqual(fishing.catalog(self.s)['active'],[])
 def test_invalid_tables_never_commit_history(self):
  for changes in (dict(map='GeneratedWorld_Cave'),dict(map='Route101'),dict(map='Route4'),dict(minutes=1441),dict(rods='{}'),dict(rods=json.dumps(dict(self.rods,old=[['UNKNOWN',5,10]]*2))),dict(rods=json.dumps(dict(self.rods,old=[['MAGIKARP',10,5]]*2)))):
   with self.assertRaises(ValueError),self.s.db:fishing.configure(self.s,'harbor_guide',{},dict(self.args,**changes))
  self.assertEqual(fishing.catalog(self.s)['active'],[])
