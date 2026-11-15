import sqlite3,unittest
from world import contest_results as result,contest_guests as guest
from test_contest_guests import ContestGuests
class Reports(unittest.TestCase):
 def setUp(self):
  self.f=ContestGuests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.p=self.f.peer();self.p['campaign_run']='saveA';self.c=dict(id='Alice',presence=self.p)
  with self.s.db:guest.configure(self.s,'harbor_guide',{},dict(category='cool',individual='partner'))
  self.rev=guest.available(self.s)[0]['revision']
 def join(self):
  out=result.handle(self.s,self.c,f'C JOIN 1 harbor_guide {self.rev} 0'.encode());self.assertTrue(out.startswith('C ADMIT '),out);return out.split()[2]
 def test_result_identity_no_state_mutation_and_replay(self):
  lease=self.join();before=self.s.module_state.copy();out=result.handle(self.s,self.c,f'C RESULT {lease} 0'.encode());self.assertEqual(out,f'C ACK {lease}\n');self.assertEqual(before,self.s.module_state)
  count=self.s.db.execute('SELECT count(*) FROM events').fetchone()[0]
  self.assertEqual(result.handle(self.s,self.c,f'C RESULT {lease} 0'.encode()),out)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM events').fetchone()[0],count)
  self.assertIn('ERROR',result.handle(self.s,self.c,f'C RESULT {lease} 1'.encode()))
 def test_save_identity_and_restart(self):
  lease=self.join();self.p['campaign_run']='saveB';self.assertIn('ERROR',result.handle(self.s,self.c,f'C RESULT {lease} 2'.encode()));self.p['campaign_run']='saveA'
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:self.assertIn('ACK',result.handle(self.s,self.c,f'C RESULT {lease} 2'.encode()))
  finally:self.s.db=old;db.close()
 def test_no_admission_no_result(self):
  self.assertIn('ERROR',result.handle(self.s,self.c,b'C RESULT fake 0'))
  self.p['contest_guest_capable']=False
  self.assertIn('ERROR',result.handle(self.s,self.c,f'C JOIN 1 harbor_guide {self.rev} 0'.encode()))
 def test_changed_individual_record_not_overwritten(self):
  from unittest.mock import patch
  from world.character_reactions import dynamic_result
  lease=self.join()
  with patch('world.character_training.source',return_value={'different':'state'}):
   self.assertIn('ACK',result.handle(self.s,self.c,f'C RESULT {lease} 1'.encode()))
  import json
  event=json.loads(self.s.db.execute("SELECT data FROM events WHERE kind='world_memory' ORDER BY seq DESC LIMIT 1").fetchone()[0])
  self.assertFalse(event['individual_unchanged']);self.assertEqual(event['placing'],2)
  self.assertNotIn('trainer',event);self.assertNotIn('lineage',event)
  self.assertTrue(dynamic_result(event,'harbor_guide',{}));self.assertFalse(result.relevant(event,'other'))
