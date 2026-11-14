from concurrent.futures import Future
from copy import deepcopy
import hashlib,json,unittest
import test_region_characters as fixture
from world import actor_runtime
from world.practice_circuit import install,status,ACTORS,ID
from world.mechanics import Candidate
from world.character_companions import roster

class PracticeCircuitTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  # Retain an existing real NPC, geometry and mechanic while adding the venue.
  source='def update(context,state):\n    return dict(state=state,tiles=[],objects='+repr(self.s.objects)+')\n'
  self.s.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
 def admit(self):
  _,path,_=self.s.deployment;self.s.deployment=None;source=path.read_text();ns={};exec(source,ns)
  result=ns['update'](self.s._context(),deepcopy(self.s.module_state))
  f=Future();f.set_result((Candidate(source,hashlib.sha256(source.encode()).hexdigest()),result))
  self.s.job=(f,'deploy',None,self.s.interaction_cursor);self.s._poll_mechanics();self.assertIsNone(self.s.module_error)
 def test_host_install_actual_admission_plan_native_battle_and_restart(self):
  before=deepcopy(self.s.objects);shared=self.s.shared_cave.identity
  result=self.s.host_controls.request(dict(command='host_controls',action='practice'),self.s)
  self.assertEqual(result['practice']['status'],'staged');self.admit()
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded');self.assertEqual(status(self.s)['status'],'ready')
  self.assertTrue(all(o in self.s.objects for o in before));self.assertEqual(self.s.shared_cave.identity,shared)
  self.assertEqual(len(roster(self.s,'camp_final')),2)
  row=status(self.s);token=self.s.create_identity('Alice')['token'];c=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.assertIn('WELCOME',self.f.send(c,'HELLO 1 Alice '+token+' SOCIALCAVEREGION1CHAR1CHARQUEST1CHARREG1CORE1CHARPK1CHARSHOP1CHARTUTOR1'))
  self.f.state(c,0,9,8,8)
  self.assertIn('SELECTED',self.f.send(c,'REGION SELECT '+row['place']))
  self.assertIn('CAVE BEGIN',self.f.send(c,'CAVE GET'))
  self.assertIn('CAVE OK',self.f.send(c,'CAVE ACK '+row['revision']))
  self.f.state(c,*self.s.cave_map,1,1)
  self.f.state(c,*self.s.cave_map,6,7)
  snapshot=self.s._snapshot(c);self.assertIn('CHARACTER camp_gate 1',snapshot)
  from world.battle_campaigns import command,active
  from world.campaign_milestones import handle
  handle(self.s,c,'a'*32,'0','private');command(self.s,c,['start',ID])
  seq=c['seq']+1
  wire=self.f.send(c,f'CHARACTER_CHALLENGE_REGION {seq} camp_gate 1 {row["revision"]}')
  self.assertTrue(wire.startswith('CHARACTER_BATTLE_V2'),wire);self.assertIn(' 5 ',wire)
  self.f.send(c,f'CHARACTER_RESULT {seq} camp_gate 1 1')
  self.assertEqual(active(self.s,c)[1]['choices'],['sky','meadow'])
  command(self.s,c,['choose','sky']);command(self.s,c,['prepare','camp'])
  self.assertIn('CHARACTER_TUTOR camp_sky 1',self.s._snapshot(c))
  for actor,x,y in [('camp_sky',10,7),('camp_final',10,11)]:
   if actor=='camp_final':command(self.s,c,['choose','final']);command(self.s,c,['prepare','camp'])
   self.f.state(c,*self.s.cave_map,x,y);seq=c['seq']+1
   self.assertIn('CHARACTER_BATTLE_V2',self.f.send(c,f'CHARACTER_CHALLENGE_REGION {seq} {actor} 1 {row["revision"]}'))
   self.assertIn('CHARACTER_RESULT_ACK',self.f.send(c,f'CHARACTER_RESULT {seq} {actor} 1 1'))
  self.assertEqual(active(self.s,c)[1]['status'],'complete')
  self.assertEqual(len(active(self.s,c)[1]['history']),3)
  # Re-opening actual authority retains venue, population, campaign and owned identities.
  identities=roster(self.s,'camp_gate');self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.server=self.s
  self.assertEqual(status(self.s)['status'],'ready');self.assertEqual(roster(self.s,'camp_gate'),identities)
  self.assertEqual(install(self.s)['status'],'ready');self.assertIsNone(self.s.deployment)
 def test_source_grounding_and_no_claim_of_exact_canonical_teams(self):
  install(self.s);self.admit()
  from world.species_cohort import species_id
  teams=self.s.module_state['world_characters']
  self.assertEqual(teams['camp_gate']['team'][0]['species'],species_id('POOCHYENA','expansion-native'))
  self.assertEqual([m['level'] for m in teams['camp_sky']['team']],[4,3])
  self.assertEqual([m['level'] for m in teams['camp_final']['team']],[6,6])
  self.assertNotIn('Calvin',[teams[a]['name'] for a in ACTORS])
  self.assertTrue(all('not the original trainer' in teams[a]['reason'] for a in ACTORS))
 def test_staged_retry_and_capacity_do_not_overwrite(self):
  first=install(self.s);self.s.deployment=None
  self.assertEqual(install(self.s),first);self.assertIsNotNone(self.s.deployment)
  self.s.deployment=None;self.s.candidate=Candidate('different','f'*64)
  with self.assertRaisesRegex(ValueError,'replaced'):install(self.s)
