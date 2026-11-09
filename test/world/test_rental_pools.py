import importlib.util,json,pathlib,random,sqlite3,subprocess,tempfile,unittest
import test_region_characters
from world import rental_pools as pools,actor_runtime
VALID=[17,8,32,15,63,57]
class RentalPools(unittest.TestCase):
 def setUp(self):
  self.f=test_region_characters.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
 def peer(self,name,cap=True):
  token=self.s.create_identity(name)['token'];p=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.assertIn('WELCOME',self.f.send(p,f'HELLO 1 {name} {token} SOCIAL'+('RENTALS1' if cap else '')))
  return p
 def test_real_plan_configures_optional_native_pool(self):
  p=self.peer('Alice');old=self.peer('Old',False)
  c=dict(self.f.character,version=2,plan=dict(id='rentals',purpose='Offer an alternative native rental selection.',steps=[dict(id='pool',tool='world.rentals',args=dict(operation='configure',value=json.dumps(VALID)),after=[])]))
  self.f.commit(dict(state={'world_characters':{'harbor_guide':c}},tiles=[],objects=[self.f.obj]))
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  line=next(l for l in self.s._snapshot(p).splitlines() if l.startswith('RENTAL_POOL'))
  self.assertEqual(list(map(int,line.split()[2:])),VALID);self.assertNotIn('RENTAL_POOL',self.s._snapshot(old))
  self.assertEqual(pools.tool(self.s,'harbor_guide',{},dict(operation='inspect',value=0))['active']['sets'],VALID)
 def test_ownership_restart_close(self):
  with self.s.db:pools.configure(self.s,'harbor_guide',{},dict(sets=json.dumps(VALID)))
  with self.assertRaises(ValueError):pools.configure(self.s,'another',{},dict(sets='[]'))
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   pools.setup(db);self.assertEqual(pools.catalog(self.s)['active']['sets'],VALID)
   with db:pools.configure(self.s,'harbor_guide',{},dict(sets='[]'))
   self.assertIsNone(pools.catalog(self.s)['active'])
  finally:self.s.db=old;db.close()
 def test_invalid_sets_do_not_publish(self):
  before=self.s.db.execute('SELECT count(*) FROM events').fetchone()[0]
  for ids in ([70,8,32,15,63,57],[17]*6,[True,8,32,15,63,57],{},[1,2]):
   with self.assertRaises(ValueError):pools.configure(self.s,'harbor_guide',{},dict(sets=json.dumps(ids)))
  self.assertEqual(before,self.s.db.execute('SELECT count(*) FROM events').fetchone()[0])
 def test_actual_native_catalog_and_validator_agree_on_varied_pools(self):
  path=pathlib.Path('../native-shared-rental-pools/tests/test_world_rentals.py').resolve()
  if not path.exists():self.skipTest('paired native source unavailable')
  spec=importlib.util.spec_from_file_location('native_rentals',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  mons,trainers=module.source_catalog();self.assertEqual(mons,[{k:m[k] for k in ('id','species','item')} for m in pools.CATALOG['sets']]);self.assertEqual(trainers,[t['sets'] for t in pools.CATALOG['trainers']])
  with tempfile.TemporaryDirectory() as d:
   exe=str(module.build(d));subprocess.run([exe],check=True,capture_output=True)
   rng=random.Random(18)
   for ids in [VALID]+[rng.sample(range(70),6) for _ in range(100)]:
    try:pools.validate(ids);expected=True
    except ValueError:expected=False
    self.assertEqual(subprocess.run([exe,*map(str,ids)],capture_output=True).returncode==0,expected,ids)
