"""Shared research to actual canonical character decision, with a test author."""
import json, tempfile, time, unittest
import test_canonical_cast as fixture
from world import character_reactions as reactions, shared_research as research
from world.runtime_gm import IntentQueue

class BirchReactionTests(unittest.TestCase):
 def test_research_prompts_character_and_changes_dialogue(self):
  f=fixture.CanonicalCastTests(); f.setUp(); self.addCleanup(f.doCleanups)
  action=f.action(); action['id']='canon_birch'; f.apply(action)
  c=f.peer(); c['presence']=dict(campaign_run='a'*32,state=[1,4,5,5,0,0,1],state_time=time.monotonic())
  # In a real connection the protocol's busy check is also present.
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,f.s.inspect(),'canon_birch','Consider voluntarily shared research.')
    self.assertEqual(reactions.observe(q,f.s.inspect(),f.fetch),[])
    self.assertEqual(research.handle(f.s,c,b'D REPORT 1 3'),'D ACK 1\n')
    self.assertEqual(len(reactions.observe(q,f.s.inspect(),f.fetch)),1)
    item=q.claim(); packet=json.loads(item['result']); ctx=f.context()
    ctx['runtime'].update(kind='character',observed_event=packet)
    reaction=reactions.prepare(ctx,f.fetch)
    event=packet['evidence']
    a=f.action(1,'Someone shared a new research report. I will consider what it means.')
    a['id']='canon_birch';a['changes']['evidence']=[event]
    reactions.check_response(dict(canonical_actions=[a],tests='assert True'),reaction)
    f.apply(a)
    self.assertIn('new research report',f.s.module_state['canonical_cast']['canon_birch']['dialogue'])
   finally:q.close()
