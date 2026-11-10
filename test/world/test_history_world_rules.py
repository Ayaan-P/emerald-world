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
 def test_owner_pause_all_and_bounded_scan(self):
  self.install()
  for i in range(70):self.event(str(i))
  seq=self.event();self.assertIsNone(rules.tick(self.s,now=10000))
  self.assertEqual(rules.tick(self.s,now=10006)['trigger'],seq)
  result=rules.control(self.s,dict(command='world_reactions',action='pause_all'))
  self.assertFalse(any(r['enabled'] for r in result['rules']));self.event()
  self.assertIsNone(rules.tick(self.s,now=10100))
