"""Existing Hoenn story receipts drive independent canonical decisions, not quests."""
import json,tempfile,time,unittest
from copy import deepcopy
import test_canonical_cast as fixture
from world import canonical_cast as cast,character_reactions as reactions
from world.core_story import shared_outcome
from world.runtime_gm import IntentQueue
from world.build_catalog import catalog_maps

class CampaignCastTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.peer=self.f.peer();self.run='a'*32
  for actor in ('canon_briney','canon_rydel'):
   a=self.f.action();a['id']=actor
   a['changes']['places']=['native:LittlerootTown','native:RusturfTunnel']
   if actor=='canon_rydel':a['changes']['offer']=dict(map='LittlerootTown',count=1)
   self.f.apply(a)
 def place(self,name):
  self.peer['state'][:2]=next(p for p,m in catalog_maps().items() if m['name']==name)
  self.peer['state_time']=time.monotonic()
 def command(self,action,key,confirmation):
  return self.s.core_story.handle(self.peer,['CORE',self.run,action,key,confirmation])
 def report(self):
  self.place('PetalburgWoods');self.command('REPORT','woods_rescued','complete')
  self.place('RusturfTunnel');self.command('REPORT','goods_recovered','complete')
 def test_actual_shared_rescue_informs_two_independent_cast_goals_and_native_responses(self):
  with tempfile.TemporaryDirectory() as tmp:
   queue=IntentQueue(tmp)
   try:
    for actor in ('canon_briney','canon_rydel'):
     reactions.configure(queue,self.s.inspect(),actor,'Consider real shared Hoenn events while preserving your identity and normal services.')
    self.assertEqual(reactions.observe(queue,self.s.inspect(),self.f.fetch),[])
    self.report()
    self.assertEqual(reactions.observe(queue,self.s.inspect(),self.f.fetch),[]) # Private progress is not author input.
    receipt=self.command('SHARE','goods_recovered','confirm')
    event=next(e for e in self.s.memory.history()['events'] if e['seq']==receipt['evidence'])
    self.assertNotIn('trainer',event);self.assertNotIn('run',event)
    self.assertEqual(len(reactions.observe(queue,self.s.inspect(),self.f.fetch)),2)
    choices={
      'canon_briney':('Reconsider sailing plans now that Peeko has been rescued','Peeko is safe. I am thinking about our next voyage.'),
      'canon_rydel':('Consider how to make advice useful to trainers travelling west','News from Rusturf makes me think about safer journeys.')}
    for _ in range(2):
     item=queue.claim();actor=item['player'];goal,dialogue=choices[actor]
     ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
     prepared=reactions.prepare(ctx,self.f.fetch)
     action=self.f.action(1,dialogue);action['id']=actor
     action['changes'].update(goal=goal,places=['native:RusturfTunnel'],evidence=[event['seq']],reason='Reconsider my own plans from the shared rescue report')
     reactions.check_response(dict(canonical_actions=[action],tests='assert True'),prepared)
     self.f.apply(action);queue.finish(item['id'],'succeeded',dict(ok=True))
    self.assertEqual(self.command('SHARE','goods_recovered','confirm'),receipt)
    self.assertEqual(reactions.observe(queue,self.s.inspect(),self.f.fetch),[])
    for actor in choices:
     binding=cast.BINDINGS[actor];self.place(binding['map'])
     response=self.command('CAST',binding['wire'],'safe')
     self.assertEqual(response['briefing'],choices[actor][1])
    self.assertEqual(self.s.objects,[]) # No duplicate/moved story NPC.
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM core_story_progress').fetchone()[0],2)
   finally:queue.close()
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s;self.f.f.server=self.s
  self.assertEqual(cast.records(self.s.module_state)['canon_briney']['goal'],choices['canon_briney'][0])
 def test_wrong_source_map_beat_or_claim_does_not_qualify(self):
  self.report();receipt=self.command('SHARE','goods_recovered','confirm')
  event=next(e for e in self.s.memory.history()['events'] if e['seq']==receipt['evidence'])
  self.assertTrue(shared_outcome(event,['native:RusturfTunnel']))
  self.assertFalse(shared_outcome(event,['native:PetalburgWoods']))
  for field,value in [('source','native_client_attestation'),('arc','invented'),('beat','champion'),('outcome','briney_won'),('summary','Briney personally won the battle'),('places',['native:LittlerootTown'])]:
   altered=dict(event,**{field:value})
   self.assertFalse(shared_outcome(altered,['native:RusturfTunnel']))
  # Shared rescue does not imply another actor's participation or relationship.
  row=deepcopy(cast.records(self.s.module_state)['canon_briney'])
  row['relationships']={'canon_rydel':dict(assessment='Rydel rescued Peeko',evidence=[event['seq']])}
  with self.assertRaises(ValueError):cast.validate_relationship_evidence(row,lambda seq:event,'canon_briney')
 def test_existing_native_devon_sync_can_seed_cast_without_expedition_evidence(self):
  self.place('RustboroCity_DevonCorp_3F')
  before=deepcopy(self.s.memory.history())
  self.command('SYNC','7','private')
  self.assertEqual(self.s.memory.history(),before)
  receipt=self.command('SHARE','devon_met','confirm')
  event=next(e for e in self.s.memory.history()['events'] if e['seq']==receipt['evidence'])
  self.assertEqual(event['outcome'],'devon_delivery_requested')
  self.assertTrue(shared_outcome(event,['native:RustboroCity_DevonCorp_3F']))
  self.assertNotIn('trainer',event);self.assertNotIn('run',event)
  # An ordinary GM can establish Steven's supplemental intentions directly
  # from actual campaign history, without inventing another expedition.
  action=self.f.action();action['id']='canon_steven'
  action['changes'].update(goal='Consider how to help couriers without assuming the letter has arrived',
    dialogue='Devon has asked for a delivery. I wonder how the journey will unfold.',
    places=['native:RustboroCity_DevonCorp_3F'],evidence=[receipt['evidence']],
    reason='The public record is a request, not proof of completed delivery')
  self.f.apply(action)
  self.assertEqual(cast.records(self.s.module_state)['canon_steven']['goal'],action['changes']['goal'])
  self.assertEqual(self.command('SHARE','devon_met','confirm'),receipt)
  self.command('SYNC','3','private')
  with self.assertRaises(ValueError):self.command('SHARE','devon_met','confirm')
 def test_devon_preview_matches_exact_native_literal(self):
  import os,re
  from pathlib import Path
  from world.core_story import BEATS
  source=Path(os.environ.get('EW_NATIVE_SOURCE','engines/expansion-native'))/'src/world/world_core_story.c'
  if not source.exists():self.skipTest('native component source not available')
  text=source.read_text();previews=re.search(r'sPreviews\[\]=\{(.*?)\};',text,re.S).group(1)
  strings=re.findall(r'"([^"\n]+)"',previews)
  self.assertEqual(strings[2],BEATS['devon_met']['public'])
  self.assertIn('if (VarGet(VAR_DEVON_CORP_3F_STATE)>=1) bits|=7;',text)
