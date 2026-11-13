import sqlite3,types,tempfile,unittest
from world import pyramid_courses as p
class Courses(unittest.TestCase):
 def server(self,path=':memory:'):return types.SimpleNamespace(db=sqlite3.connect(path),link_protocol=types.SimpleNamespace(busy=lambda _:False))
 def test_immutable_course_restart_forecast_and_close(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.server(d+'/db');args=dict(id='exploration',seed=123)
   with s.db:r=p.publish(s,'guide',{},args)
   self.assertEqual(len(r['floors']),7);self.assertTrue(all(f['entrance_square']!=f['exit_square'] for f in r['floors']))
   with self.assertRaises(ValueError):p.publish(s,'other',{},args)
   with self.assertRaises(ValueError):p.publish(s,'guide',{},dict(id='exploration',seed=124))
   s.db.close();s=self.server(d+'/db');conn=dict(id='a',presence=dict(campaign_run='private'))
   raw=f"E GET 1 exploration {r['revision']}".encode();self.assertEqual(p.handle(s,conn,raw),'E COURSE 1 123\n')
   self.assertEqual(len(p.command(s,{},['show','exploration'])),8)
   self.assertTrue(any('/pyramid load' in l for l in p.command(s,{},['page','0'])))
   with self.assertRaises(ValueError):p.close(s,'other',{},dict(id='exploration'))
   p.close(s,'guide',{},dict(id='exploration'));self.assertEqual(p.handle(s,conn,raw),'E ERROR 1\n')
   self.assertEqual(p.publish(s,'guide',{},args)['revision'],r['revision'])
 def test_sequence_vectors_and_geometry_bounds(self):
  for seed in [0,1,123,0xffffffff,0x12345678]:
   forecast=p.preview(seed)
   for f in forecast:
    self.assertEqual(len(f['seeds']),4);self.assertTrue(all(0<=v<=65535 for v in f['seeds']));self.assertTrue(0<=f['template']<16)
    self.assertEqual(len(f['layout_offsets']),8)
   self.assertEqual(p.preview(seed),forecast)
 def test_invalid_private_context_and_requests(self):
  s=self.server()
  for seed in [True,-1,2**32,'one']:
   with self.assertRaises(ValueError):p.publish(s,'a',{},dict(id='x',seed=seed))
  r=p.publish(s,'a',{},dict(id='x',seed=1));raw=f"E GET 1 x {r['revision']}".encode()
  self.assertEqual(p.handle(s,dict(id='a',presence={}),raw),'E ERROR 1\n')
  self.assertEqual(p.handle(s,dict(id='a',presence=dict(campaign_run='s')),b'E GET 0 x no'),'E ERROR 0\n')
  s.link_protocol.busy=lambda _:True;self.assertEqual(p.handle(s,dict(id='a',presence=dict(campaign_run='s')),raw),'E ERROR 1\n')
 def test_reopening_does_not_bypass_capacity(self):
  s=self.server();p.publish(s,'a',{},dict(id='old',seed=2));p.close(s,'a',{},dict(id='old'))
  for n in range(32):p.publish(s,'a',{},dict(id='course'+str(n),seed=n))
  with self.assertRaises(ValueError):p.publish(s,'a',{},dict(id='old',seed=2))
  p.close(s,'a',{},dict(id='course0'));p.publish(s,'a',{},dict(id='old',seed=2));self.assertEqual(len(p.catalog(s)),32)
