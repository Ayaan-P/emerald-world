"""Actual arrival adjacency delivers a message; recipient independently responds."""
from copy import deepcopy
import hashlib,json,tempfile,unittest
import test_region_characters as region_fixture
import test_character_journeys as journey_fixture
from world.character_actions import compile_actions,action_step,validate_actions
from world.mechanics import Candidate
from world import character_reactions as reactions
from world.runtime_gm import IntentQueue

class EncounterTests(unittest.TestCase):
 tick=journey_fixture.JourneyTests.tick
 def setUp(self):
  self.f=region_fixture.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.server;self.revision=self.f.enable_shared_xl();self.peer=self.f.connect_shared_xl(walking=True)
  state=deepcopy(self.s.module_state)
  target=deepcopy(state['world_characters']['harbor_guide'])
  target.update(version=1,name='Hill Keeper',object_id='hill_keeper',offer=None)
  target.pop('offer')
  state['world_characters']['hill_keeper']=target
  self.target=dict(self.f.obj,id='hill_keeper',x=88,y=73,text='I am studying this hillside.')
  self.f.commit(dict(state=state,tiles=[],objects=self.s.objects+[self.target]));self.assertIsNone(self.s.module_error)
  self.path=[[x,70] for x in range(71,89)]+[[88,71],[88,72]]
  self.action=dict(id='harbor_guide',expected_version=2,evidence=[self.s.memory.history()['events'][-1]['seq']],
      reason='Visit the hill keeper to compare priorities',changes={},object=dict(self.f.obj,x=88,y=72,text='What should we study next?'),
      journey=self.path,meet=dict(target='hill_keeper',expected_version=1,text='What should we study next?'))
  ctx=self.s.inspect();ctx['runtime']=dict(previous_source=self.f.candidate.source)
  source=compile_actions([self.action],ctx);self.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.definition=hashlib.sha256(json.dumps([self.action],sort_keys=True).encode()).hexdigest();self.snapshots=[]
  self.tick(0)
 def fetch(self,query):
  return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
 def encounters(self):return [e for e in self.s.memory.history()['events'] if e['event']=='character_encounter']
 def test_arrival_message_triggers_recipient_choice_not_forced_response(self):
  before=deepcopy(self.s.module_state['world_characters']['hill_keeper'])
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'hill_keeper','Respond to an actual visitor according to your own goals.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
    for n in range(1,30):self.tick(n)
    event=self.encounters()[-1]
    self.assertEqual(event['outcome'],'public_message_delivered')
    self.assertEqual(event['recipient'],'hill_keeper');self.assertEqual(event['text'],'What should we study next?')
    self.assertEqual(self.s.module_state['world_characters']['hill_keeper'],before) # Delivery does not force a reply/feeling.
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
    item=q.claim();ctx=self.s.inspect();ctx['runtime']=dict(previous_source=self.candidate.source,kind='character',observed_event=json.loads(item['result']))
    reaction=reactions.prepare(ctx,self.fetch)
    response=dict(id='hill_keeper',expected_version=1,evidence=[event['seq']],reason='Consider the actual visitor question',
       changes=dict(goals=['Compare the nearby routes before choosing further work']),object=dict(self.target,text='Let us compare these routes.'))
    reactions.check_response(dict(character_actions=[response],tests='assert True'),reaction)
    source=compile_actions([response],ctx);definition=hashlib.sha256(json.dumps([response],sort_keys=True).encode()).hexdigest()
    self.action=response;self.definition=definition;self.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
    self.tick(31)
    self.assertEqual(next(o for o in self.s.objects if o['id']=='hill_keeper')['text'],'Let us compare these routes.')
    self.assertEqual(len(self.encounters()),1)
    self.assertEqual(self.s.module_state['world_characters']['hill_keeper']['relationships'],{})
   finally:q.close()
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server
  self.assertEqual(len(self.encounters()),1)
  self.assertEqual(next(o for o in self.s.objects if o['id']=='hill_keeper')['text'],'Let us compare these routes.')
 def test_changed_target_records_miss_without_delivering_message(self):
  state=deepcopy(self.s.module_state);state['world_characters']['hill_keeper']['version']=2
  self.f.commit(dict(state=state,tiles=[],objects=[dict(o,x=90) if o['id']=='hill_keeper' else o for o in self.s.objects]))
  self.assertIsNone(self.s.module_error)
  for n in range(1,30):self.tick(n)
  event=self.encounters()[-1]
  self.assertEqual(event['outcome'],'missed');self.assertEqual(event['reason'],'target_changed')
  self.assertNotIn('text',event)
  self.assertFalse(reactions.dynamic_result(event,'hill_keeper',state['world_characters']['hill_keeper']))
  self.assertTrue(reactions.dynamic_result(event,'harbor_guide',state['world_characters']['harbor_guide']))
 def test_wrong_scope_or_unbound_message_cannot_be_authored(self):
  # Current traveler version advanced; inspect a fresh action from current location.
  bad=deepcopy(self.action);bad['expected_version']=3
  for modify in ('message','target','endpoint'):
   action=deepcopy(bad)
   if modify=='message':action['meet']['text']='A different message.'
   if modify=='target':action['meet']['target']='canon_steven'
   if modify=='endpoint':action['object']['y']=71;action['journey']=action['journey'][:-1]
   with self.assertRaises(ValueError):validate_actions([action],self.s.inspect())
