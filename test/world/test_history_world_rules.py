import json,sqlite3,unittest
from copy import deepcopy
import test_actor_agreements as fixture
from world import history_world_rules as rules,shared_outbreaks

class HistoryRuleTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.AgreementTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.actor='harbor_guide';self.peer=self.f.peer
  self.spec=dict(event='player_addressed_character',where={'character_id':self.actor,'text':'Open the field'},tool='world.configure_outbreak',args=self.f.f.args,cooldown=60,per_hour=2)
 def install(self,key='field',actor=None):
  result=self.f.run_tool(actor or self.actor,'world.publish_reaction',dict(id=key,rule=json.dumps(self.spec,separators=(',',':'))),'register_'+key)
  self.assertEqual(result['status'],'succeeded');return result
 def event(self,text='Open the field',kind='player_addressed_character'):
  with self.s.db:return self.s.memory.append(kind,dict(character_id=self.actor,text=text,publication='explicit_public_npc_speech',basis='authenticated_nearby_player_message'))
 def test_recent_activity_expires_across_restart_and_uses_actual_public_records(self):
  from unittest.mock import patch
  self.spec.update(every=2,within_seconds=60);self.install()
  with patch('world.world_memory.time.time',return_value=10000):old=self.event()
  self.assertIsNone(rules.tick(self.s,now=10000))
  db=sqlite3.connect(':memory:');self.s.db.backup(db);original=self.s.db;self.s.db=db
  try:
   rules.setup(db);self.s.history_rule_next=0
   with patch('world.world_memory.time.time',return_value=10070):fresh=self.event()
   self.assertIsNone(rules.tick(self.s,now=10070))
   with patch('world.world_memory.time.time',return_value=10080):new=self.event()
   result=rules.tick(self.s,now=10080)
   self.assertEqual(result['trigger_events'],[fresh,new]);self.assertNotIn(old,result['trigger_events'])
   self.assertTrue(any(line.startswith('WILD_OUTBREAK') for line in self.s._snapshot(self.peer).splitlines()))
  finally:self.s.db=original;db.close()
 def test_expired_backlog_and_receipt_failure_cannot_create_phantom_reaction(self):
  from unittest.mock import patch
  self.spec.update(every=2,within_seconds=60);self.install()
  with patch('world.world_memory.time.time',return_value=10000):self.event();self.event()
  self.assertIsNone(rules.tick(self.s,now=10100))
  self.assertIsNone(shared_outbreaks.line(self.s,self.peer))
  with patch('world.world_memory.time.time',return_value=10105):a=self.event();b=self.event()
  original=self.s.memory.append
  def append(kind,data):
   if kind=='history_world_rule_result':raise ValueError('receipt unavailable')
   return original(kind,data)
  with patch.object(self.s.memory,'append',side_effect=append):self.assertEqual(rules.tick(self.s,now=10105)['status'],'uncommitted')
  self.assertIsNone(shared_outbreaks.line(self.s,self.peer))
  self.assertEqual(rules.tick(self.s,now=10110)['trigger_events'],[a,b])

 def test_recent_window_rejects_invalid_configuration_and_future_events(self):
  from unittest.mock import patch
  for value in (True,0,59,604801):
   d=deepcopy(self.spec);d.update(every=2,within_seconds=value)
   with self.assertRaises(ValueError):rules.publish(self.s,self.actor,{},dict(id='bad',rule=json.dumps(d)))
  d=deepcopy(self.spec);d['within_seconds']=60
  with self.assertRaises(ValueError):rules.publish(self.s,self.actor,{},dict(id='bad',rule=json.dumps(d)))
  self.spec.update(every=2,within_seconds=60);self.install()
  with patch('world.world_memory.time.time',return_value=20000):self.event()
  with patch('world.world_memory.time.time',return_value=10000):self.event()
  self.assertIsNone(rules.tick(self.s,now=10000))
  self.assertEqual(len(rules.discover(self.s)['rules'][0]['pending_matches']),1)

 def test_actual_future_event_effect_native_wire_and_no_replay(self):
  old=self.event();self.install();self.assertIsNone(rules.tick(self.s,now=10000));self.assertIsNone(shared_outbreaks.line(self.s,self.peer))
  seq=self.event();out=rules.tick(self.s,now=10006)
  self.assertEqual(out['status'],'succeeded');self.assertEqual(out['trigger'],seq)
  self.assertTrue(any(l.startswith('WILD_OUTBREAK') for l in self.s._snapshot(self.peer).splitlines()))
  self.assertIsNone(rules.tick(self.s,now=10100))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM history_world_rule_runs').fetchone()[0],1)
  receipt=next(e for e in self.s.memory.history()['events'] if e['event']=='history_world_rule_result')
  self.assertEqual(receipt['trigger'],seq);self.assertNotEqual(seq,old)
 def test_filters_no_private_read_and_no_effect_feedback_loop(self):
  self.install();self.event('Other words');self.event(kind='shared_outbreak_configured')
  with self.s.db:self.s.db.execute("INSERT INTO events(kind,data) VALUES('private',?)",(json.dumps(dict(event='player_addressed_character',character_id=self.actor,text='Open the field')),))
  self.assertIsNone(rules.tick(self.s,now=10000));self.assertIsNone(shared_outbreaks.line(self.s,self.peer))
  self.event();self.assertEqual(rules.tick(self.s,now=10006)['status'],'succeeded');self.assertIsNone(rules.tick(self.s,now=10100))
 def test_restart_recurring_budget_and_failed_attempt_consumption(self):
  self.spec['per_hour']=1;self.install()
  with self.s.db:shared_outbreaks.configure(self.s,'other',{},self.f.f.args)
  self.event();self.assertEqual(rules.tick(self.s,now=10000)['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT used FROM history_world_rules').fetchone()[0],1)
  seq=self.event();self.assertIsNone(rules.tick(self.s,now=10100))
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   rules.setup(db);self.s.history_rule_next=0
   self.assertIsNone(rules.tick(self.s,now=11000))
   out=rules.tick(self.s,now=13601);self.assertEqual(out['trigger'],seq);self.assertEqual(out['status'],'blocked')
   self.assertEqual(db.execute('SELECT count(*) FROM history_world_rule_runs').fetchone()[0],2)
  finally:self.s.db=old;db.close()
 def test_pause_ownership_retirement_and_discovery(self):
  self.install();self.assertEqual(self.s.inspect()['actor_runtime']['history_world_rules']['rules'][0]['id'],'field')
  with self.assertRaises(ValueError):rules.pause(self.s,'other',{},dict(id='field'))
  with self.s.db:rules.pause(self.s,self.actor,{},dict(id='field'))
  self.event();self.assertIsNone(rules.tick(self.s,now=10000))
  self.install('second');self.s.module_state['world_characters'][self.actor]['status']='retired';self.s.module_state['world_characters'][self.actor].pop('offer',None)
  self.event();self.assertIsNone(rules.tick(self.s,now=10006))
  self.assertFalse(any(r['enabled'] for r in rules.discover(self.s)['rules']))
 def test_invalid_operations_cycles_and_limits(self):
  for field,value in [('tool','world.publish_reaction'),('event','history_world_rule_result'),('cooldown',0),('per_hour',99),('args',{'map':{'result':'event'}})]:
   d=deepcopy(self.spec);d[field]=value
   with self.assertRaises(ValueError):rules.publish(self.s,self.actor,{},dict(id='bad',rule=json.dumps(d)))
  self.install();self.install('two')
  with self.assertRaises(ValueError):rules.publish(self.s,self.actor,{},dict(id='three',rule=json.dumps(self.spec)))
  d=deepcopy(self.spec);d['where']['text']='Different'
  with self.assertRaises(ValueError):rules.publish(self.s,self.actor,{},dict(id='field',rule=json.dumps(d)))
 def test_round_robin_and_one_effect_per_tick(self):
  self.install();self.install('other_field','other');self.event()
  first=rules.tick(self.s,now=10000);self.assertEqual(first['actor'],self.actor)
  self.assertIsNone(rules.tick(self.s,now=10001))
  second=rules.tick(self.s,now=10006);self.assertEqual(second['actor'],'other');self.assertEqual(second['status'],'blocked')
 def test_real_player_speech_enters_rule_without_injected_event(self):
  from world.npc_conversations import command
  self.install();f=self.f.f.f;revision=f.obj['region_revision'];place=self.s.db.execute('SELECT place_id FROM world_region_revisions WHERE revision=?',(revision,)).fetchone()[0]
  player=f.connect('Speaker',place,revision);command(self.s,player,['say-public',self.actor,'Open','the','field'])
  result=rules.tick(self.s,now=10000);self.assertEqual(result['status'],'succeeded')
  event=next(e for e in self.s.memory.history()['events'] if e['seq']==result['trigger'])
  self.assertEqual(event['publication'],'explicit_public_npc_speech')
 def test_receipt_failure_rolls_back_actual_effect_and_retries_uncommitted_event(self):
  from unittest.mock import patch
  self.install();seq=self.event();before=self.s.revision;original=self.s.memory.append
  def append(kind,data):
   if kind=='history_world_rule_result':raise ValueError('receipt unavailable')
   return original(kind,data)
  with patch.object(self.s.memory,'append',side_effect=append):self.assertEqual(rules.tick(self.s,now=10000)['status'],'uncommitted')
  self.assertIsNone(shared_outbreaks.line(self.s,self.peer));self.assertEqual(self.s.revision,before)
  self.assertEqual(self.s.db.execute('SELECT used FROM history_world_rules').fetchone()[0],0)
  self.assertEqual(rules.tick(self.s,now=10006)['trigger'],seq)
 def test_public_event_can_publish_attributed_tv_bulletin(self):
  from world.actor_bulletins import line
  self.spec.update(tool='world.publish_bulletin',args=dict(pages=json.dumps(['News from the field','A visitor spoke today']),evidence='@trigger',hours=1))
  self.install(); seq=self.event(); out=rules.tick(self.s,now=10000)
  self.assertEqual(out['status'],'succeeded'); self.assertEqual(out['trigger'],seq)
  published=next(e for e in self.s.memory.history()['events'] if e['event']=='character_bulletin_published')
  self.assertEqual(published['source_events'],[seq]); self.assertEqual(published['character_id'],self.actor)
  self.assertTrue(line(self.s,{'world_bulletin_capable':True}).startswith('WORLD_BULLETIN '))
  self.assertIsNone(line(self.s,{'world_bulletin_capable':False}))
  self.assertIsNone(rules.tick(self.s,now=10100))
 def test_bulletin_and_causal_receipt_roll_back_together(self):
  from unittest.mock import patch
  from world.actor_bulletins import line
  self.spec.update(tool='world.publish_bulletin',args=dict(pages='["News","Today"]',evidence='@trigger',hours=1));self.install();seq=self.event()
  original=self.s.memory.append
  def append(kind,data):
   if kind=='history_world_rule_result':raise ValueError('receipt unavailable')
   return original(kind,data)
  with patch.object(self.s.memory,'append',side_effect=append):self.assertEqual(rules.tick(self.s,now=10000)['status'],'uncommitted')
  self.assertIsNone(line(self.s,{'world_bulletin_capable':True}))
  self.assertEqual(rules.tick(self.s,now=10006)['trigger'],seq)
  self.assertTrue(line(self.s,{'world_bulletin_capable':True}).startswith('WORLD_BULLETIN '))
 def test_bulletin_cannot_select_or_interpolate_evidence(self):
  self.spec.update(tool='world.publish_bulletin',args=dict(pages='["News","Today"]',evidence='[1]',hours=1))
  with self.assertRaises(ValueError):rules.publish(self.s,self.actor,{},dict(id='bad',rule=json.dumps(self.spec)))
  self.spec['args']['evidence']='@trigger';self.spec['args']['pages']='["{event.text}","Today"]'
  self.install();self.event();self.assertEqual(rules.tick(self.s,now=10000)['status'],'blocked')
 def test_repeated_events_produce_a_real_outbreak_and_persist_across_restart(self):
  self.spec['every']=3;self.install();a=self.event();self.event('Different');b=self.event()
  self.assertIsNone(rules.tick(self.s,now=10000));self.assertIsNone(shared_outbreaks.line(self.s,self.peer))
  self.assertEqual(rules.discover(self.s)['rules'][0]['pending_matches'],[a,b])
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   self.s.history_rule_next=0;c=self.event();out=rules.tick(self.s,now=10006)
   self.assertEqual(out['trigger_events'],[a,b,c]);self.assertEqual(out['status'],'succeeded')
   self.assertTrue(shared_outbreaks.line(self.s,self.peer).startswith('WILD_OUTBREAK'))
   receipt=next(e for e in self.s.memory.history()['events'] if e['event']=='history_world_rule_result')
   self.assertEqual(receipt['trigger_events'],[a,b,c]);self.assertIsNone(rules.tick(self.s,now=10100))
  finally:self.s.db=old;db.close()
 def test_threshold_receipt_failure_preserves_progress_and_retries(self):
  from unittest.mock import patch
  self.spec['every']=2;self.install();a=self.event();self.assertIsNone(rules.tick(self.s,now=10000));b=self.event()
  original=self.s.memory.append
  def append(kind,data):
   if kind=='history_world_rule_result':raise ValueError('receipt unavailable')
   return original(kind,data)
  with patch.object(self.s.memory,'append',side_effect=append):self.assertEqual(rules.tick(self.s,now=10006)['status'],'uncommitted')
  self.assertIsNone(shared_outbreaks.line(self.s,self.peer))
  out=rules.tick(self.s,now=10012);self.assertEqual(out['trigger_events'],[a,b]);self.assertEqual(out['status'],'succeeded')
 def test_threshold_can_publish_bulletin_with_final_event_source(self):
  self.spec.update(every=2,tool='world.publish_bulletin',args=dict(pages='["News","Today"]',evidence='@trigger',hours=1))
  self.install();a=self.event();b=self.event();result=rules.tick(self.s,now=10000)
  self.assertEqual(result['trigger_events'],[a,b]);self.assertEqual(result['status'],'succeeded')
  event=next(e for e in self.s.memory.history()['events'] if e['event']=='character_bulletin_published')
  self.assertEqual(event['source_events'],[b])

 def test_repeated_threshold_batches_and_validation(self):
  for value in (0,13,True,'3'):
   self.spec['every']=value
   with self.assertRaises(ValueError):rules.publish(self.s,self.actor,{},dict(id='bad',rule=json.dumps(self.spec)))
  self.spec['every']=2;self.install();a=self.event();b=self.event();c=self.event();d=self.event()
  self.assertEqual(rules.tick(self.s,now=10000)['trigger_events'],[a,b])
  self.assertEqual(rules.tick(self.s,now=10066)['trigger_events'],[c,d])

 def test_owner_pause_all_and_bounded_scan(self):
  self.install()
  for i in range(70):self.event(str(i))
  seq=self.event();self.assertIsNone(rules.tick(self.s,now=10000))
  self.assertEqual(rules.tick(self.s,now=10006)['trigger'],seq)
  result=rules.control(self.s,dict(command='world_reactions',action='pause_all'))
  self.assertFalse(any(r['enabled'] for r in result['rules']));self.event()
  self.assertIsNone(rules.tick(self.s,now=10100))
