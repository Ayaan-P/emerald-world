"""Two native observers execute the reviewed Steven path, not a position mock."""
import importlib.util,os,tempfile,unittest
from pathlib import Path
import test_canonical_scenes as base
from world import canonical_cast as cast

class CanonicalPathTests(unittest.TestCase):
 def setUp(self):
  self.f=base.CanonicalSceneTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.a=self.f.a;self.b=self.f.b;self.run=self.f.run
  action=self.f.f.action();action['id']='canon_steven';action['changes']['scene']='steven_study'
  self.f.f.apply(action)
  for p in (self.a,self.b):
   p['state'][:4]=[14,7,7,6]
   self.f.send(p,'CORE SCENE HELLO2 '+self.run)
  cast.response(self.s,self.a,self.run,'steven')
 def offer(self):
  self.f.send(self.a,'CORE SCENE ASK '+self.run+' steven')
  self.assertIsNotNone(self.s.cast_scenes.offer)
  t=self.s.cast_scenes.offer['token'];self.f.join(t);return t
 def test_actual_native_observers_walk_four_steps_and_restore_original_actor(self):
  root=os.environ.get('EW_NATIVE_SOURCE')
  if not root:self.skipTest('production native source required')
  spec=importlib.util.spec_from_file_location('path_native',Path(root)/'tests/test_world_cast_scene.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as tmp:
   binary=module.build(tmp);drivers=[module.Driver(binary),module.Driver(binary)]
   try:
    t=self.offer()
    def native(i,command):
     out=drivers[i].call(command)
     for line in out:
      if line.startswith('SEND '):self.f.send((self.a,self.b)[i],line[5:])
     return out
    for i in (0,1):
     native(i,'STEVEN');native(i,'WIRE CORE SCENE PREPARE_PATH '+t+' steven_study')
    for step,x in ((1,5),(2,4),(3,5),(4,6)):
     for i in (0,1):
      self.assertEqual(self.s.cast_scenes.live['step'],step)
      native(i,'WIRE CORE SCENE STEP '+t+' '+str(step));native(i,'TICK');out=native(i,'TICK')
      self.assertIn('SEND CORE SCENE AT '+t+' '+str(step),out)
      self.assertTrue(any(line.startswith('STATE '+str(x)+' 5 1') for line in out))
    self.assertEqual(self.s.cast_scenes.leases.current.phase,'restoring')
    for i in (0,1):
     native(i,'WIRE CORE SCENE RETURN '+t);out=native(i,'TICK')
     self.assertIn('SEND CORE SCENE HOME '+t,out)
    self.assertIsNone(self.s.cast_scenes.debt)
    self.assertEqual(self.s.objects,[])
   finally:
    for d in drivers:d.close()
 def test_legacy_observer_and_occupied_route_cannot_start(self):
  self.f.send(self.b,'CORE SCENE HELLO '+self.run)
  self.assertIn('CORE SCENE REFUSED',self.f.send(self.a,'CORE SCENE ASK '+self.run+' steven'))
  self.f.send(self.b,'CORE SCENE HELLO2 '+self.run)
  self.f.send(self.a,'CORE SCENE ASK '+self.run+' steven');t=self.s.cast_scenes.offer['token']
  self.b['state'][2:4]=[4,5]
  self.f.send(self.a,'CORE SCENE JOIN '+t)
  self.assertIn('CORE SCENE REFUSED',self.f.send(self.b,'CORE SCENE JOIN '+t))
  self.assertIsNone(self.s.cast_scenes.debt)
 def test_restart_recovers_exact_actor_path_not_rydel_home(self):
  t=self.offer();self.s.close();case=self.f.f.f.case;case.server=case.open();self.s=case.server;self.f.s=self.s;self.f.f.s=self.s
  self.assertEqual(self.s.cast_scenes.debt['path'],'steven_study')
  p=self.f.f.peer('Alice')
  self.f.send(p,'CORE '+self.run+' SYNC 0 private 1');self.f.send(p,'CORE '+self.run+' SCENES native private 2')
  lines=self.f.send(p,'CORE SCENE HELLO2 '+self.run)
  self.assertIn('CORE SCENE RECOVER_PATH '+t+' steven_study',lines)
  self.assertNotIn('CORE SCENE RECOVER '+t+' 14 7 1 2 5',lines)
