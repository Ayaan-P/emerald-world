"""Long-lived cast experience informs later actual shared actions, not counters."""
import copy,json,tempfile,unittest
from world import canonical_cast as cast,canonical_world_actions as actions,character_reactions as reactions
from world.canonical_experiences import recall
from world.runtime_gm import IntentQueue
import test_canonical_world_actions as fixture

class ExperienceTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.WorldActionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.cast=self.f.f
  self.cast.apply(self.f.actor());self.first=actions.step(self.s,now=10)['seq']
  a=self.cast.action();a['id']='canon_wally';a['changes']['evidence']=[self.first]
  self.memory=dict(id='first_discussion',events=[self.first],interpretation='Rydel made room for a public discussion. I may have something different to contribute.')
  a['changes']['memories']=[self.memory];self.cast.apply(a)
 def test_older_experience_is_recalled_after_restart_and_changes_actual_opportunities(self):
  for _ in range(12):self.cast.complete()
  self.assertNotIn(self.first,[e['seq'] for e in self.s.inspect()['world_memory']['recent']])
  self.s.close();case=self.cast.f.case;case.server=case.open();self.s=case.server;self.cast.s=self.s;self.cast.f.server=self.s
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_wally','Consider your past experience when choosing an independent contribution.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.cast.fetch),[])
    # A normal new public gameplay outcome triggers the turn, not a timer or fake memory event.
    for name in ('Alice','Bob'):self.cast.f.connections[name]=self.cast.peer(name)
    self.cast.complete()
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.cast.fetch)),1)
    item=q.claim();ctx=self.cast.context();ctx['recalled_history']={'events':[]}
    ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    turn=reactions.prepare(ctx,self.cast.fetch)
    self.assertEqual(ctx['character_experiences']['memories'],[self.memory])
    self.assertIn(self.first,[e['seq'] for e in ctx['recalled_history']['events']])
    self.assertEqual(ctx['players'],[])
    a=self.f.actor('canon_wally',1,1,'contribute','join',self.cast.evidence)
    a['changes']['evidence'].append(self.first);a['changes']['memories']=[self.memory]
    a['changes']['dialogue']='I remember Rydel making room for a discussion. I have decided to add my own perspective.'
    reactions.check_response(dict(canonical_actions=[a],tests='assert True'),turn)
    # Compile using prepared context, not a special test-only memory bypass.
    source=cast.compile_actions([a],ctx);ns={};exec(source,ns)
    self.cast.commit(source,ns['update'](self.s._context(),copy.deepcopy(self.s.module_state)))
    self.assertEqual(actions.step(self.s,now=100)['actor'],'canon_wally')
    self.assertEqual(self.s.opportunities.offers('Bob','LittlerootTown')[0]['scenes'][0]['id'],'shared')
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
    from world.build_catalog import catalog_maps
    peer=self.cast.peer();peer['state'][:2]=next(pair for pair,m in catalog_maps().items() if m['name']=='VerdanturfTown_WandasHouse')
    self.s._line(peer,('CORE '+'a'*32+' CAST wally safe 55').encode())
    self.assertIn('I remember Rydel',bytes.fromhex(peer['out'].decode().strip().split()[-1]).decode())
    self.assertTrue(any('Rydel' in line for line in cast.guild_command(self.s,peer,['wally','experiences'])))
   finally:q.close()
 def test_cannot_launder_uninspected_private_or_missing_sources(self):
  for events in ([99999],[True],[self.first,self.first]):
   a=self.cast.action(1);a['id']='canon_wally';a['changes']['memories']=[dict(self.memory,events=events)]
   with self.assertRaises(ValueError):cast.compile_actions([a],self.cast.context())
  a=self.cast.action(1);a['id']='canon_wally';a['changes']['memories']=[dict(self.memory,interpretation='A revised interpretation without its source.')]
  with self.assertRaisesRegex(ValueError,'inspected decision evidence'):cast.compile_actions([a],self.cast.context())
 def test_retained_experience_can_be_revised_or_dropped_without_rewriting_history(self):
  before=self.s.memory.history()['events']
  a=self.cast.action(1);a['id']='canon_wally';a['changes']['evidence']=[self.first]
  a['changes']['memories']=[dict(self.memory,interpretation='Making an opportunity is not proof that anyone agreed with it.')]
  self.cast.apply(a)
  self.assertEqual(self.s.memory.history()['events'][:len(before)],before)
  a=self.cast.action(2);a['id']='canon_wally';self.cast.apply(a)
  self.assertNotIn('memories',cast.records(self.s.module_state)['canon_wally'])
 def test_recall_rejects_wrong_world_or_missing_history(self):
  row=cast.records(self.s.module_state)['canon_wally']
  for response in (dict(ok=True,world_id='other',events=[dict(seq=self.first)]),dict(ok=True,world_id=self.s.memory.world_id,events=[])):
   with self.assertRaises(ValueError):recall(self.cast.context(),row,lambda request:response)
 def test_existing_relationship_evidence_is_recalled_without_new_episode(self):
  a=self.cast.action(1);a['id']='canon_wally';a['changes']['evidence']=[self.first]
  a['changes']['relationships']={'canon_rydel':dict(stance='curious',motivation='His real decision made room for another perspective.',evidence=[self.first])}
  self.cast.apply(a)
  ctx=self.cast.context();ctx['recalled_history']={'events':[]}
  recall(ctx,cast.records(self.s.module_state)['canon_wally'],self.cast.fetch)
  self.assertEqual(ctx['character_experiences']['memories'],[])
  self.assertEqual(ctx['character_experiences']['relationship_sources'],{'canon_rydel':[self.first]})
  self.assertEqual([e['seq'] for e in ctx['recalled_history']['events']],[self.first])
