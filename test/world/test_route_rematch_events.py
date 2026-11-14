import unittest,time,json,sqlite3
import test_contest_guests as fixture
from world import route_rematch_events as r,actor_runtime
from world.build_catalog import catalog_maps
class Rematches(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ContestGuests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def test_actual_actor_plan_and_local_delivery(self):
  self.f.c=dict(self.f.c,version=3,plan=dict(id='event',purpose='Organize optional route practice.',steps=[dict(id='open',tool='world.organize_rematches',args=dict(route='Route110',minutes=30),after=[])]));self.f.commit()
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  self.assertIn('world.organize_rematches',actor_runtime.inspect_runtime(self.s)['capabilities'])
  pos=next(k for k,v in catalog_maps().items() if v['name']=='Route110');conn=dict(presence=dict(state=[*pos,1,1],state_time=time.monotonic()))
  self.assertTrue(r.wire(self.s,conn,b'J GET 1').startswith('J MAP '));conn['presence']['state_time']=0;self.assertEqual(r.wire(self.s,conn,b'J GET 1'),'J NONE\n')
  self.assertIn('Route110',str(r.command(self.s,{},[])))
 def test_ownership_expiry_and_restart(self):
  before=json.dumps(self.s.module_state,sort_keys=True)
  with self.s.db:r.configure(self.s,'harbor_guide',{},dict(route='Route104',minutes=10))
  with self.assertRaises(ValueError):r.configure(self.s,'other',{},dict(route='Route104',minutes=10))
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   self.assertEqual(r.catalog(self.s)['active'][0]['route'],'Route104')
   with db:r.configure(self.s,'harbor_guide',{},dict(route='Route104',minutes=0))
   self.assertEqual(r.catalog(self.s)['active'],[])
  finally:self.s.db=old;db.close()
  self.assertEqual(before,json.dumps(self.s.module_state,sort_keys=True))
 def test_not_special_or_invalid(self):
  for args in [dict(route='VictoryRoad_B2F',minutes=10),dict(route='Route110',minutes=True),dict(route='Route110',minutes=1441)]:
   with self.assertRaises(ValueError):r.configure(self.s,'harbor_guide',{},args)
