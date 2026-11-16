from copy import deepcopy
import json,tempfile
from unittest.mock import patch
from test_actor_knowledge import KnowledgeTests
from world import actor_runtime as runtime,character_reactions as reactions
from world.actor_knowledge import recall,inbox
from world.knowledge_relays import relay,flush
from world.runtime_gm import IntentQueue

class RelayTests(KnowledgeTests):
 def third(self):
  state=deepcopy(self.s.module_state);third=deepcopy(state['world_characters']['second']);third.update(name='Third Researcher',object_id='third',version=1);third.pop('plan',None)
  state['world_characters']['third']=third
  second=next(o for o in self.s.objects if o['id']=='second');obj=dict(second,id='third',x=75,y=70)
  self.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects+[obj]));self.assertIsNone(self.s.module_error)
 def test_real_relay_independent_reaction_restart_and_loop_prevention(self):
  delivery=self.deliver();self.third()
  with tempfile.TemporaryDirectory() as td:
   q=IntentQueue(td);self.addCleanup(q.close);reactions.configure(q,self.s.inspect(),'third','Decide whether to investigate actual reports.')
   self.plan('second',[dict(id='relay',tool='world.relay_report',args=dict(target='third',expected_version=1,delivery=delivery),after=[])])
   self.assertEqual(runtime.tick(self.s,now=42)['status'],'succeeded')
   self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
   result=inbox(self.s)['third'][0];report=recall(self.s,'third',{},dict(delivery=result['delivered']))
   original=recall(self.s,'second',{},dict(delivery=delivery))
   self.assertEqual(report['snapshot'],original['snapshot']);self.assertEqual(report['sender'],'second')
   self.assertEqual(report['provenance']['observer'],'harbor_guide');self.assertEqual(report['provenance']['hops'],2)
   self.assertEqual(report['provenance']['previous_delivery'],delivery)
   with self.s.db:
    old=relay(self.s,'third',{},dict(target='second',expected_version=2,delivery=result['delivered']))
   self.assertEqual(old['outcome'],'report_already_known');self.assertEqual(len(inbox(self.s)['second']),1)
   self.s.close();self.f.f.f.f.server=self.f.f.f.f.open();self.s=self.f.f.f.f.server
   self.assertEqual(recall(self.s,'third',{},dict(delivery=result['delivered'])),report)
 def test_wrong_recipient_remote_and_rollback(self):
  delivery=self.deliver();self.third()
  with self.assertRaisesRegex(ValueError,'did not receive'):relay(self.s,'third',{},dict(target='second',expected_version=1,delivery=delivery))
  with self.assertRaisesRegex(ValueError,'adjacent'):relay(self.s,'harbor_guide',{},dict(target='third',expected_version=1,delivery=delivery))
  with self.assertRaisesRegex(ValueError,'rollback'):
   with self.s.db:
    relay(self.s,'second',{},dict(target='third',expected_version=1,delivery=delivery));raise ValueError('rollback')
  self.assertFalse(inbox(self.s)['third']);self.assertEqual(self.s.db.execute('SELECT count(*) FROM actor_knowledge_notices').fetchone()[0],0)
 def test_post_commit_nearby_notice_not_replayed(self):
  delivery=self.deliver();self.third()
  with self.s.db:relay(self.s,'second',{},dict(target='third',expected_version=1,delivery=delivery))
  with patch('world.spatial_speech.player_near',return_value=True),patch.object(self.s.guild_chat,'message') as send:
   flush(self.s);self.assertTrue(send.called)
   self.assertIn('second passes a dated report to third.',str(send.call_args))
   n=send.call_count;flush(self.s);self.assertEqual(send.call_count,n)
