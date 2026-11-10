"""Production worker/GM/staging loop; only API and local socket transport are fake."""
import json,time,unittest
from unittest.mock import patch
from world import gm,author_backends,actor_runtime,character_reactions
from world.runtime_gm import RuntimeGM
import test_character_reactions as fixture
from test_author_backends import openai,anthropic

class AuthorLoopTests(unittest.TestCase):
 def admin(self,s,request):
  conn=dict(out=bytearray(),closing=False,sock=object(),id=None,admin=True)
  s.connections[conn['sock']]=conn
  try:
   s._admin_line(conn,json.dumps(request).encode())
   until=time.monotonic()+15
   while not conn['out'] and time.monotonic()<until:
    s._poll_mechanics();time.sleep(.01)
   if not conn['out']:raise AssertionError('Admin response timeout')
   return json.loads(conn['out'])
  finally:s.connections.pop(conn['sock'],None)
 def test_both_providers_worker_plan_real_effect_source_recovery_and_replan(self):
  for provider,wrap in [('openai-responses',openai),('anthropic-messages',anthropic)]:
   with self.subTest(provider=provider):
    f=fixture.ReactionTests();f.setUp();s=f.server
    try:
     with RuntimeGM(s.runtime.root,'unused',model='explicit-model',provider=provider,min_author_interval=0) as worker:
      character_reactions.configure(worker.queue,s.inspect(),'field_researcher','Choose your own supported plans from real results.')
      f.finish_trip();prompts=[]
      def transport(payload,timeout):
       prompt=payload['input'] if provider=='openai-responses' else payload['messages'][0]['content'];prompts.append(prompt)
       context=json.loads(prompt.split('Inspected context (data):\n',1)[1]);reaction=context['character_reaction'];data=context.get('data',context)
       self.assertIn('world.populate',data['actor_runtime']['capabilities'])
       self.assertIn('conditional_steps',data['actor_runtime'])
       if len(prompts)==1:
        blueprint=json.dumps(dict(rooms=[[3,3,6,6],[19,19,7,7]],links=[[0,1]],entrance_room=0,exit_room=1),separators=(',',':'))
        definition=json.dumps(dict(id='chosen_prop',kind='prop',x=5,y=5,gfx=0,text='A field marker.',portable=True),separators=(',',':'))
        plan=dict(id='make_place',purpose='Create a usable marked place.',steps=[dict(id='create',tool='world.create_place',args=dict(label='Field Hollow',blueprint=blueprint),after=[]),dict(id='populate',tool='world.populate',args=dict(revision=dict(result='create',key='revision'),definition=definition),after=['create'],when=dict(step='create',path='/outcome',equals='region_opened'))])
       else:
        self.assertIn('_population_',context['runtime']['previous_source'])
        self.assertTrue(any(o['id']=='chosen_prop' for o in data['objects']))
        self.assertTrue(any(p['receipts'] for p in data['actor_runtime']['plans']))
        plan=None # Real result causes this fixture author to choose to stop.
       action=dict(id='field_researcher',expected_version=reaction['expected_version'],evidence=[reaction['evidence']],reason='Choose from actual public evidence.',changes=dict(plan=plan),object=next(o for o in data['objects'] if o['id']=='field_researcher'))
       tests='def test_update():\n    result=update({"players":[],"tick":0,"revision":0,"interactions":[]},{})\n    assert "world_characters" in result["state"]\n'
       return wrap(dict(character_actions=[action],tests=tests))
      def author(argv,prompt,timeout,*rest):
       return author_backends.request('explicit-model',prompt,timeout,provider=provider,transport=transport)
      with patch.object(gm,'admin_request',side_effect=lambda path,req,timeout=5:self.admin(s,req)),patch.object(gm,'_run_author',side_effect=author):
       first=worker.step()
       if 'Failed to create NETLINK_ROUTE socket' in first.get('result',{}).get('error',''):
        self.skipTest('Environment cannot start the required mechanic sandbox; no isolation bypass')
       self.assertEqual(first['status'],'succeeded',first)
       self.assertEqual(actor_runtime.tick(s,now=10)['status'],'succeeded')
       self.assertEqual(actor_runtime.tick(s,now=16)['status'],'pending')
       until=time.monotonic()+15
       while (s.deployment is not None or s.job is not None) and time.monotonic()<until:
        s._poll_mechanics();time.sleep(.01)
       self.assertIsNone(s.module_error)
       self.assertEqual(actor_runtime.tick(s,now=22)['status'],'succeeded')
       source_hash=s.candidate.sha256
       self.assertNotEqual(source_hash,first['result']['source_sha256'])
       second=worker.step();self.assertEqual(second['status'],'succeeded',second)
       self.assertIsNone(s.module_state['world_characters']['field_researcher'].get('plan'))
       self.assertTrue(any(o['id']=='chosen_prop' for o in s.objects));self.assertEqual(len(prompts),2)
    finally:f.doCleanups()
 def test_source_endpoint_refuses_stale_hash(self):
  f=fixture.ReactionTests();f.setUp()
  try:
   self.assertFalse(self.admin(f.server,dict(command='mechanic_source',expected_hash='0'*64))['ok'])
   result=self.admin(f.server,dict(command='mechanic_source',expected_hash=f.server.candidate.sha256))
   self.assertTrue(result['ok']);self.assertEqual(result['source'],f.server.candidate.source)
  finally:f.doCleanups()

 def test_actual_capability_source_is_recovered_without_author_cache(self):
  import test_actor_population as population
  f=population.PopulationTests();f.setUp()
  try:
   f.plan();actor_runtime.tick(f.s,now=10);actor_runtime.tick(f.s,now=16);f.admit();actor_runtime.tick(f.s,now=22)
   with RuntimeGM(f.s.runtime.root,'unused',model='explicit-model',provider='anthropic-messages',min_author_interval=0) as worker:
    with patch.object(gm,'admin_request',side_effect=lambda path,req,timeout=5:self.admin(f.s,req)):
     source=worker._previous_source(f.s.inspect())
     self.assertEqual(source,f.s.candidate.source);self.assertIn('_population_',source)
    with patch.object(gm,'admin_request',return_value=dict(ok=True,sha256=f.s.candidate.sha256,source='wrong')):
     with self.assertRaises(ValueError):worker._previous_source(f.s.inspect())
  finally:f.doCleanups()
