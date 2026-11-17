"""Retained cast initiative installs actual survey; only shared arrivals feed growth."""
from copy import deepcopy
import json,tempfile,unittest
import test_canonical_cast as fixture
import test_landmark_survey as survey_fixture
from test_route_landscape import plan
from world.route_landscape import compile_plan
from world import canonical_cast as cast,character_reactions as reactions
from world.runtime_gm import IntentQueue

class CanonicalStudyTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  blob,self.report=compile_plan(plan())
  self.revision=self.s._replace_cave(blob,label='Field Study Grounds')
  self.study=dict(revision=self.revision,title='Steven field comparison',
      sites=[{k:p[k] for k in ('id','x','y')} for p in self.report['landmarks'][1:-1]])
  self.initial=self.f.action();self.initial['id']='canon_steven'
  self.initial['changes'].update(goal='Prepare a field comparison for willing explorers',
      dialogue='I want to organize a field comparison without deciding what explorers will find.',
      intentions=[dict(id='organize_study',kind='study',target=self.revision,reason='Create a useful comparison of existing terrain.')])
  self.f.apply(self.initial)
 def fetch(self,query):
  if query['command']=='inspect_saved_place':return dict(ok=True,**self.s.memory.inspect_saved_place(self.s,query['revision']))
  return self.f.fetch(query)
 def install(self):
  action=deepcopy(self.initial);action['expected_version']=1
  action['changes'].update(intentions=[],fulfill='organize_study',study=deepcopy(self.study))
  self.f.apply(action);return action
 def scout(self):
  h=survey_fixture.LandmarkSurveyTests();h.s=self.s;h.revision=self.revision;h.conn=h.connect('Scout')
  return h
 def test_autonomous_install_private_arrival_shared_feedback_and_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_steven','Organize useful studies from inspected geometry, then reconsider actual shared findings.')
    # Retained initiative starts without an expedition or another player event.
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    item=q.claim();self.assertEqual(json.loads(item['result'])['intention']['kind'],'study')
    ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    reactions.prepare(ctx,self.fetch)
    self.assertEqual(ctx['character_study_map']['revision'],self.revision)
    self.assertEqual(len(ctx['character_study_map']['rows']),127)
    self.assertNotIn('players',ctx['character_study_map'])
    action=self.install();q.finish(item['id'],'succeeded',dict(ok=True))
    publication=next(e for e in self.s.memory.history()['events'] if e['event']=='canonical_study_published')
    self.assertEqual(publication['outcome'],'immutable_survey_installed')
    self.assertEqual(self.s.shared_cave.identity,self.revision)
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_sessions').fetchone()[0],0)
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_intent_receipts').fetchone()[0],1)
    # Consume the real fulfillment event before testing private-visit isolation.
    for key in reactions.observe(q,self.s.inspect(),self.f.fetch):
     claimed=q.claim();self.assertEqual(claimed['id'],key);q.finish(key,'succeeded',dict(ok=True))
    h=self.scout();site=self.study['sites'][0]
    h.state(h.conn,site['x'],site['y']);self.assertEqual(h.count(),0)
    h.command('/explore start');self.assertEqual(h.count(),1)
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.fetch),[])
    before=self.s.memory.history()
    h.command('/explore share '+site['id']);self.assertEqual(self.s.memory.history(),before)
    h.command('/explore share '+site['id']+' confirm')
    shared=self.s.memory.history()['events'][-1]
    self.assertEqual(shared['study_actor'],'canon_steven');self.assertEqual(shared['study_digest'],publication['digest'])
    self.assertNotIn('Scout',json.dumps(shared));self.assertNotIn('trainer',shared)
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    reaction=q.claim();self.assertEqual(reaction['player'],'canon_steven')
    changed=deepcopy(action);changed['expected_version']=2
    changed['changes'].update(goal='Compare the shared landmark observation with the remaining sites',
       dialogue='One explorer shared an arrival. I want to compare the other sites before drawing conclusions.',
       evidence=[shared['seq']])
    ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(reaction['result']))
    reactions.check_response(dict(canonical_actions=[changed],tests='assert True'),reactions.prepare(ctx,self.fetch))
    self.f.apply(changed)
    self.assertEqual(self.s.objects,[])
    public=self.s.memory.history()['events']
    for site in self.study['sites'][1:]:h.state(h.conn,site['x'],site['y'])
    self.assertIn('Survey complete',' '.join(self.s.landmark_survey.lines(h.conn)))
    self.assertEqual(self.s.memory.history()['events'],public)
   finally:q.close()
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_studies').fetchone()[0],1)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_visits').fetchone()[0],len(self.study['sites']))
  self.assertEqual(cast.records(self.s.module_state)['canon_steven']['goal'],changed['changes']['goal'])
 def test_painted_outdoors_supports_independent_survey_and_private_share(self):
  from world.shared_outdoor_palette import encode, add_trail
  from world.shared_cave import SharedCave
  geometry,network=compile_plan(plan());base=SharedCave(geometry);rows=[r.decode('ascii') for r in base._rows]
  site=self.study['sites'][0]
  blob=encode(dict(rows=rows,spawn=[1,1],exit=[125,125]),[])
  positions={s['id']:(s['x'],s['y']) for s in network['landmarks']}
  for route in network['routes']:
   blob,_,_=add_trail(blob,'sand',1,endpoints=(positions[route['source']],positions[route['target']]))
  revision=self.s._replace_cave(blob,label='Painted Study Grounds');self.assertEqual(self.s.shared_cave.version,17)
  change=deepcopy(self.initial);change['expected_version']=1
  change['changes'].update(intentions=[dict(id='painted_study',kind='study',target=revision,reason='Compare this landscape.')])
  self.f.apply(change)
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_steven','Inspect a possible study on the outdoor map.')
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    item=q.claim();ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    reactions.prepare(ctx,self.fetch)
    self.assertEqual(ctx['character_study_map']['template_version'],17)
    self.assertEqual(ctx['character_study_map']['rows'][site['y']][site['x']],'.')
    self.assertEqual(ctx['character_study_map']['palette_rows'][site['y']][site['x']],'s')
    self.assertEqual(ctx['character_study_map']['terrain_legend']['s'],'sand')
    def bad_fetch(query):
     saved=self.fetch(query)
     if query['command']=='inspect_saved_place':
      saved['palette_rows']=list(saved['palette_rows']);y=site['y'];x=site['x'];line=saved['palette_rows'][y]
      saved['palette_rows'][y]=line[:x]+'r'+line[x+1:]
     return saved
    bad=self.f.context();bad['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    with self.assertRaisesRegex(ValueError,'terrain does not match'):reactions.prepare(bad,bad_fetch)
   finally:q.close()
  action=deepcopy(change);action['expected_version']=2
  study=deepcopy(self.study);study['revision']=revision
  action['changes'].update(intentions=[],fulfill='painted_study',study=study)
  self.f.apply(action)
  h=survey_fixture.LandmarkSurveyTests();h.s=self.s;h.revision=revision
  def connect(name):
   token=self.s.create_identity(name)['token'];c=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
   h.send(c,f'HELLO 1 {name} {token} SOCIALCAVE17');h.send(c,'CHAT_ENABLE');h.send(c,'CAVE GET');h.send(c,'CAVE ACK '+revision);h.state(c,1,1);return c
  h.conn=connect('PaintScout');other=connect('OtherScout')
  h.command('/explore start');h.state(h.conn,site['x'],site['y']);self.assertEqual(h.count(),1)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_visits WHERE trainer=?',(other['id'],)).fetchone()[0],0)
  before=self.s.memory.history()['events'];h.command('/explore share '+site['id']);self.assertEqual(before,self.s.memory.history()['events'])
  h.command('/explore share '+site['id']+' confirm');event=self.s.memory.history()['events'][-1]
  self.assertEqual(event['event'],'landmark_discovery_shared');self.assertEqual(event['revision'],revision);self.assertNotIn('PaintScout',json.dumps(event))
  # Plain geometry remains the actor-facing representation, never private visits.
  from admin_transport import admin_request
  saved=admin_request(self.s,dict(command='inspect_saved_place',revision=revision));self.assertTrue(saved['ok'])
  self.assertEqual(saved['template_version'],17)
  self.assertLess(len(json.dumps(saved).encode()),65536)
  self.assertEqual(saved['rows'][site['y']][site['x']],'.');self.assertNotIn('survey_visits',saved)

 def test_painted_rock_cannot_become_a_study_site(self):
  from world.shared_outdoor_palette import encode
  from world.shared_cave import SharedCave
  from world.canonical_studies import publish
  base=SharedCave(compile_plan(plan())[0]);rows=[r.decode('ascii') for r in base._rows];site=self.study['sites'][0]
  blob=encode(dict(rows=rows,spawn=[1,1],exit=[125,125]),[dict(x=site['x'],y=site['y'],width=1,height=1,terrain='rock')])
  revision=self.s._replace_cave(blob,label='Rock Study Grounds');study=deepcopy(self.study);study['revision']=revision
  with self.assertRaisesRegex(ValueError,'not walkable'):
   with self.s.db:publish(self.s,dict(character_id='canon_steven',character_name='Steven',before={},after=dict(study=study,evidence=[self.f.evidence])))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_studies').fetchone()[0],0)

 def test_failed_geometry_rolls_back_actor_study_and_receipts(self):
  before=deepcopy(self.s.module_state);history=self.s.memory.history()
  bad=deepcopy(self.study);bad['sites'][0].update(x=124,y=2)
  action=deepcopy(self.initial);action['expected_version']=1
  action['changes'].update(intentions=[],fulfill='organize_study',study=bad)
  source=cast.compile_actions([action],self.f.context());ns={};exec(source,ns)
  result=ns['update'](self.s._context(),deepcopy(self.s.module_state))
  from concurrent.futures import Future
  from world.mechanics import Candidate
  import hashlib
  fut=Future();fut.set_result((Candidate(source,hashlib.sha256(source.encode()).hexdigest()),result))
  self.s.job=(fut,'deploy',None,self.s.interaction_cursor);self.s._poll_mechanics()
  self.assertIn('not walkable',self.s.module_error)
  self.assertEqual(self.s.module_state,before)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_routes').fetchone()[0],0)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_intent_receipts').fetchone()[0],0)
  self.assertEqual(self.s.memory.history(),history)
 def test_existing_survey_cannot_be_replaced_or_claimed(self):
  self.s.landmark_survey.register(plan())
  from world.canonical_studies import publish
  with self.assertRaisesRegex(ValueError,'cannot be replaced'):
   with self.s.db:publish(self.s,dict(character_id='canon_steven',character_name='Steven',before={},after=dict(study=self.study,evidence=[self.f.evidence])))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_studies').fetchone()[0],0)
 def test_invalid_scope_and_duplicate_sites_refused(self):
  from world.canonical_studies import validate,publish
  for study in [dict(self.study,revision='bad'),dict(self.study,sites=[self.study['sites'][0]]*2)]:
   with self.assertRaises(ValueError):validate(study)
  missing=dict(self.study,revision='0'*64)
  with self.assertRaisesRegex(ValueError,'archived'):
   with self.s.db:publish(self.s,dict(character_id='canon_steven',character_name='Steven',before={},after=dict(study=missing,evidence=[self.f.evidence])))
