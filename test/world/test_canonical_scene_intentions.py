"""Actor intention -> actual encounter -> native path -> later authored world action."""
import copy,json,tempfile,unittest
import test_canonical_paths as paths
import test_canonical_world_actions as world_actions
from world import canonical_cast as cast,canonical_world_actions as actions,character_reactions as reactions
from world.runtime_gm import IntentQueue

class SceneIntentionTests(paths.CanonicalPathTests):
 def setUp(self):
  super().setUp()
  a=self.f.f.action(1);a['id']='canon_steven'
  a['changes'].update(scene='steven_study',intentions=[dict(id='look_together',kind='scene',target='steven_study',reason='Make room to consider the collection together, then reconsider my next plan.')])
  self.f.f.apply(a);cast.response(self.s,self.a,self.run,'steven')
 def offer(self):
  self.s.cast_scenes.tick();self.assertIsNotNone(self.s.cast_scenes.offer)
  self.assertEqual(self.s.cast_scenes.offer['intention'],'look_together')
  t=self.s.cast_scenes.offer['token'];self.f.join(t);return t
 def test_physical_result_enters_real_author_queue_and_changes_available_project(self):
  project=world_actions.pack();project['scenes']['organize']['actors']=['canon_steven']
  self.s.opportunities.publish(project)
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_steven','Choose what to do after a real supported activity, without claiming research or travel.')
    reactions.observe(q,self.s.inspect(),self.f.f.fetch)
    # Uses compiled production C for both observers, not forged success packets.
    self.test_actual_native_observers_walk_four_steps_and_restore_original_actor()
    events=[e for e in self.s.memory.history()['events'] if e['event']=='canonical_scene_observed']
    self.assertEqual(len(events),1);event=events[0]
    self.assertEqual(event['steps'],4)
    self.assertEqual(event['source'],'cohort_native_attestation')
    self.assertNotIn('Alice',json.dumps(event));self.assertNotIn(self.run,json.dumps(event))
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.f.fetch)),1)
    item=q.claim();ctx=self.f.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    a=self.f.f.action(2);a['id']='canon_steven';a['changes'].update(evidence=[event['seq']],
      world_action=dict(pack='workshop',scene='organize',choice='open',place='LittlerootTown',revision=0),
      intentions=[dict(id='share_next',kind='world_action',target='workshop',reason='Make a public discussion available after the observed activity.')])
    reactions.check_response(dict(canonical_actions=[a],tests='assert True'),reactions.prepare(ctx,self.f.f.fetch))
    self.f.f.apply(a);self.assertEqual(actions.step(self.s,now=100)['status'],'completed')
    self.assertEqual(self.s.opportunities.offers('Alice','LittlerootTown')[0]['scenes'][0]['id'],'solo')
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
   finally:q.close()
 def test_decline_does_not_spam_complete_or_publish(self):
  self.s.cast_scenes.tick();t=self.s.cast_scenes.offer['token']
  self.f.send(self.a,'CORE SCENE DECLINE '+t)
  self.s.cast_scenes.tick();self.assertIsNone(self.s.cast_scenes.offer)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_intent_receipts').fetchone()[0],0)
  self.assertFalse(any(e['event']=='canonical_scene_observed' for e in self.s.memory.history()['events']))
 def test_cancelled_path_cannot_become_success_or_authored_fulfillment(self):
  t=self.offer()
  for p in (self.a,self.b):self.f.send(p,'CORE SCENE ACK '+t)
  self.f.send(self.a,'CORE SCENE CANCEL '+t)
  for p in (self.a,self.b):self.f.send(p,'CORE SCENE HOME '+t)
  self.assertFalse(any(e['event']=='canonical_scene_observed' for e in self.s.memory.history()['events']))
  a=self.f.f.action(2);a['id']='canon_steven';a['changes'].update(fulfill='look_together',intentions=[])
  with self.assertRaisesRegex(ValueError,'native observation'):cast.compile_actions([a],self.f.f.context())
 def test_record_failure_keeps_last_restoration_pending(self):
  from unittest.mock import patch
  t=self.offer()
  for p in (self.a,self.b):self.s.cast_scenes.handle(p,['ACK',t])
  for n in range(1,5):
   for p in (self.a,self.b):self.s.cast_scenes.handle(p,['AT',t,str(n)])
  self.s.cast_scenes.handle(self.a,['HOME',t])
  with patch.object(self.s.memory,'append',side_effect=ValueError('database refused')):
   with self.assertRaises(ValueError):self.s.cast_scenes.handle(self.b,['HOME',t])
  self.assertEqual(self.s.cast_scenes.debt['remaining'],['Bob'])
  self.s.cast_scenes.handle(self.b,['HOME',t])
  self.assertIsNone(self.s.cast_scenes.debt)
  self.assertEqual(len([e for e in self.s.memory.history()['events'] if e['event']=='canonical_scene_observed']),1)
