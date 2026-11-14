import unittest
from copy import deepcopy
import test_region_characters as fixture
from world import cave_links

class CaveLinkTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.obj=dict(self.f.obj,id='door',kind='prop',portable=False,gfx=0,x=4,y=3,text='A passage.')
  self.f.commit(dict(state=self.s.module_state,tiles=[],objects=self.s.objects+[self.obj]))
  from world.actor_observation import observe
  entry=next(e for e in observe(self.s,'harbor_guide',{},dict(radius=4))['entities'] if e['id']=='door')
  with self.s.db:self.result=cave_links.install(self.s,'harbor_guide',{},dict(object='door',revision=entry['program_revision'],place=self.f.f.rb['place_id'],destination=self.f.f.b))
 def connect(self,name):
  token=self.s.create_identity(name)['token'];conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.assertIn('WELCOME',self.f.send(conn,f'HELLO 1 {name} {token} SOCIALCAVEREGION1CHAR1CHARQUEST1CHARREG1WORLDOBJ1CAVELINK1'))
  self.f.state(conn,0,9,8,8);self.f.send(conn,'REGION SELECT '+self.f.f.ra['place_id']);self.f.send(conn,'CAVE GET');self.f.send(conn,'CAVE ACK '+self.f.f.a)
  self.f.state(conn,*self.s.cave_map,3,3);return conn
 def test_real_interaction_consent_staging_ack_arrival_and_independent_peer(self):
  a=self.connect('Alice');b=self.connect('Bob');seq=a['seq']+1
  wire=self.f.send(a,f'INTERACT_REGION {seq} door {self.f.f.a}');self.assertIn('LINK OFFER',wire)
  self.assertEqual(a['cave_ack'],self.f.f.a)
  data=self.f.send(a,f'LINK ACCEPT {seq}');self.assertIn('LINK DATA',data);self.assertEqual(a['cave_ack'],self.f.f.a)
  self.assertIn('LINK COMMIT',self.f.send(a,f'LINK ACK {seq} {self.f.f.b}'));self.assertIsNone(a['state']);self.assertEqual(b['cave_ack'],self.f.f.a)
  self.f.state(a,*self.s.cave_map,1,1)
  self.assertIn('LINK DONE',self.f.send(a,f'LINK ARRIVED {seq} {self.f.f.b}'));self.assertIsNone(a['cave_link_pending'])
 def test_abort_keeps_source_and_no_stale_ready_state(self):
  a=self.connect('Alice');seq=a['seq']+1;self.f.send(a,f'INTERACT_REGION {seq} door {self.f.f.a}')
  self.f.send(a,f'LINK ABORT {seq}');self.assertEqual(a['cave_ack'],self.f.f.a);self.assertIsNone(a['state'])

 def test_paired_actual_native_decoder_pump_and_authority_frames(self):
  import tempfile,sys,subprocess
  from pathlib import Path
  import os
  root=Path(os.environ.get('EW_LINK_NATIVE_SOURCE',Path(__file__).resolve().parents[3]/'native-cave-links'))
  if not (root/'tests/link_fixture.py').exists():self.skipTest('requires paired cave-link native sources')
  sys.path.insert(0,str(root/'tests'));from link_fixture import build
  a=self.connect('Alice');seq=a['seq']+1
  offer=self.f.send(a,f'INTERACT_REGION {seq} door {self.f.f.a}');offer=next(l for l in offer.splitlines() if l.startswith('LINK OFFER'))
  frames=self.f.send(a,f'LINK ACCEPT {seq}');commit=self.f.send(a,f'LINK ACK {seq} {self.f.f.b}');commit=next(l for l in commit.splitlines() if l.startswith('LINK COMMIT'))
  self.f.state(a,*self.s.cave_map,1,1);done=self.f.send(a,f'LINK ARRIVED {seq} {self.f.f.b}');done=next(l for l in done.splitlines() if l.startswith('LINK DONE'))
  transcript=offer+'\nPUMP\nYES\n'+frames+'PUMP\n'+commit+'\nPUMP\nLANDED\n'+done+'\n'
  with tempfile.TemporaryDirectory() as d:
   binary=build(root,d);run=subprocess.run([str(binary),self.f.f.a,str(seq)],input=transcript,text=True,capture_output=True)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertIn(f'LINK ACK {seq} {self.f.f.b}',run.stdout);self.assertIn('RESULT 0 1 '+self.f.f.b,run.stdout)
   bad=transcript.replace('LINK COMMIT '+str(seq),'LINK COMMIT '+str(seq+1));rejected=subprocess.run([str(binary),self.f.f.a,str(seq)],input=bad,text=True,capture_output=True);self.assertNotEqual(rejected.returncode,0)

 def test_committed_abort_and_stale_ack_do_not_restore_ready_coordinates(self):
  a=self.connect('Alice');seq=a['seq']+1;self.f.send(a,f'INTERACT_REGION {seq} door {self.f.f.a}');self.f.send(a,f'LINK ACCEPT {seq}')
  self.f.send(a,f'LINK ACK {seq} {self.f.f.b}');self.f.send(a,f'LINK ABORT {seq}')
  self.assertEqual(a['cave_ack'],self.f.f.a);self.assertIsNone(a['state'])
  self.f.state(a,*self.s.cave_map,3,3);a['last_interaction']=-1;seq=a['seq']+1
  self.f.send(a,f'INTERACT_REGION {seq} door {self.f.f.a}');self.f.send(a,f'LINK ACCEPT {seq}');a['state_time']=0
  self.assertNotIn('LINK COMMIT',self.f.send(a,f'LINK ACK {seq} {self.f.f.b}'));self.assertEqual(a['cave_ack'],self.f.f.a)
 def test_link_persists_without_claiming_a_player_visit(self):
  source=self.f.f.a;target=self.f.f.b
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.server=self.s
  self.assertEqual(self.s.db.execute('SELECT source,destination FROM cave_links WHERE object=?',('door',)).fetchone(),(source,target))
  self.assertEqual(self.s.db.execute("SELECT count(*) FROM events WHERE kind='cave_link_arrival'").fetchone()[0],0)

class HabitatLinkTests(CaveLinkTests):
 def setUp(self):
  super().setUp()
  import hashlib,time
  from world.shared_cave import SharedCave
  raw=self.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(self.f.f.b,)).fetchone()[0]
  population=bytes([25])+bytes([22,1,18])*12
  blob=b'EWGMAP10'+bytes([2])+population+raw[8:]
  cave=SharedCave(blob);self.habitat=cave.identity;self.population=population
  with self.s.db:
   self.s.db.execute('INSERT INTO generated_area_archive VALUES(?,?,?,?,?)',(cave.identity,'Habitat','cave',blob,int(time.time())))
   self.habitat_place=self.s._pin_region(cave.identity)['place_id']
   self.s.db.execute('DELETE FROM cave_links WHERE object=?',('door',))
  from world.actor_observation import observe
  entry=next(e for e in observe(self.s,'harbor_guide',{},dict(radius=4))['entities'] if e['id']=='door')
  with self.s.db:cave_links.install(self.s,'harbor_guide',{},dict(object='door',revision=entry['program_revision'],place=self.habitat_place,destination=self.habitat))
  self.f.f.b=self.habitat
 def connect(self,name):
  token=self.s.create_identity(name)['token'];conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.assertIn('WELCOME',self.f.send(conn,f'HELLO 1 {name} {token} SOCIALCAVE10REGION1CHAR1CHARQUEST1CHARREG1WORLDOBJ1CAVELINK1CAVELINKW1'))
  self.f.state(conn,0,9,8,8);self.f.send(conn,'REGION SELECT '+self.f.f.ra['place_id']);self.f.send(conn,'CAVE GET');self.f.send(conn,'CAVE ACK '+self.f.f.a)
  self.f.state(conn,*self.s.cave_map,3,3);return conn
 def test_old_link_client_cannot_commit_wildlife_destination(self):
  a=self.connect('Legacy');a['cave_link_wildlife']=False
  wire=self.f.send(a,f'INTERACT_REGION {a["seq"]+1} door {self.f.f.a}')
  self.assertNotIn('LINK OFFER',wire);self.assertEqual(a['cave_ack'],self.f.f.a)
 def test_habitat_population_prop_scope_and_reconnect(self):
  a=self.connect('Explorer');seq=a['seq']+1
  self.f.send(a,f'INTERACT_REGION {seq} door {self.f.f.a}');frames=self.f.send(a,f'LINK ACCEPT {seq}')
  self.assertIn(self.population.hex(),frames)
  self.f.send(a,f'LINK ACK {seq} {self.habitat}');self.f.state(a,*self.s.cave_map,1,1);self.f.send(a,f'LINK ARRIVED {seq} {self.habitat}')
  self.assertEqual(self.s._connection_cave(a).wildlife,self.population)
  # Real validated placement of a persistent return object on this cave geometry.
  back=dict(self.obj,id='return_door',region_revision=self.habitat,x=4,y=3)
  self.f.commit(dict(state=self.s.module_state,tiles=[],objects=self.s.objects+[back]))
  self.assertIsNone(self.s.module_error)
  self.f.state(a,*self.s.cave_map,3,3)
  self.assertIn('return_door',self.s._snapshot(a))
  # Reconnect never asserts arrival or restores guessed readiness; reselecting
  # the persisted exact region downloads the same wildlife.
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.server=self.s
  b=self.connect('Reconnect')
  self.f.state(b,0,9,8,8);self.f.send(b,'REGION SELECT '+self.habitat_place)
  self.assertIn(self.population.hex(),self.f.send(b,'CAVE GET'))
  self.assertNotEqual(b.get('cave_ack'),self.habitat)
