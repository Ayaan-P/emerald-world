import json
import unittest
import test_cast_agent_ui as fixture
from world import character_reactions as reactions
from world import actor_runtime as runtime
from world.gm import _prompt

class WorldGoalTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.AgentUITests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def submit(self,**changes):
  fields=dict(actor='canon_rydel',goal='Build a small connected outdoor meeting place.',request_id='goal-test-123',confirmed=True);fields.update(changes)
  return self.f.call('goal',**fields)
 def exercise(self,provider):
  info=self.submit();self.assertEqual(info['queued'],1);self.assertEqual(info['goals'][0]['status'],'queued');self.f.session.start_gm.assert_not_called()
  self.submit();q=self.f.session._gm_queue();self.addCleanup(q.close)
  self.assertEqual(len(q.status()['requests']),1)
  item=q.claim();context=self.f.f.context();context['runtime']=dict(kind=item['kind'],observed_event=json.loads(item['result']))
  reaction=reactions.prepare(context,self.f.f.fetch)
  self.assertTrue(reaction['host_goal']);self.assertIn('world.create_place',context['actor_runtime']['capabilities'])
  self.assertIn('host_world_goal',_prompt(item['text'],context));self.assertEqual(context['players'],[])
  # Fake author chooses a supported real action. No API or invented model behavior.
  action=self.f.f.action(1);action['changes']['plan']=dict(id='host_build',purpose='Create a real place.',steps=[dict(id='create',tool='world.create_place',args=dict(label='New Place',blueprint=json.dumps(dict(rooms=[[3,3,6,6],[19,19,7,7]],links=[[0,1]],entrance_room=0,exit_room=1))),after=[])])
  action['changes']['evidence']=[reaction['evidence']]
  from world.author_backends import request
  from test_author_backends import openai,anthropic
  wrap=anthropic if provider=='anthropic-messages' else openai
  response=request('explicit-model',_prompt(item['text'],context),30,provider=provider,transport=lambda payload,timeout:wrap(dict(canonical_actions=[action],tests='def test_safe(): assert True')))
  reactions.check_response(response,reaction)
  self.f.f.apply(response['canonical_actions'][0]);q.finish(item['id'],'succeeded',dict(ok=True))
  result=runtime.tick(self.s,now=10);self.assertEqual(result['status'],'succeeded')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_region_revisions').fetchone()[0],1)
  ids=reactions.observe(q,self.s.inspect(),self.f.f.fetch);self.assertEqual(len(ids),1)
  follow=q.claim();self.assertEqual(follow['kind'],'character')
  self.assertEqual(json.loads(follow['result'])['evidence'],result['seq'])
  next_context=self.f.f.context();next_context['runtime']=dict(kind='character',observed_event=json.loads(follow['result']))
  next_reaction=reactions.prepare(next_context,self.f.f.fetch)
  done=self.f.f.action(2);done['changes'].update(plan=None,evidence=[result['seq']])
  reply=request('explicit-model',_prompt(follow['text'],next_context),30,provider=provider,transport=lambda payload,timeout:wrap(dict(canonical_actions=[done],tests='def test_safe(): assert True')))
  reactions.check_response(reply,next_reaction);self.f.f.apply(reply['canonical_actions'][0]);q.finish(follow['id'],'succeeded',dict(ok=True))
  self.assertIsNone(runtime.tick(self.s,now=30))

 def test_claude_goal_plan_actual_result_and_replan(self):self.exercise('anthropic-messages')
 def test_openai_goal_plan_actual_result_and_replan(self):self.exercise('openai-responses')
 def test_unconfirmed_stale_identity_and_restart_do_not_duplicate(self):
  from world.session import SessionError
  with self.assertRaises(SessionError):self.submit(confirmed=False)
  self.submit()
  with self.assertRaises(SessionError):self.submit(goal='Different request under same id')
  with self.assertRaises(SessionError):self.submit(request_id='another-goal-123')
  q=self.f.session._gm_queue();self.assertEqual(len(q.status()['requests']),1);q.close()
  self.submit();q=self.f.session._gm_queue();self.addCleanup(q.close);self.assertEqual(len(q.status()['requests']),1)
  self.f.call('unfollow',actor='canon_rydel');self.assertEqual(q.status()['requests'][0]['status'],'interrupted')
