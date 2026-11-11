import unittest,sqlite3,pathlib,tempfile,subprocess,importlib.util
from world import contest_guests as guest,actor_runtime
import test_region_characters

class ContestGuests(unittest.TestCase):
 def setUp(self):
  self.f=test_region_characters.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.obj=dict(self.f.obj,group=13,num=4,x=5,y=5);self.obj.pop('region_revision')
  self.c=dict(self.f.character,version=2,name='Guide',team=[dict(species=278,level=18,individual='partner')])
  self.commit()
 def commit(self):self.f.commit(dict(state={'world_characters':{'harbor_guide':self.c}},tiles=[],objects=[self.obj]))
 def peer(self,name='Alice',cap=True):
  token=self.s.create_identity(name)['token'];p=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.assertIn('WELCOME',self.f.send(p,f'HELLO 1 {name} {token} SOCIAL'+('CONTEST1' if cap else '')))
  self.f.state(p,13,4,4,5);return p
 def test_actual_plan_to_native_guest_preserves_individual(self):
  p=self.peer();old=self.peer('Old',False)
  self.c=dict(self.c,version=3,plan=dict(id='contest',purpose='Offer owned partner.',steps=[dict(id='entry',tool='world.enter_contest',args=dict(category='cool',individual='partner'),after=[])]));self.commit()
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  wire=next(l for l in self.s._snapshot(p).splitlines() if l.startswith('CONTEST_GUEST'))
  self.assertNotIn('CONTEST_GUEST',self.s._snapshot(old));self.assertEqual(len(wire.split()),11)
  from world.character_companions import roster
  identity=roster(self.s,'harbor_guide')[0]
  self.assertEqual(list(map(int,wire.split()[6:8])),[identity['personality'],identity['owner']])
  path=pathlib.Path('../native-contest-guests/tests/test_contest_guest.py').resolve()
  if not path.exists():self.skipTest('Matching native C fixture unavailable')
  spec=importlib.util.spec_from_file_location('contest_native',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as d:subprocess.run([str(module.build(d,wire))],check=True,capture_output=True)
 def test_restart_withdraw_and_actual_location(self):
  p=self.peer()
  with self.s.db:guest.configure(self.s,'harbor_guide',{},dict(category='cute',individual='partner'))
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:guest.setup(db);self.assertEqual(guest.available(self.s)[0]['individual'],'partner')
  finally:self.s.db=old;db.close()
  self.obj=dict(self.obj,group=0,num=9,x=8,y=8);self.c=dict(self.c,version=3);self.commit()
  self.assertEqual(guest.available(self.s),[]);self.assertEqual(guest.lines(self.s,p),[])
  with self.s.db:guest.configure(self.s,'harbor_guide',{},dict(category='cute',individual=''))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM contest_guests').fetchone()[0],0)
 def test_ownership_and_nonexistent_mon_rejected(self):
  with self.assertRaises(ValueError):guest.configure(self.s,'harbor_guide',{},dict(category='cool',individual='invented'))
  with self.s.db:guest.configure(self.s,'harbor_guide',{},dict(category='cool',individual='partner'))
  with self.assertRaises(ValueError):guest.configure(self.s,'other',{},dict(category='cool',individual=''))
  self.c=dict(self.c,version=3,name='TooLongName');self.commit()
  self.assertEqual(guest.available(self.s),[])
