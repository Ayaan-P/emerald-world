"""Real private survey and opt-in publication can inform a recurring actor."""
from copy import deepcopy
import json,unittest
from admin_transport import admin_request
from test_character_research_interests import ResearchInterestTests
from test_landmark_survey import LandmarkSurveyTests
from test_route_landscape import plan
from world import character_reactions as reactions
from world.route_landscape import compile_plan

class FieldInterestTests(unittest.TestCase):
 def setUp(self):
  self.f=ResearchInterestTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s
 def test_shared_discovery_drives_decision_and_return_battle_after_restart(self):
  blob,report=compile_plan(plan());revision=self.s._replace_cave(blob,label='Field survey')
  place=self.s.memory.place(revision)
  registered=admin_request(self.s,dict(command='register_survey',plan=plan()))
  self.assertTrue(registered['ok'],registered)
  evidence=self.s.memory.history()['events'][-1]['seq']
  ctx=self.s.inspect();ctx['runtime']=dict(previous_source=self.f.f.f.candidate.source)
  action=dict(id='field_researcher',expected_version=1,evidence=[evidence],reason='Follow discoveries in this place.',
    changes=dict(field_interests=[place]),object=dict(self.s.objects[0]))
  self.f.apply(action,ctx)
  self.assertEqual(self.f.f.observe(),[])
  h=LandmarkSurveyTests();h.s=self.s;h.revision=revision;h.conn=h.connect('Scout')
  h.command('/explore start');h.state(h.conn,15,20)
  self.assertEqual(self.f.f.observe(),[])  # Private arrival never wakes the actor.
  h.command('/explore share camp');self.assertEqual(self.f.f.observe(),[])
  h.command('/explore share camp confirm')
  self.assertEqual(len(self.f.f.observe()),1)
  job=self.f.f.q.claim();packet=json.loads(job['result']);ctx=self.s.inspect()
  ctx['runtime']=dict(kind='character',observed_event=packet,previous_source=self.f.f.f.candidate.source)
  reaction=reactions.prepare(ctx,self.f.f.fetch)
  self.assertIn('client-reported',ctx['field_report_limits'])
  event=ctx['recalled_history']['events'][-1];self.assertNotIn('Scout',json.dumps(event))
  response=dict(id='field_researcher',expected_version=2,evidence=[packet['evidence']],reason='A shared report suggests returning.',
    changes=dict(goals=['Explore the shared landmark'],team=[dict(species=278,level=14)]),
    object=dict(self.s.objects[0],text='A discovery worth exploring.'))
  reactions.check_response(dict(character_actions=[response],tests='assert True'),reaction)
  self.f.apply(response,ctx);self.f.f.q.finish(job['id'],'succeeded',dict(ok=True))
  self.assertEqual(self.f.f.observe(),[])
  self.s.close();holder=self.f.f.f.fixture.case;holder.server=holder.open();self.s=holder.server
  actor=self.s.module_state['world_characters']['field_researcher']
  self.assertEqual(actor['field_interests'],[place]);self.assertEqual(actor['team'],[dict(species=278,level=14)])
  token=self.s.create_identity('Returner')['token'];conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.s._line(conn,('HELLO 1 Returner '+token+' SOCIALTRAVELCHATRALLYCHAR1CHARQUEST1').encode());conn['out'].clear()
  self.s._line(conn,('STATE 1 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16).encode());conn['out'].clear()
  self.s._line(conn,b'CHARACTER_CHALLENGE 2 field_researcher 3')
  self.assertIn('field_researcher 3 1 278 14',conn['out'].decode())
 def test_validation_and_public_scope(self):
  from world.characters import records
  from world.landmark_survey import character_interested
  state=deepcopy(self.s.module_state);actor=state['world_characters']['field_researcher']
  place='area:01234567-89ab-cdef-0123-456789abcdef'
  for bad in ([place,place],['area:no'],['native:LittlerootTown'],[place]*5,'bad'):
   actor['field_interests']=bad
   with self.assertRaises(ValueError):records(state)
  actor['field_interests']=[place]
  event=dict(event='landmark_discovery_shared',publication='explicit_player_share',basis='authenticated_acknowledged_client_presence',place_id=place,revision='a'*64,landmark='camp',x=15,y=20)
  self.assertTrue(character_interested(event,actor))
  for change in (dict(publication='private'),dict(place_id='area:other'),dict(revision='bad'),dict(x=True),dict(basis='unknown')):
   self.assertFalse(character_interested(dict(event,**change),actor))
