import copy,json,sqlite3,unittest
import test_region_characters as fixture
from world import floorplans as fp,actor_runtime
class Plans(unittest.TestCase):
 def setUp(self):
  self.f=fixture.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.design=dict(title='A furnished room',layout='SecretBase_RedCave1',placements=[[1,3,4],[10,5,4]])
  self.args=dict(id='room',design=json.dumps(self.design))
 def test_real_plan_catalog_wire_and_restart_without_player_data(self):
  c=copy.deepcopy(self.f.character);c['version']=2;c['plan']=dict(id='design',purpose='Suggest a room, not grant furniture.',steps=[dict(id='publish',tool='world.publish_floorplan',args=self.args,after=[])])
  self.f.commit(dict(state={'world_characters':{'harbor_guide':c}},tiles=[],objects=[self.f.obj]));self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  peer=dict(id='Buyer');ch=dict(id='Buyer',presence=peer,out=bytearray(),sock=object());self.s.peers['Buyer']=peer;self.s.link_channels['Buyer']=ch;self.s.connections[ch['sock']]=ch
  before=self.s.db.total_changes;self.s._link_line(ch,b'FP GET 1 room');self.assertEqual(ch['out'],b'FP PLAN 1 SecretBase_RedCave1 0103040a0504\n');self.assertEqual(self.s.db.total_changes,before)
  self.assertEqual(fp.handle(self.s,ch,b'FP COMPLETE 1 room'),'FP FAIL 0\n')
  self.assertIn('/floorplan room',' '.join(fp.command(self.s,peer,[])))
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:self.assertEqual(fp.catalog(self.s)['plans'][0]['placements'],self.design['placements'])
  finally:self.s.db=old;db.close()
  history=self.s.memory.history()['events'];self.assertTrue(any(e.get('event')=='floorplan_published' for e in history));self.assertFalse(any('Buyer' in json.dumps(e) for e in history))
 def test_bounds_immutable_identity_and_close(self):
  for p in [[[1,-1,0]],[[1,16,0]],[[3,10,0]],[[1,3,4],[1,3,4]],[[121,1,1]],[[True,1,1]],[]]:
   with self.assertRaises(ValueError):fp.configure(self.s,'harbor_guide',{},dict(self.args,design=json.dumps(dict(self.design,placements=p))))
  with self.s.db:fp.configure(self.s,'harbor_guide',{},self.args)
  with self.assertRaises(ValueError):fp.configure(self.s,'other',{},self.args)
  with self.assertRaises(ValueError):fp.configure(self.s,'harbor_guide',{},dict(self.args,design=json.dumps(dict(self.design,title='Changed'))))
  with self.s.db:fp.configure(self.s,'harbor_guide',{},dict(id='room',design=''))
  self.assertFalse(fp.catalog(self.s)['plans'])
  with self.s.db:fp.configure(self.s,'harbor_guide',{},self.args)
  self.assertEqual(len(fp.catalog(self.s)['plans']),1)
 def test_auth_and_atomic_publication(self):
  self.assertEqual(fp.handle(self.s,dict(id='x',presence={}),b'FP GET 1 room'),'FP FAIL 0\n')
  fp.setup(self.s.db);self.s.db.execute("CREATE TRIGGER reject_floorplan BEFORE INSERT ON floorplans BEGIN SELECT RAISE(ABORT,'no'); END")
  with self.assertRaises(sqlite3.IntegrityError):
   with self.s.db:fp.configure(self.s,'harbor_guide',{},self.args)
  self.assertFalse(fp.catalog(self.s)['plans']);self.assertFalse(any(e.get('event')=='floorplan_published' for e in self.s.memory.history()['events']))
 def test_metadata_and_native_not_buildable_claim(self):
  self.assertEqual(len(fp.CATALOG['layouts']),24);self.assertEqual(len(fp.CATALOG['decorations']),120)
  self.assertEqual(fp.CATALOG['decorations']['3']['width'],3)
  # Overlapping different decorations may be valid (for example a doll on a desk).
  # Surface/collision legality remains the real native placement decision.
  with self.s.db:fp.configure(self.s,'harbor_guide',{},dict(self.args,design=json.dumps(dict(self.design,placements=[[1,3,4],[76,3,4]]))))
  self.assertIn('may reject',fp.catalog(self.s)['limits'])
