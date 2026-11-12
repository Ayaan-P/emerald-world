"""Real public guild events -> bounded first actor -> original native CAST reply.
The deterministic author below is a fixture, not a live model.
"""
import json,tempfile,unittest
from world import canonical_seeds as seeds,character_reactions as reactions,canonical_cast as cast
from world.runtime_gm import IntentQueue
from world.build_catalog import catalog_maps
import test_canonical_cast as fixtures

class SeedTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.q=IntentQueue(self.tmp.name);self.addCleanup(lambda:self.q.close())
 def observe(self):return reactions.observe(self.q,self.f.s.inspect(),self.f.fetch)
 def complete(self):
  pair=next(p for p,m in catalog_maps().items() if m['name']=='MauvilleCity_Gym')
  self.f.f.command('expedition start MauvilleCity_Gym 2')
  self.f.f.state('Alice',location=pair);self.f.f.state('Bob',location=pair)
 def test_future_evidence_initializes_original_actor_then_continues(self):
  seeds.enroll(self.q,self.f.s.inspect());self.assertEqual(self.observe(),[])
  self.assertNotIn('canonical_cast',self.f.s.module_state)
  self.complete();self.assertEqual(len(self.observe()),2) # Wally and Rydel interests, not invented participation.
  item=self.q.claim();packet=json.loads(item['result']);self.assertTrue(packet['bootstrap'])
  context=self.f.context();context['runtime'].update(kind='character',observed_event=packet)
  reactions.prepare(context,self.f.fetch);self.assertIn('source',context['canonical_identity'])
  action=dict(id=packet['id'],expected_version=0,changes=dict(goal='Consider how trainers prepare for the local Gym',dialogue='The local Gym has been busy. I have something to think about.',places=['native:MauvilleCity_Gym'],evidence=[packet['evidence']],reason='Actual public group arrival informs a new idea, not a victory'))
  reactions.check_response(dict(canonical_actions=[action],tests=''),packet)
  self.f.apply(action);self.q.finish(item['id'],'succeeded',dict(ok=True))
  self.assertEqual(self.f.s.objects,[])
  if packet['id']=='canon_rydel':self.assertIn('local Gym',bytes.fromhex(self.f.query(self.f.peer()).split()[-1]).decode())
  with self.assertRaises(ValueError):reactions.prepare(self.f.context()|{'runtime':dict(kind='character',observed_event=packet)},self.f.fetch)
  self.complete();self.observe()
  row=self.q.db.execute("SELECT result FROM requests WHERE player=? AND status='queued' ORDER BY seq DESC",(packet['id'],)).fetchone()
  next_packet=json.loads(row[0]);self.assertEqual(next_packet['expected_version'],1);self.assertNotIn('bootstrap',next_packet)
 def test_restart_idempotence_and_unfollow(self):
  self.complete() # Existing relevant history is not backfilled.
  seeds.enroll(self.q,self.f.s.inspect());before=reactions.subscriptions(self.q)
  self.assertEqual(self.observe(),[])
  self.q.close();self.q=IntentQueue(self.tmp.name);seeds.enroll(self.q,self.f.s.inspect())
  self.assertEqual(reactions.subscriptions(self.q),before)
  reactions.unfollow(self.q,'canon_rydel');self.complete();self.observe()
  self.assertFalse(self.q.db.execute("SELECT 1 FROM requests WHERE player='canon_rydel'").fetchone())
 def test_profiles_are_known_bindings_not_event_evidence(self):
  maps={m['name'] for m in catalog_maps().values()}
  for actor in seeds.PROFILES:
   self.assertTrue(set(seeds.PROFILES[actor]['places'])<=maps)
   self.assertEqual(seeds.profile(actor)['binding'],cast.BINDINGS[actor])
   self.assertFalse(cast.decision_evidence(seeds.profile(actor),actor,seeds.pending(actor)))

 def test_commission_starts_five_without_campaign_sharing_or_fake_outcomes(self):
  seeds.initialize(self.q,self.f.s)
  events=[e for e in self.f.s.memory.history()['events'] if e['event']=='canonical_actor_commissioned']
  expected={'canon_birch','canon_rydel','canon_wally','canon_briney','canon_steven'}
  self.assertEqual({e['character_id'] for e in events},expected)
  self.assertEqual(len(events),5);self.assertEqual(len(self.observe()),5)
  item=self.q.claim();packet=json.loads(item['result']);actor=packet['id']
  context=self.f.context();context['runtime'].update(kind='character',observed_event=packet)
  reactions.prepare(context,self.f.fetch)
  action=dict(id=actor,expected_version=0,changes=dict(goal='Consider what I can offer local trainers',dialogue='Hello! It is good to see trainers here.',places=['native:'+cast.BINDINGS[actor]['map']],evidence=[packet['evidence']],reason='Initial identity-based outlook requested by the host, not an earned outcome'))
  # Fixture author, normal compiler and real atomic world admission.
  self.f.apply(action);self.q.finish(item['id'],'succeeded',dict(ok=True))
  self.assertEqual(self.f.s.objects,[])
  # Commission cannot enable a service/project or justify later growth.
  action['expected_version']=1
  with self.assertRaises(ValueError):cast.compile_actions([action],self.f.context())
  seeds.initialize(self.q,self.f.s)
  self.assertEqual(len([e for e in self.f.s.memory.history()['events'] if e['event']=='canonical_actor_commissioned']),5)
  self.assertEqual(len(self.observe()),1) # New committed goal, not replayed commissioning.
  planning=self.q.db.execute("SELECT result FROM requests WHERE player=? AND status='queued'",(actor,)).fetchone()
  self.assertTrue(json.loads(planning[0])['self_direction'])
  other=next(a for a in seeds.PROFILES if a!=actor)
  e=next(e for e in events if e['character_id']==other)
  row=dict(version=1,goal='Initial goal',dialogue='Hello.',places=['native:'+cast.BINDINGS[other]['map']],evidence=[e['seq']],reason='Initial request',offer=dict(map='LittlerootTown',count=1))
  self.assertFalse(cast.decision_evidence(e,other,row))

 def test_unfollow_reenroll_does_not_replay_commission(self):
  seeds.initialize(self.q,self.f.s);self.observe()
  for actor in seeds.PROFILES:reactions.unfollow(self.q,actor)
  self.q.close();self.q=IntentQueue(self.tmp.name)
  seeds.initialize(self.q,self.f.s)
  self.assertEqual(self.observe(),[])
