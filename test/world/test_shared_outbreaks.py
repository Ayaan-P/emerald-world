import unittest,sqlite3,pathlib,importlib.util,tempfile,subprocess
from unittest.mock import patch
import test_region_characters
from world import shared_outbreaks as outbreaks,actor_runtime
from world.build_catalog import catalog_maps

class OutbreakTests(unittest.TestCase):
 def setUp(self):
  self.f=test_region_characters.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.args=dict(map='Route102',species='RALTS',level=12,chance=35,minutes=10)
 def peer(self,name='Alice',cap=True):
  token=self.s.create_identity(name)['token'];p=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.assertIn('WELCOME',self.f.send(p,f'HELLO 1 {name} {token} SOCIAL'+('OUTBREAK1' if cap else '')))
  group,num=next(k for k,m in catalog_maps().items() if m['name']=='Route102')
  self.f.state(p,group,num,1,1);return p
 def test_actual_plan_snapshot_native_and_no_saved_player_mutation(self):
  peer=self.peer();old=self.peer('Old',False)
  c=dict(self.f.character,version=2,plan=dict(id='population',purpose='Author public population.',steps=[dict(id='set',tool='world.configure_outbreak',args=self.args,after=[])]))
  self.f.commit(dict(state={'world_characters':{'harbor_guide':c}},tiles=[],objects=[self.f.obj]))
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  wire=next(x for x in self.s._snapshot(peer).splitlines() if x.startswith('WILD_OUTBREAK'))
  self.assertNotIn('WILD_OUTBREAK',self.s._snapshot(old))
  path=pathlib.Path('../native-shared-outbreaks/tests/test_outbreak.py').resolve()
  if not path.exists():self.skipTest('Matching native component source unavailable')
  spec=importlib.util.spec_from_file_location('outbreak_native',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as d:subprocess.run([str(module.build(d,wire))],check=True,capture_output=True)
  self.assertIn('RALTS',str(outbreaks.command(self.s,peer,[])))
 def test_expiry_restart_close_and_other_maps(self):
  p=self.peer()
  with patch('world.shared_outbreaks.time.time',return_value=1000),self.s.db:outbreaks.configure(self.s,'harbor_guide',{},self.args)
  with patch('world.shared_outbreaks.time.time',return_value=1200):self.assertIsNotNone(outbreaks.line(self.s,p))
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   outbreaks.setup(db)
   with patch('world.shared_outbreaks.time.time',return_value=1601):self.assertIsNone(outbreaks.line(self.s,p))
  finally:self.s.db=old;db.close()
  with self.s.db:outbreaks.configure(self.s,'harbor_guide',{},self.args)
  p['state'][:2]=[0,0];self.assertIsNone(outbreaks.line(self.s,p))
  with self.s.db:outbreaks.configure(self.s,'harbor_guide',{},dict(self.args,minutes=0))
  self.assertEqual(outbreaks.catalog(self.s)['active'],[])
 def test_collision_disabled_species_and_non_native_habitats(self):
  with self.s.db:outbreaks.configure(self.s,'harbor_guide',{},self.args)
  with self.assertRaises(ValueError):outbreaks.configure(self.s,'other',{},self.args)
  for changes in (dict(map='Route130'),dict(map='GeneratedWorld_Cave'),dict(species='UNKNOWN'),dict(chance=100),dict(minutes=61)):
   with self.assertRaises(ValueError):outbreaks.configure(self.s,'harbor_guide',{},dict(self.args,**changes))
