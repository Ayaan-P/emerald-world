import copy,json,unittest
import test_actor_navigation as fixture
from world import actor_methods as methods,actor_runtime as runtime

class MethodTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def apply(self,p,actor='harbor_guide'):
  from world.character_actions import compile_actions
  from world.mechanics import Candidate
  import hashlib
  c=self.s.module_state['world_characters'][actor];obj=next(o for o in self.s.objects if o['id']==actor)
  action=dict(id=actor,expected_version=c['version'],evidence=c['evidence'],reason='Choose my next real action.',changes=dict(plan=p),object=obj)
  context=self.s.inspect();context['runtime']=dict(previous_source=self.f.f.candidate.source)
  context['recalled_history']=dict(events=[dict(json.loads(self.s.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone()[0]),seq=seq) for seq in c['evidence']])
  source=compile_actions([action],context);self.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  ns={};exec(source,ns);self.f.f.commit(ns['update'](self.s._context(),copy.deepcopy(self.s.module_state)));self.assertIsNone(self.s.module_error)
 def source(self,actor='harbor_guide',x=78,y=70):
  p=dict(id='learn_route',purpose='Observe actual surroundings, travel, and inspect the arrival.',steps=[
   dict(id='see',tool='world.observe',args=dict(radius=2),after=[]),
   dict(id='go',tool='world.navigate',args=dict(revision={'result':'see','key':'revision'},x=x,y=y),after=['see']),
   dict(id='arrive',tool='world.observe',args=dict(radius=2),after=['see','go'])])
  self.apply(p,actor);self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending')
  self.f.advance(0,True)
  for n in range(1,30):self.f.advance(n)
  self.assertEqual(runtime.tick(self.s,now=40)['status'],'succeeded');self.assertEqual(runtime.tick(self.s,now=46)['status'],'succeeded')
  return p
 def retain(self,actor='harbor_guide'):
  args=dict(name='explore',plan='learn_route',parameters=json.dumps(dict(x=dict(step='go',argument='x'),y=dict(step='go',argument='y'))))
  self.apply(dict(id='retain',purpose='Retain experience.',steps=[dict(id='save',tool='world.remember_method',args=args,after=[])]),actor)
  self.assertEqual(runtime.tick(self.s,now=52)['status'],'succeeded')
  return json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE actor=? AND plan='retain'",(actor,)).fetchone()[0])
 def invoke(self,digest,x=80,y=72):
  return dict(id='reuse',purpose='Apply my practiced approach at a different destination.',steps=[dict(id='method',tool='world.perform_method',args=dict(method='explore',digest=digest,bindings=json.dumps(dict(x=x,y=y))),after=[])])
 def test_real_movement_new_destination_restart_and_no_replay(self):
  self.source();record=self.retain();self.apply(self.invoke(record['digest']))
  self.assertEqual(runtime.tick(self.s,now=60)['step'],'see');self.assertEqual(runtime.tick(self.s,now=66)['status'],'pending');self.f.advance(30,True)
  self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server;self.f.s=self.s;self.f.f.server=self.s;self.f.f.candidate=self.s.candidate
  for n in range(31,60):self.f.advance(n)
  self.assertEqual(runtime.tick(self.s,now=90)['step'],'go');self.assertEqual(runtime.tick(self.s,now=96)['step'],'arrive')
  r=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE plan='reuse' AND step='arrive'").fetchone()[0]);self.assertEqual((r['x'],r['y']),(80,72))
  self.assertIsNone(runtime.tick(self.s,now=102));self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_journey_receipts').fetchone()[0],2)
  self.assertIn('explore',' '.join(methods.command(self.s,None,['harbor_guide'])))
 def test_unseen_blocked_destination_is_failure_not_learned_success(self):
  self.source();r=self.retain();self.apply(self.invoke(r['digest'],0,0));runtime.tick(self.s,now=60)
  self.assertEqual(runtime.tick(self.s,now=66)['status'],'blocked');self.assertIsNone(runtime.tick(self.s,now=72))
  with self.assertRaises(ValueError):methods.remember(self.s,'harbor_guide',{},dict(name='failed',plan='reuse',parameters='{}'))
 def test_no_cross_actor_adoption_or_stale_digest_or_nested_invocation(self):
  self.source();r=self.retain();p=self.invoke(r['digest'])
  with self.assertRaises(ValueError):methods.expand(self.s,'second',p)
  p['steps'][0]['args']['digest']='0'*64
  with self.assertRaises(ValueError):methods.expand(self.s,'harbor_guide',p)
  p=self.invoke(r['digest']);p['steps'].append(dict(id='extra',tool='world.observe',args=dict(radius=1),after=['method']))
  with self.assertRaises(ValueError):methods.expand(self.s,'harbor_guide',p)
 def test_requires_actual_full_receipts_fresh_revision_refs_and_typed_bindings(self):
  p=self.source();r=self.retain()
  self.s.db.execute("UPDATE actor_tool_receipts SET result=? WHERE plan='learn_route' AND step='go'",(json.dumps(dict(outcome='reconstruction_conflict')),))
  with self.assertRaises(ValueError):methods.remember(self.s,'harbor_guide',{},dict(name='fake',plan='learn_route',parameters='{}'))
  p=self.invoke(r['digest']);p['steps'][0]['args']['bindings']='{"x":true,"y":72}'
  with self.assertRaises(ValueError):methods.expand(self.s,'harbor_guide',p)
 def test_cannot_retain_hardcoded_revision_or_parameterize_capability_guard(self):
  self.source()
  with self.assertRaises(ValueError):methods.remember(self.s,'harbor_guide',{},dict(name='guard',plan='learn_route',parameters=json.dumps(dict(revision=dict(step='go',argument='revision')))))
  raw=self.s.db.execute("SELECT definition FROM actor_plans WHERE plan='learn_route'").fetchone()[0];p=json.loads(raw)
  p['steps'][1]['args']['revision']=self.f.revision
  self.s.db.execute("UPDATE actor_plans SET definition=? WHERE plan='learn_route'",(json.dumps(p),))
  with self.assertRaises(ValueError):methods.remember(self.s,'harbor_guide',{},dict(name='stale',plan='learn_route',parameters='{}'))
 def test_invalid_invocation_blocks_once_and_cannot_replace_frozen_bindings(self):
  self.source();r=self.retain();p=self.invoke(r['digest']);self.apply(p)
  runtime.tick(self.s,now=60)
  changed=copy.deepcopy(p);changed['steps'][0]['args']['bindings']='{"x":81,"y":73}'
  with self.assertRaises(ValueError):methods.expand(self.s,'harbor_guide',changed)
  bad=self.invoke('0'*64);bad['id']='bad_method';self.apply(bad)
  self.assertEqual(runtime.tick(self.s,now=66)['status'],'blocked');self.assertIsNone(runtime.tick(self.s,now=72))
 def test_second_actor_learns_independently_and_fake_providers_see_discovery(self):
  self.source('second',77,72);r=self.retain('second');p=self.invoke(r['digest'],79,73);self.apply(p,'second')
  self.assertEqual(runtime.tick(self.s,now=60)['status'],'succeeded');self.assertEqual(runtime.tick(self.s,now=66)['status'],'pending')
  from world import author_backends
  from test_author_backends import openai,anthropic
  prompt=json.dumps(self.s.inspect()['actor_runtime']);self.assertIn('explore',prompt)
  for provider,wrap in [('openai-responses',openai),('anthropic-messages',anthropic)]:
   def transport(payload,timeout):return wrap(dict(character_actions=[dict(id='second',changes=dict(plan=p))],tests=''))
   result=author_backends.request('fake-model',prompt,30,provider=provider,transport=transport)
   runtime.validate(result['character_actions'][0]['changes']['plan'])
 def test_cancel_pending_method_uses_expanded_step_and_never_claims_arrival(self):
  self.source();r=self.retain();self.apply(self.invoke(r['digest']));runtime.tick(self.s,now=60);runtime.tick(self.s,now=66)
  self.s.deployment=None;self.apply(None)
  self.assertEqual(runtime.tick(self.s,now=72)['status'],'blocked');self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_journey_receipts').fetchone()[0],1)

if __name__=='__main__':unittest.main()

class ObjectMethodTests(unittest.TestCase):
 def test_method_rebinds_a_different_real_advertised_object_with_fresh_revision(self):
  import test_actor_objects
  from world.mechanics import Candidate
  import hashlib
  f=test_actor_objects.ObjectTests();f.setUp();self.addCleanup(f.doCleanups);s=f.s
  objects=copy.deepcopy(s.objects)+[dict(s.objects[-1],id='other',x=71,y=71,text='Other.')]
  state=copy.deepcopy(s.module_state);state['world_object_actions']['other']={'move':'Change this object.'}
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects)+')\n'
  source+="def actor_interact(object_id,action,state):\n assert action=='move'\n x,y=(72,70) if object_id=='fixture' else (71,71)\n return dict(state={'uses':state.get('uses',0)+1},x=x,y=y,gfx=1,text='Activated.')\n"
  f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());f.f.f.commit(dict(state=state,tiles=[],objects=objects))
  def apply(p):
   state=copy.deepcopy(s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1;c['plan']=p
   f.f.f.commit(dict(state=state,tiles=[],objects=s.objects));self.assertIsNone(s.module_error)
  p=dict(id='learn_object',purpose='Inspect and use an actual advertised action.',steps=[
   dict(id='see',tool='world.observe',args=dict(radius=1),after=[]),
   dict(id='go',tool='world.navigate',args=dict(revision={'result':'see','key':'revision'},x=72,y=69),after=['see']),
   dict(id='target',tool='world.inspect_object',args=dict(object='fixture'),after=['see','go']),
   dict(id='act',tool='world.use_object',args=dict(object={'result':'target','key':'object'},object_revision={'result':'target','key':'object_revision'},action='move'),after=['see','go','target'])])
  apply(p);runtime.tick(s,now=10);self.assertEqual(runtime.tick(s,now=16)['status'],'pending');f.f.advance(0,True)
  for n in range(1,25):f.f.advance(n)
  self.assertEqual(runtime.tick(s,now=40)['status'],'succeeded');runtime.tick(s,now=46)
  self.assertEqual(runtime.tick(s,now=52)['status'],'pending');f.f.advance(25,True);self.assertEqual(runtime.tick(s,now=58)['status'],'succeeded')
  with s.db:r=methods.remember(s,'harbor_guide',{},dict(name='activate',plan='learn_object',parameters=json.dumps(dict(target=dict(step='target',argument='object'),x=dict(step='go',argument='x'),y=dict(step='go',argument='y')))))
  invocation=dict(id='different_object',purpose='Use my method with a different nearby object.',steps=[dict(id='method',tool='world.perform_method',args=dict(method='activate',digest=r['digest'],bindings='{"target":"other","x":70,"y":71}'),after=[])])
  # Normal action compiler removes completed movement metadata when changing plans.
  from world.character_actions import compile_actions
  c=s.module_state['world_characters']['harbor_guide'];obj=next(o for o in s.objects if o['id']=='harbor_guide')
  action=dict(id='harbor_guide',expected_version=c['version'],evidence=c['evidence'],reason='Try the same method on another object.',changes=dict(plan=invocation),object=obj)
  context=s.inspect();context['runtime']=dict(previous_source=f.f.f.candidate.source)
  context['recalled_history']=dict(events=[dict(json.loads(s.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone()[0]),seq=seq) for seq in c['evidence']])
  source=compile_actions([action],context);f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());f.f.advance(26)
  runtime.tick(s,now=64);self.assertEqual(runtime.tick(s,now=70)['status'],'pending');f.f.advance(27,True)
  for n in range(28,55):f.f.advance(n)
  self.assertEqual(runtime.tick(s,now=100)['status'],'succeeded');runtime.tick(s,now=106)
  self.assertEqual(runtime.tick(s,now=112)['status'],'pending');f.f.advance(55,True);self.assertEqual(runtime.tick(s,now=118)['status'],'succeeded')
  self.assertEqual(s.module_state['world_object_controls']['other']['state']['uses'],1)
  self.assertEqual(next(o for o in s.objects if o['id']=='other')['text'],'Activated.')
  self.assertIsNone(runtime.tick(s,now=124))
