"""Ownership/reservation state machine only; no native actor is moved."""
import unittest
from world.canonical_scene_leases import SceneLeases

class SceneLeaseTests(unittest.TestCase):
 def setUp(self):
  self.now=0;self.n=0;self.a=object();self.b=object()
  def token():self.n+=1;return str(self.n)
  self.s=SceneLeases(lambda:self.now,token)
 def prepare(self):
  return self.s.prepare('canon_rydel',(9,0),[(4,4),(5,4),(4,4)],self.a,[self.a,self.b],validate_tile=lambda m,p:True)['token']
 def ack(self,p,t):return self.s.acknowledge(p,t,home=True,clear=True,installed=True)
 def test_all_peers_install_before_motion_and_all_restore_before_release(self):
  t=self.prepare();self.assertFalse(self.s.admits_connection());self.assertTrue(self.s.blocks((9,0),4,4))
  self.assertFalse(self.s.blocks((9,1),4,4));self.assertFalse(self.s.blocks((9,0),6,4))
  self.assertFalse(self.ack(self.a,t))
  with self.assertRaises(ValueError):self.s.start(self.a,t)
  self.assertTrue(self.ack(self.b,t))
  with self.assertRaises(ValueError):self.s.start(self.b,t)
  self.s.start(self.a,t);self.s.finish(self.a,t)
  self.assertFalse(self.s.restored(self.a,t,home=True,idle=True))
  self.assertTrue(self.s.blocks((9,0),4,4))
  self.assertTrue(self.s.restored(self.b,t,home=True,idle=True))
  self.assertTrue(self.s.admits_connection());self.assertFalse(self.s.blocks((9,0),4,4))
 def test_deadlines_disconnect_and_new_sessions_never_infer_restoration(self):
  t=self.prepare();self.ack(self.a,t);self.ack(self.b,t);self.s.start(self.a,t)
  self.now=11;self.assertEqual(self.s.tick()['phase'],'restoring')
  self.now=10000;self.s.tick();self.assertFalse(self.s.admits_connection())
  with self.assertRaises(ValueError):self.s.restored(object(),t,home=True,idle=True)
  with self.assertRaises(ValueError):self.s.restored(self.a,t,home=False,idle=True)
  self.s.disconnected(self.a);self.assertTrue(self.s.blocks((9,0),4,4))
  with self.assertRaises(ValueError):self.prepare()
 def test_failed_prepare_requires_release_ack_and_stale_tokens_are_fenced(self):
  t=self.prepare();self.assertFalse(self.s.acknowledge(self.b,t,home=True,clear=False,installed=True))
  self.assertEqual(self.s.snapshot()['phase'],'restoring')
  self.s.restored(self.a,t,home=True,idle=True);self.s.restored(self.b,t,home=True,idle=True)
  next_token=self.prepare();self.assertNotEqual(t,next_token)
  with self.assertRaises(ValueError):self.ack(self.a,t)
  self.now=4;self.assertFalse(self.ack(self.a,next_token))
  self.assertTrue(self.s.blocks((9,0),5,4))
 def test_bad_routes_geometry_and_duplicate_peers_cannot_reserve(self):
  for path in ([(4,4),(5,4)],[(4,4),(6,4),(4,4)],[(4,4),(5,4),(6,4)],[(4,4),(True,4),(4,4)]):
   with self.subTest(path=path),self.assertRaises(ValueError):
    self.s.prepare('canon_rydel',(9,0),path,self.a,[self.a],validate_tile=lambda m,p:True)
  with self.assertRaises(ValueError):
   self.s.prepare('canon_rydel',(9,0),[(4,4),(5,4),(4,4)],self.a,[self.a],validate_tile=lambda m,p:False)
  with self.assertRaises(ValueError):
   self.s.prepare('canon_rydel',(9,0),[(4,4),(5,4),(4,4)],self.a,[self.a,self.a],validate_tile=lambda m,p:True)
  self.assertIsNone(self.s.current)
