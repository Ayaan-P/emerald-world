"""Fieldwork measures real archived geometry only after actual authority travel."""
from copy import deepcopy
import hashlib,json,unittest
import test_character_journeys as journeys
from world.character_actions import compile_actions,validate_actions
from world.mechanics import Candidate
from world.canonical_cast import decision_evidence,reaction_activity
from world.character_reactions import dynamic_result

class ReconnaissanceTests(unittest.TestCase):
 def tick(self,n):
  from concurrent.futures import Future
  from world.character_actions import action_step
  self.s.tick=n
  result=action_step([self.action],self.definition,dict(state=self.s.module_state,tiles=[],objects=self.s.objects),self.s._context())
  future=Future();future.set_result((self.candidate,result))
  self.s.job=(future,'tick',None,self.s.interaction_cursor);self.s.next_tick=float('inf');self.s._poll_mechanics()
  self.assertIsNone(self.s.module_error)
  self.snapshots.append(deepcopy(self.s.module_state['world_character_controls']['harbor_guide'].get('walk')))
 def setUp(self):
  journeys.JourneyTests.setUp(self)
  # Start a new versioned task from the same current position before movement.
  self.action['expected_version']=3;self.action['survey']='Northern access transect'
  ctx=self.s.inspect();ctx['runtime']=dict(previous_source=self.candidate.source)
  source=compile_actions([self.action],ctx)
  self.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.definition=hashlib.sha256(json.dumps([self.action],sort_keys=True).encode()).hexdigest();self.tick(0)
 def reports(self):return [e for e in self.s.memory.history()['events'] if e['event']=='character_field_report']
 def test_measured_report_reacts_and_survives_restart(self):
  for n in range(1,7):self.tick(n)
  self.assertEqual(self.reports(),[])
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.server=self.s
  for n in range(7,35):self.tick(n)
  event=self.reports()[0];self.assertEqual(len(self.reports()),1)
  self.assertEqual([s[:2] for s in event['samples']],self.path)
  cave=self.s.shared_cave
  for x,y,mask in event['samples']:
   expected=sum(1<<i for i,(dx,dy) in enumerate(((0,-1),(1,0),(0,1),(-1,0))) if cave.walkable(x+dx,y+dy))
   self.assertEqual(mask,expected)
  self.assertEqual(event['revision'],self.revision)
  self.assertEqual(event['title'],'Northern access transect')
  self.assertTrue(dynamic_result(event,'harbor_guide',{}))
  self.assertFalse(dynamic_result(event,'hill_keeper',{}))
  self.assertTrue(decision_evidence(event,'canon_steven',dict(journey_interests=[self.revision])))
  self.assertTrue(reaction_activity(event,'canon_steven',dict(journey_interests=[self.revision])))
  self.assertFalse(decision_evidence(event,'canon_steven',dict(places=[],journey_interests=['0'*64])))
  self.assertNotIn('species',event);self.assertNotIn('players',event)
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.server=self.s
  self.tick(36);self.assertEqual(len(self.reports()),1)
  # A separate deterministic author decision uses the real report, changing
  # actual rendered dialogue and retained goals, not inferred exploration success.
  control=self.s.module_state['world_character_controls']['harbor_guide']
  response=dict(id='harbor_guide',expected_version=control['character']['version'],
    evidence=[event['seq']],reason='Choose next work from the completed access measurements',
    changes=dict(goals=['Compare the '+str(len(event['junctions']))+' measured junctions']),
    object=dict(control['object'],text='The access report is ready.'))
  ctx=self.s.inspect();ctx['runtime']=dict(previous_source=self.candidate.source)
  source=compile_actions([response],ctx);self.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.action=response;self.definition=hashlib.sha256(json.dumps([response],sort_keys=True).encode()).hexdigest()
  self.tick(37)
  self.assertEqual(self.s.objects[0]['text'],'The access report is ready.')
  self.assertEqual(self.s.module_state['world_characters']['harbor_guide']['goals'],response['changes']['goals'])
  self.assertEqual(len(self.reports()),1)
 def test_survey_cannot_be_added_or_rewritten_midjourney(self):
  from world.character_journeys import validate
  after=deepcopy(self.s.module_state);after['world_character_controls']['harbor_guide']['journey']['survey']='Invented new work'
  with self.assertRaises(ValueError):validate(self.s,self.s.module_state,after,self.s.objects)
  bad=deepcopy(self.action);bad['expected_version']=4;bad.pop('journey')
  with self.assertRaises(ValueError):validate_actions([bad],self.s.inspect())
 def test_waiting_or_cancelled_fieldwork_never_reports(self):
  self.f.state(self.peer,*self.s.wilds_map,72,70)
  for n in range(1,5):self.tick(n)
  self.assertEqual(self.reports(),[])
  self.assertEqual(self.s.objects[0]['x'],71)
  self.action.pop('journey');self.action.pop('survey');self.action['expected_version']=4
  self.action['object']=deepcopy(self.s.objects[0])
  ctx=self.s.inspect();ctx['runtime']=dict(previous_source=self.candidate.source)
  source=compile_actions([self.action],ctx);self.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.definition=hashlib.sha256(json.dumps([self.action],sort_keys=True).encode()).hexdigest()
  for n in range(5,30):self.tick(n)
  self.assertEqual(self.reports(),[])
