"""Actual authority/native controller pairing; engine drawing remains doubled."""
import importlib.util,os,tempfile,time,unittest
from pathlib import Path
import test_canonical_cast as fixture
from world import canonical_cast as cast

class CanonicalSceneTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  a=self.f.action();a['changes']['scene']='rydel_step';self.f.apply(a)
  self.a=self.f.peer('Alice');self.b=self.f.peer('Bob');self.run='a'*32
  self.s.peers.pop('Eve',None) # This scenario has two connected participants.
  for p in (self.a,self.b):
   self.send(p,'CORE '+self.run+' SYNC 0 private 1');self.send(p,'CORE '+self.run+' SCENES native private 2');self.send(p,'CORE SCENE HELLO '+self.run)
  self.f.query(self.a)
 def send(self,p,line):
  p['out'].clear();self.s._line(p,line.encode());return p['out'].decode().splitlines()
 def offer(self):
  self.send(self.a,'CORE SCENE ASK '+self.run+' rydel');self.assertIsNotNone(self.s.cast_scenes.offer)
  return self.s.cast_scenes.offer['token']
 def join(self,t):
  self.send(self.a,'CORE SCENE JOIN '+t);self.send(self.b,'CORE SCENE JOIN '+t)
  self.assertIsNotNone(self.s.cast_scenes.live)
 def test_native_two_observers_ack_each_real_step_before_authority_progress(self):
  root=os.environ.get('EW_NATIVE_SOURCE')
  if not root:self.skipTest('EW_NATIVE_SOURCE needed for production native controller')
  spec=importlib.util.spec_from_file_location('native_scene',Path(root)/'tests/test_world_cast_scene.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as tmp:
   binary=module.build(tmp);drivers=[module.Driver(binary),module.Driver(binary)]
   try:
    t=self.offer();self.join(t)
    def native(i,command):
     output=drivers[i].call(command)
     for line in output:
      if line.startswith('SEND '):self.send((self.a,self.b)[i],line[5:])
     return output
    prep='WIRE CORE SCENE PREPARE '+t+' 10 1 1 2 5 3 5'
    native(0,prep);self.assertEqual(self.s.cast_scenes.live['step'],0)
    native(1,prep);self.assertEqual(self.s.cast_scenes.live['step'],1)
    for i in (0,1):
     native(i,'WIRE CORE SCENE STEP '+t+' 1');native(i,'TICK');out=native(i,'TICK')
     self.assertIn('STATE 3 5 1 1',out)
     self.assertEqual(self.s.cast_scenes.live['step'],1 if i==0 else 2)
    for i in (0,1):
     native(i,'WIRE CORE SCENE STEP '+t+' 2');native(i,'TICK');native(i,'TICK')
    self.assertEqual(self.s.cast_scenes.leases.current.phase,'restoring')
    for i in (0,1):
     native(i,'WIRE CORE SCENE RETURN '+t);out=native(i,'TICK');self.assertIn('STATE 2 5 0 1',out)
    self.assertIsNone(self.s.cast_scenes.debt);self.assertIsNone(self.s.cast_scenes.live)
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_scene_recovery').fetchone()[0],0)
    for i in (0,1):self.assertIn('STATE 2 5 0 0',native(i,'WIRE CORE SCENE RELEASE '+t))
   finally:
    for d in drivers:d.close()
  self.assertEqual(self.s.objects,[])
  self.assertFalse(any(e['event']=='canonical_scene_completed' for e in self.s.memory.history()['events']))
 def test_no_forced_join_original_story_changes_or_early_restoration(self):
  t=self.offer();self.send(self.a,'CORE SCENE JOIN '+t)
  self.assertIsNone(self.s.cast_scenes.live);self.assertIsNone(self.s.cast_scenes.debt)
  self.send(self.b,'CORE SCENE DECLINE '+t);self.assertIsNone(self.s.cast_scenes.offer)
  self.a['cast_scene_next']=0;t=self.offer();self.join(t)
  for p in (self.a,self.b):self.send(p,'CORE SCENE ACK '+t)
  self.assertIn('CORE SCENE REFUSED',self.send(self.a,'CORE SCENE HOME '+t))
  self.send(self.b,'CORE SCENE CANCEL '+t)
  self.send(self.a,'CORE SCENE HOME '+t);self.assertIsNotNone(self.s.cast_scenes.debt)
  self.send(self.b,'CORE SCENE HOME '+t);self.assertIsNone(self.s.cast_scenes.debt)
 def test_restart_preserves_restoration_debt_and_fences_new_scenes(self):
  t=self.offer();self.join(t)
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s
  self.assertEqual(self.s.cast_scenes.debt['remaining'],['Alice','Bob'])
  peers=[self.f.peer(name) for name in ('Alice','Bob')]
  for p in peers:
   self.send(p,'CORE '+self.run+' SYNC 0 private 1')
   self.send(p,'CORE '+self.run+' SCENES native private 2');lines=self.send(p,'CORE SCENE HELLO '+self.run)
   self.assertIn('CORE SCENE RECOVER '+t+' 10 1 1 2 5',lines)
  self.f.query(peers[0]);self.assertIn('CORE SCENE REFUSED',self.send(peers[0],'CORE SCENE ASK '+self.run+' rydel'))
  self.assertIn('CORE SCENE REFUSED',self.send(peers[0],'CORE SCENE HOME '+'b'*32))
  for p in peers:self.send(p,'CORE SCENE HOME '+t)
  self.assertIsNone(self.s.cast_scenes.debt)
 def test_legacy_remote_and_occupied_path_refuse_before_native_motion(self):
  self.b.pop('cast_scene_run');self.assertIn('CORE SCENE REFUSED',self.send(self.a,'CORE SCENE ASK '+self.run+' rydel'))
  self.send(self.b,'CORE SCENE HELLO '+self.run);t=self.offer()
  self.b['state'][2:4]=[3,5]
  self.send(self.a,'CORE SCENE JOIN '+t);self.assertIn('CORE SCENE REFUSED',self.send(self.b,'CORE SCENE JOIN '+t))
  self.assertIsNone(self.s.cast_scenes.debt)
 def test_disconnect_restores_remaining_observers_and_keeps_missing_save_debt(self):
  t=self.offer();self.join(t)
  for p in (self.a,self.b):self.send(p,'CORE SCENE ACK '+t)
  self.a['closing']=True;self.s.cast_scenes.disconnected(self.a)
  self.assertEqual(self.s.cast_scenes.leases.current.phase,'restoring')
  self.assertIn('CORE SCENE REFUSED',self.send(self.b,'CORE SCENE AT '+t+' 1'))
  self.send(self.b,'CORE SCENE HOME '+t)
  self.assertIsNone(self.s.cast_scenes.live)
  self.assertEqual(self.s.cast_scenes.debt['remaining'],['Alice'])
  replacement=self.f.peer('Alice')
  other='c'*32
  self.send(replacement,'CORE '+other+' SYNC 0 private 1')
  self.send(replacement,'CORE '+other+' SCENES native private 2')
  self.assertFalse(any('RECOVER' in line for line in self.send(replacement,'CORE SCENE HELLO '+other)))
  self.assertIn('CORE SCENE REFUSED',self.send(replacement,'CORE SCENE HOME '+t))
  self.send(replacement,'CORE '+self.run+' SYNC 0 private 3')
  self.assertTrue(any('RECOVER' in line for line in self.send(replacement,'CORE SCENE HELLO '+self.run)))
  self.send(replacement,'CORE SCENE HOME '+t);self.assertIsNone(self.s.cast_scenes.debt)
