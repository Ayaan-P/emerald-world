import json,unittest
import test_world_memory as memory_fixture
import test_actor_runtime as runtime_fixture
from world import actor_history as history,actor_runtime

class HistoryTests(unittest.TestCase):
 def setUp(self):
  self.f=memory_fixture.WorldMemoryTests();self.f.setUp();self.addCleanup(self.f.tearDown);self.s=self.f.server
 def search(self,query=None,after=0,through=0):
  return history.search(self.s,'reader',{},dict(query=json.dumps(query or {}),after=after,through=through))
 def test_old_matches_pagination_fixed_boundary_restart_and_private_exclusion(self):
  ids=[]
  with self.s.db:
   for n in range(25):
    ids.append(self.s.memory.append('canonical_letter_delivered',dict(sender='canon_steven',recipient='canon_wally',text='Meteor report '+str(n))))
   secret=self.s.db.execute('INSERT INTO events(kind,data) VALUES (?,?)',('private_report',json.dumps(dict(event='canonical_letter_delivered',sender='canon_steven',text='Meteor private')))).lastrowid
  q=dict(terms=['meteor'],actor='canon_wally',event='canonical_letter_delivered')
  first=self.search(q);self.assertEqual([r['seq'] for r in first['events']],ids[:8]);self.assertTrue(first['has_more'])
  with self.s.db:self.s.memory.append('canonical_letter_delivered',dict(sender='canon_steven',recipient='canon_wally',text='Meteor later'))
  self.s.close();self.f.server=self.f.open();self.s=self.f.server
  seen=[r['seq'] for r in first['events']];page=first
  while page['has_more']:
   page=self.search(q,page['cursor'],first['through']);seen.extend(r['seq'] for r in page['events'])
  self.assertEqual(seen,ids);self.assertEqual(page['cursor'],first['through'])
  with self.assertRaises(ValueError):history.read(self.s,'reader',{},dict(sequence=secret,path=''))
  self.assertNotIn('private',json.dumps(self.search(q)))
 def test_large_original_record_pointer_and_report_provenance(self):
  with self.s.db:
   seq=self.s.memory.append('canonical_trainer_result',dict(basis='voluntary_client_report',limits='Not a verified victory',detail={'a/b~c':['x'*13000,{'outcome':'reported_loss'}]}))
  page=self.search(dict(event='canonical_trainer_result'));self.assertFalse(page['events'][0]['complete'])
  read=lambda path:history.read(self.s,'reader',{},dict(sequence=seq,path=path))
  self.assertFalse(read('')['complete']);self.assertEqual(read('/basis')['value'],'voluntary_client_report')
  self.assertEqual(read('/detail/a~1b~0c/1/outcome')['value'],'reported_loss')
  self.assertFalse(read('/detail/a~1b~0c/0')['complete'])
  for path in ('/missing','/detail/~2','/detail/a~1b~0c/-1'):
   with self.assertRaises(ValueError):read(path)
 def test_place_filter_and_retrieval_nonrecursion(self):
  with self.s.db:
   original=self.s.memory.append('area_named',dict(place_id='area:one',before='Old',after='New'))
   self.s.memory.append('area_named',dict(place_id='area:two',before='Old',after='Other'))
   for n in range(30):
    retrieval=self.s.memory.append('actor_tool_result',dict(character_id='reader',tool='world.search_history',result={'copied':'not a new fact'},places=['area:one']))
  result=self.search(dict(place='area:one'));self.assertEqual([r['seq'] for r in result['events']],[original])
  self.assertEqual([e['seq'] for e in self.s.memory.recall(through=self.s.memory.history(limit=1)['through'],places=['area:one'])['events']],[original])
  self.assertFalse(any(r.get('record',{}).get('tool') in history.READ_TOOLS for r in self.search()['events']))
  with self.assertRaises(ValueError):history.read(self.s,'reader',{},dict(sequence=retrieval,path=''))
 def test_invalid_inputs(self):
  for args in (dict(query='[]',after=0,through=0),dict(query='{}',after=True,through=0),dict(query='{}',after=999999,through=0),dict(query='{"actor":"x\' OR 1=1"}',after=0,through=0)):
   with self.assertRaises(ValueError):history.search(self.s,'reader',{},args)

class HistoryRuntimeTests(unittest.TestCase):
 def test_canonical_real_plan_reads_original_then_exposes_receipt_for_replanning(self):
  f=runtime_fixture.ActorRuntimeTests();f.setUp();self.addCleanup(f.doCleanups);s=f.s
  with s.db:
   source=s.memory.append('canonical_letter_delivered',dict(sender='canon_wally',recipient='canon_rydel',text='A remembered proposal.'))
  plan=dict(id='remember',purpose='Consult the original public exchange before choosing what to do.',steps=[
   dict(id='find',tool='world.search_history',args=dict(query=json.dumps(dict(actor='canon_wally',event='canonical_letter_delivered',terms=['remembered'])),after=0,through=0),after=[]),
   dict(id='read',tool='world.read_history',args=dict(sequence=dict(result='find',key='first_sequence'),path='/text'),after=['find'])])
  f.apply(plan)
  self.assertEqual(actor_runtime.tick(s,now=10)['status'],'succeeded')
  self.assertEqual(actor_runtime.tick(s,now=16)['status'],'succeeded')
  detail=s.inspect()['actor_runtime'];receipt=next(p for p in detail['plans'] if p['actor']=='canon_rydel')['receipts'][-1]
  self.assertEqual(receipt['result']['value'],'A remembered proposal.')
  event=json.loads(s.db.execute('SELECT data FROM events WHERE seq=?',(receipt['seq'],)).fetchone()[0])
  self.assertTrue(actor_runtime.relevant(event,'canon_rydel'))
  self.assertFalse(actor_runtime.relevant(event,'canon_wally'))
  self.assertIn('world',detail['capabilities']['world.search_history']['actor_kinds'])
 def test_generated_actor_receives_original_event_without_claiming_observation(self):
  import copy
  import test_actor_navigation as nav
  f=nav.NavigationTests();f.setUp();self.addCleanup(f.doCleanups);s=f.s
  state=copy.deepcopy(s.module_state);c=state['world_characters']['second'];c['version']+=1
  c['plan']=dict(id='research',purpose='Read public history before deciding.',steps=[dict(id='find',tool='world.search_history',args=dict(query='{}',after=0,through=0),after=[])])
  positions=copy.deepcopy(s.objects)
  f.f.commit(dict(state=state,tiles=[],objects=s.objects));self.assertIsNone(s.module_error)
  result=actor_runtime.tick(s,now=10);self.assertEqual(result['status'],'succeeded');self.assertEqual(result['actor'],'second')
  data=json.loads(s.db.execute('SELECT result FROM actor_tool_receipts WHERE actor=?',('second',)).fetchone()[0])
  self.assertTrue(data['events']);self.assertIn('not personal sight',data['limits']);self.assertEqual(s.objects,positions)
