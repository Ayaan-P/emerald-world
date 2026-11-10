"""Real canonical/generated plans and receipt-backed independent work."""
from copy import deepcopy
import json,tempfile,unittest
import test_canonical_cast as fixture
from world import actor_runtime as runtime,actor_cooperation as work,canonical_cast,character_reactions
from world.build_catalog import catalog_maps
from world.runtime_gm import IntentQueue

class CastWorldWorkTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.now=0
  self.f.apply(self.f.action())
  self.obj=dict(id='researcher',group=0,num=9,x=9,y=8,gfx=8,text='I decide my own research.')
  self.c=dict(version=1,name='Researcher',role='Independent field researcher',goals=['Consider the habitats'],relationships={},team=[dict(species=278,level=18)],status='active',object_id='researcher',evidence=[],reason='New original researcher')
  state=deepcopy(self.s.module_state);state['world_characters']={'researcher':self.c};self.commit(state)
 def commit(self,state):
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr([self.obj])+')\n'
  self.f.commit(source,dict(state=state,tiles=[],objects=[self.obj]))
 def act(self,actor,tool,args):
  rows=runtime.actor_records(self.s);version=rows[actor]['version']
  plan=dict(id='decision_'+str(version+1),purpose='Choose independent work from public facts.',steps=[dict(id='act',tool=tool,args=args,after=[])])
  if actor.startswith('canon_'):
   action=self.f.action(version=version);action['id']=actor;action['changes']['plan']=plan;self.f.apply(action)
  else:
   state=deepcopy(self.s.module_state);state['world_characters'][actor].update(version=version+1,plan=plan);self.commit(state)
  self.now+=10;return runtime.tick(self.s,now=self.now)
 def offer(self,target='researcher',tool='world.configure_outbreak'):
  result=self.act('canon_rydel','actor.request_work',dict(target=target,purpose='Consider a supported local habitat opportunity.',tool=tool,where=json.dumps(dict(outcome='shared_outbreak_configured'))))
  return result
 def test_original_actor_requests_independent_work_actual_outcome_and_restart(self):
  self.assertEqual(self.offer()['status'],'succeeded');request=work.discover(self.s)[0]
  self.assertEqual(request['terms']['channel'],'public_correspondence_not_physical_meeting')
  self.assertNotIn('plan',runtime.actor_records(self.s)['researcher'])
  with tempfile.TemporaryDirectory() as d:
   q=IntentQueue(d)
   try:
    character_reactions.configure(q,self.s.inspect(),'canon_rydel','Choose what actual work means for your goals.')
    self.assertEqual(self.act('researcher','world.respond_cooperation',dict(request=request['id'],decision='accept'))['status'],'succeeded')
    self.assertEqual(self.act('researcher','world.configure_outbreak',dict(map='Route102',species='RALTS',level=12,chance=35,minutes=10))['status'],'succeeded')
    seq=self.s.db.execute("SELECT max(seq) FROM actor_tool_receipts WHERE actor='researcher' AND status='succeeded'").fetchone()[0]
    self.assertEqual(self.act('researcher','world.deliver_cooperation',dict(request=request['id'],receipt=seq))['status'],'succeeded')
    events=self.s.memory.history()['events'];event=next(e for e in events if e['event']=='character_cooperation_delivered')
    self.assertTrue(canonical_cast.reaction_activity(event,'canon_rydel',{}))
    self.assertTrue(character_reactions.observe(q,self.s.inspect(),self.f.fetch))
    response=self.f.action(version=runtime.actor_records(self.s)['canon_rydel']['version'],text='The habitat opportunity was posted. I will consider the next route.')
    response['changes'].update(evidence=[event['seq']],plan=None)
    self.f.apply(response)
    self.assertIn('habitat opportunity',runtime.actor_records(self.s)['canon_rydel']['dialogue'])
   finally:q.close()
  peer=self.f.peer();pair=next(p for p,m in catalog_maps().items() if m['name']=='Route102');peer['state'][:2]=pair;peer['outbreak_capable']=True
  from world.shared_outbreaks import line
  self.assertIsNotNone(line(self.s,peer))
  self.assertEqual(self.s.module_state['world_characters']['researcher']['team'],self.c['team'])
  self.assertEqual(self.s.db.execute('SELECT status FROM actor_cooperation').fetchone()[0],'delivered')
  self.s.close();case=self.f.f.case;case.server=case.open();self.s=case.server;self.f.s=self.s;self.f.f.server=self.s
  self.assertEqual(work.discover(self.s),[])
  self.assertEqual(self.s.db.execute('SELECT status FROM actor_cooperation').fetchone()[0],'delivered')
  self.assertIsNone(runtime.tick(self.s,now=1000))
 def test_no_forced_acceptance_or_physical_meeting(self):
  self.assertEqual(self.offer()['status'],'succeeded');key=work.discover(self.s)[0]['id']
  self.assertEqual(self.act('canon_rydel','world.respond_cooperation',dict(request=key,decision='accept'))['status'],'blocked')
  self.assertEqual(self.act('researcher','world.respond_cooperation',dict(request=key,decision='decline'))['status'],'succeeded')
  self.assertEqual(work.discover(self.s),[])
  self.assertEqual(self.act('researcher','world.request_cooperation',dict(target='canon_rydel',purpose='Meet',tool='world.create_place',where='{"outcome":"created"}'))['status'],'blocked')
 def test_unavailable_capability_and_recursive_requests_rejected(self):
  self.assertEqual(self.offer('canon_rydel')['status'],'blocked')
  self.assertEqual(self.offer(tool='actor.request_work')['status'],'blocked')
  self.assertEqual(self.offer(tool='world.act')['status'],'blocked')

 def test_canonical_recipient_independent_choice(self):
  action=self.f.action();action['id']='canon_steven';self.f.apply(action)
  result=self.act('researcher','actor.request_work',dict(target='canon_steven',purpose='Consider opening a research destination.',tool='world.create_place',where='{"outcome":"place_created"}'))
  self.assertEqual(result['status'],'succeeded');key=work.discover(self.s)[0]['id']
  self.assertNotIn('plan',runtime.actor_records(self.s)['canon_steven'])
  self.assertEqual(self.act('canon_steven','world.respond_cooperation',dict(request=key,decision='decline'))['status'],'succeeded')
  self.assertEqual(work.discover(self.s),[])
