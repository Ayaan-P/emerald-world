"""Independent cast decisions gate actual world work, not inferred meetings."""
from copy import deepcopy
import json,tempfile,unittest
import test_canonical_construction as construction_fixture
from world import canonical_cast as cast,canonical_construction as build,character_reactions as reactions
from world.runtime_gm import IntentQueue

class CooperationTests(unittest.TestCase):
 def setUp(self):
  self.f=construction_fixture.CastConstructionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.author=self.f.f
  other=self.author.action();other['id']='canon_steven';self.author.apply(other)
  self.owner=deepcopy(self.f.action);self.owner['expected_version']=1
  self.owner['changes']['worksite']['partners']=['canon_steven']
 def invite(self):
  self.author.apply(self.owner)
  return self.s.memory.history()['events'][-1]
 def decide(self,invitation,choice='join',version=1):
  a=self.author.action(version);a['id']='canon_steven'
  a['changes'].update(goal='Choose whether this courtyard fits my field interests',
      evidence=[invitation['seq']],cooperate=dict(owner='canon_briney',intention='resting_court',signature=invitation['signature'],decision=choice))
  self.author.apply(a);return a
 def test_independent_choice_blocks_then_commits_and_both_can_grow(self):
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    for who in ('canon_steven','canon_briney'):reactions.configure(q,self.s.inspect(),who,'Choose independently whether this shared project serves your goals.')
    invitation=self.invite()
    self.assertEqual(invitation['event'],'canonical_project_invited')
    waiting=build.step(self.s,now=10);self.assertEqual(waiting['status'],'waiting')
    self.assertEqual(self.s.shared_cave.identity,self.f.previous)
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.author.fetch)),1)
    turn=q.claim();self.assertEqual(turn['player'],'canon_steven')
    ctx=self.author.context();ctx['runtime'].update(kind='character',observed_event=json.loads(turn['result']))
    self.assertEqual(reactions.prepare(ctx,self.author.fetch)['id'],'canon_steven')
    self.decide(invitation,'decline')
    q.finish(turn['id'],'succeeded',dict(ok=True))
    self.assertEqual(build.step(self.s,now=20)['status'],'waiting')
    self.assertIn('decline',' '.join(build.lines(self.s,'canon_briney')))
    # The owner can react to refusal but cannot write Steven's decision.
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.author.fetch)),1)
    declined=q.claim();self.assertEqual(declined['player'],'canon_briney')
    q.finish(declined['id'],'succeeded',dict(ok=True))
    agreed=self.decide(invitation,'join',version=2)
    # Clear the owner's actual join notification; the completion is a separate fact.
    for key in reactions.observe(q,self.s.inspect(),self.author.fetch):
     item=q.claim();q.finish(item['id'],'succeeded',dict(ok=True))
    self.assertEqual(build.step(self.s,now=30)['status'],'completed')
    result=self.s.memory.history()['events'][-1]
    self.assertEqual(result['participants'],['canon_briney','canon_steven'])
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.author.fetch)),2)
    self.assertTrue(self.s.shared_cave.walkable(18,23))
    # A directional assessment is earned by actual agreed work, not an invitation.
    changed=deepcopy(agreed);changed['expected_version']=3
    changed['changes'].update(evidence=[result['seq']],goal='Consider another joint project after the courtyard succeeded',
        relationships={'canon_briney':dict(stance='respectful',motivation='Our agreed courtyard project was committed successfully.',evidence=[result['seq']])})
    self.author.apply(changed)
    self.assertEqual(cast.records(self.s.module_state)['canon_steven']['relationships']['canon_briney']['stance'],'respectful')
    # Nothing forces Briney to have the reciprocal feeling.
    self.assertNotIn('relationships',cast.records(self.s.module_state)['canon_briney'])
   finally:q.close()
  self.s.close();self.author.f.case.server=self.author.f.case.open();self.s=self.author.f.case.server
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_construction_receipts').fetchone()[0],1)
  self.assertEqual(cast.records(self.s.module_state)['canon_steven']['cooperate']['decision'],'join')
 def test_changed_plan_invalidates_old_agreement_and_invitation(self):
  old=self.invite();self.decide(old)
  updated=deepcopy(self.owner);updated['expected_version']=2;updated['changes']['worksite']['plan']['x']=35
  self.author.apply(updated)
  new=self.s.memory.history()['events'][-1];self.assertNotEqual(new['signature'],old['signature'])
  self.assertEqual(build.step(self.s,now=10)['status'],'waiting')
  bad=self.author.action(2);bad['id']='canon_steven';bad['changes'].update(evidence=[old['seq']],cooperate=dict(owner='canon_briney',intention='resting_court',signature=old['signature'],decision='decline'))
  with self.assertRaisesRegex(ValueError,'changed or was withdrawn'):cast.compile_actions([bad],self.author.context())
  self.decide(new,version=2);self.assertEqual(build.step(self.s,now=20)['status'],'completed')
 def test_cannot_infer_relationship_or_join_without_invitation(self):
  invitation=self.invite()
  fake=self.author.action(1);fake['id']='canon_steven'
  fake['changes'].update(evidence=[invitation['seq']],relationships={'canon_briney':dict(stance='respectful',motivation='Only an invitation exists.',evidence=[invitation['seq']])})
  with self.assertRaises(ValueError):cast.compile_actions([fake],self.author.context())
  fake=self.author.action(1);fake['id']='canon_steven'
  fake['changes']['cooperate']=dict(owner='canon_briney',intention='resting_court',signature=invitation['signature'],decision='join')
  with self.assertRaisesRegex(ValueError,'invitation evidence'):cast.compile_actions([fake],self.author.context())
