"""Original cast can choose to follow public generated-place discoveries."""
import json,tempfile,unittest
from copy import deepcopy
import test_canonical_studies as fixture
from world import canonical_cast as cast,character_reactions as reactions
from world.runtime_gm import IntentQueue

class CanonicalFieldInterestTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalStudyTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.f.install()
  self.place=self.s.memory.place(self.f.revision)
  self.original=self.f.f.action();self.original['id']='canon_wally'
  self.original['changes'].update(field_interests=[self.place],goal='Follow discoveries in the new area')
  self.f.f.apply(self.original)
 def test_public_discovery_informs_original_cast_without_private_visit(self):
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_wally','Consider discoveries at this place.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.f.fetch),[])
    h=self.f.scout();site=self.f.study['sites'][0]
    h.state(h.conn,site['x'],site['y']);h.command('/explore start')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.f.fetch),[])
    h.command('/explore share '+site['id']);self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.f.fetch),[])
    h.command('/explore share '+site['id']+' confirm')
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.f.fetch)),1)
    item=q.claim();packet=json.loads(item['result']);ctx=self.f.f.context()
    ctx['runtime'].update(kind='character',observed_event=packet)
    reaction=reactions.prepare(ctx,self.f.f.fetch)
    self.assertIn('client-reported',ctx['field_report_limits'])
    event=ctx['recalled_history']['events'][-1];self.assertNotIn('Scout',json.dumps(event))
    change=deepcopy(self.original);change['expected_version']=1
    change['changes'].update(goal='Consider the shared field discovery',dialogue='Someone shared a discovery. I want to learn more.',evidence=[packet['evidence']])
    reactions.check_response(dict(canonical_actions=[change],tests='assert True'),reaction)
    self.f.f.apply(change);q.finish(item['id'],'succeeded',dict(ok=True))
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.f.fetch),[])
    self.assertEqual(cast.records(self.s.module_state)['canon_wally']['field_interests'],[self.place])
    self.assertEqual(self.s.objects,[]) # No duplicate original character is spawned.
   finally:q.close()
  self.s.close();self.f.f.f.case.server=self.f.f.f.case.open();self.s=self.f.f.f.case.server
  row=cast.records(self.s.module_state)['canon_wally']
  self.assertEqual(row['goal'],'Consider the shared field discovery')
  self.assertEqual(row['field_interests'],[self.place])
 def test_interest_validation_and_scoped_evidence(self):
  row=deepcopy(cast.records(self.s.module_state)['canon_wally']);state=deepcopy(self.s.module_state)
  for bad in ([self.place,self.place],['native:LittlerootTown'],['area:bad'],[self.place]*5,'bad'):
   state['canonical_cast']['canon_wally']['field_interests']=bad
   with self.assertRaises(ValueError):cast.records(state)
  event=dict(event='landmark_discovery_shared',publication='explicit_player_share',basis='authenticated_acknowledged_client_presence',place_id=self.place,revision='a'*64,landmark='camp',x=15,y=20)
  self.assertTrue(cast.reaction_activity(event,'canon_wally',row));self.assertTrue(cast.decision_evidence(event,'canon_wally',row))
  for change in (dict(publication='private'),dict(place_id='area:other'),dict(basis='forged')):
   self.assertFalse(cast.reaction_activity(dict(event,**change),'canon_wally',row))
   self.assertFalse(cast.decision_evidence(dict(event,**change),'canon_wally',row))

class LandscapeCastIntegrationTests(unittest.TestCase):
 def test_authored_landscape_can_host_original_cast_study_and_reaction(self):
  from world import actor_runtime as runtime
  from test_route_landscape import plan
  from test_landmark_survey import LandmarkSurveyTests
  f=fixture.CanonicalStudyTests();f.setUp();self.addCleanup(f.doCleanups)
  s=f.s;s.archive_generated_areas=True;s.persist_generated_cave=True
  p=plan()
  args=dict(label='Living field',layout='clearings',blueprint=json.dumps(p,separators=(',',':')),biome='meadow',seed=1,ponds=3,trail='sand',trail_width=1,zones=json.dumps({'camp':'long_grass','ruins':'sand'}))
  action=f.f.action();action['changes']['plan']=dict(id='field',purpose='Create a connected landscape.',steps=[dict(id='create',tool='world.create_landmark_landscape',args=args,after=[])])
  f.f.apply(action)
  result=runtime.tick(s,now=10);self.assertEqual(result['status'],'succeeded')
  revision=s.shared_cave.identity;place=s.memory.place(revision)
  self.assertEqual(s.shared_cave.version,17)
  event=next(e for e in s.memory.history()['events'] if e['seq']==result['seq'])
  report=event['result']['report'];self.assertEqual(report['ponds_created'],3)
  self.assertGreaterEqual(report['watercourse_tiles'],8)
  study=deepcopy(f.study);study['revision']=revision
  change=deepcopy(f.initial);change['expected_version']=1
  change['changes'].update(intentions=[dict(id='new_study',kind='study',target=revision,reason='Study the new place.')])
  f.f.apply(change)
  change=deepcopy(change);change['expected_version']=2
  change['changes'].update(intentions=[],fulfill='new_study',study=study)
  f.f.apply(change)
  w=f.f.action();w['id']='canon_wally';w['changes'].update(field_interests=[place])
  f.f.apply(w)
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,s.inspect(),'canon_wally','Consider shared discoveries.')
    self.assertEqual(reactions.observe(q,s.inspect(),f.f.fetch),[])
    h=LandmarkSurveyTests();h.s=s;h.revision=revision
    token=s.create_identity('FieldScout')['token'];h.conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
    h.send(h.conn,'HELLO 1 FieldScout '+token+' SOCIALCAVE17');h.send(h.conn,'CHAT_ENABLE');h.send(h.conn,'CAVE GET');h.send(h.conn,'CAVE ACK '+revision)
    site=study['sites'][0];h.state(h.conn,site['x'],site['y']);h.command('/explore start')
    self.assertEqual(reactions.observe(q,s.inspect(),f.f.fetch),[])
    h.command('/explore share '+site['id']+' confirm')
    self.assertEqual(len(reactions.observe(q,s.inspect(),f.f.fetch)),1)
    packet=json.loads(q.claim()['result']);ctx=f.f.context();ctx['runtime'].update(kind='character',observed_event=packet)
    reactions.prepare(ctx,f.f.fetch)
    self.assertEqual(ctx['recalled_history']['events'][-1]['place_id'],place)
   finally:q.close()
