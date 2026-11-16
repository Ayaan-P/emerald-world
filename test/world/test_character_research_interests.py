"""Interest-driven original characters react only to public, opt-in reports."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib,json,time,unittest
from world import character_reactions as reactions, shared_research as research
from world.character_actions import compile_actions
from world.mechanics import Candidate
from test_character_reactions import ReactionTests

class ResearchInterestTests(unittest.TestCase):
 def setUp(self):
  self.f=ReactionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.server
 def apply(self,action,context):
  source=compile_actions([action],context);ns={};exec(source,ns)
  result=ns['update'](self.s._context(),deepcopy(self.s.module_state))
  candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  future=Future();future.set_result((candidate,result))
  self.s.job=(future,'tick',None,self.s.interaction_cursor);self.s.next_tick=float('inf');self.s._poll_mechanics()
  self.assertIsNone(self.s.module_error)
  self.f.f.candidate=candidate
 def test_public_research_can_prompt_an_independent_character_decision(self):
  self.f.finish_trip();self.assertEqual(len(self.f.observe()),1)
  job=self.f.q.claim();packet=json.loads(job['result']);ctx=self.s.inspect()
  ctx['runtime']=dict(kind='character',observed_event=packet,previous_source=self.f.f.candidate.source)
  reactions.prepare(ctx,self.f.fetch)
  action=dict(id='field_researcher',expected_version=1,evidence=[packet['evidence']],reason='I want to follow Bulbasaur research.',
      changes=dict(research_interests=[1]),object=dict(self.s.objects[0]))
  self.apply(action,ctx);self.f.q.finish(job['id'],'succeeded',dict(ok=True))
  self.assertEqual(self.s.module_state['world_characters']['field_researcher']['research_interests'],[1])
  self.assertEqual(self.f.observe(),[])
  conn=dict(id='Alice',presence=dict(campaign_run='private-run',state=[1,4,5,5,0,0,1],state_time=time.monotonic()))
  # Different species does not trigger an interested character.
  self.assertEqual(research.handle(self.s,conn,b'D REPORT 1 4'),'D ACK 1\n')
  self.assertEqual(self.f.observe(),[])
  self.assertEqual(research.handle(self.s,conn,b'D REPORT 1 5'),'D ACK 1\n')
  self.assertEqual(len(self.f.observe()),1)
  job=self.f.q.claim();packet=json.loads(job['result']);ctx=self.s.inspect()
  ctx['runtime']=dict(kind='character',observed_event=packet,previous_source=self.f.f.candidate.source)
  reaction=reactions.prepare(ctx,self.f.fetch)
  event=ctx['recalled_history']['events'][-1]
  self.assertNotIn('private-run',str(event));self.assertNotIn('Alice',str(event))
  action=dict(id='field_researcher',expected_version=2,evidence=[packet['evidence']],reason='Public notes suggest a new question.',
      changes=dict(goals=['Study reported Bulbasaur'],team=[dict(species=278,level=14)]),
      object=dict(self.s.objects[0],text='New research to consider.'))
  reactions.check_response(dict(character_actions=[action],tests='assert True'),reaction)
  self.apply(action,ctx)
  self.assertEqual(self.s.module_state['world_characters']['field_researcher']['goals'],['Study reported Bulbasaur'])
  self.assertEqual(self.s.module_state['world_characters']['field_researcher']['research_interests'],[1])
  self.f.q.finish(job['id'],'succeeded',dict(ok=True))
  self.assertEqual(research.handle(self.s,conn,b'D REPORT 1 5'),'D ACK 1\n')
  self.assertEqual(self.f.observe(),[])  # Re-publication does not invent another discovery.
  self.s.close();holder=self.f.f.fixture.case;holder.server=holder.open()
  self.assertEqual(holder.server.module_state['world_characters']['field_researcher']['research_interests'],[1])
 def test_validation_and_publication_guards(self):
  from world.characters import records
  from copy import deepcopy
  state=deepcopy(self.s.module_state);actor=state['world_characters']['field_researcher']
  for value in ([True], [0], [1027], [1,1],list(range(1,10)), '1'):
   actor['research_interests']=value
   with self.assertRaises(ValueError):records(state)
  actor['research_interests']=[1]
  e=dict(event='shared_research_published',basis=research.BASIS,publication='explicit_current_dex_snapshot',entries=[[1,1]])
  self.assertTrue(reactions.dynamic_result(e,'field_researcher',actor))
  for change in (dict(publication='private'),dict(basis='invented'),dict(entries=[[1,0]]),dict(entries=[[1,1],[1,2]])):
   with self.subTest(change=change):self.assertFalse(reactions.dynamic_result(dict(e,**change),'field_researcher',actor))
