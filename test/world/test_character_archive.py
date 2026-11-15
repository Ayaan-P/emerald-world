"""Real authority admission/archive persistence, without provider/native claims."""
from copy import deepcopy
import json
from test_characters import CharacterLifecycleTests
from world.character_archive import recall
from world.characters import records

class ArchiveTests(CharacterLifecycleTests):
 def retired(self,identity):
  row=deepcopy(self.character);row.update(object_id=identity,name=identity,status='retired',goals=[],evidence=[]);return row
 def test_capacity_relationship_replay_restart(self):
  cast={f'old_{i}':self.retired(f'old_{i}') for i in range(32)}
  self.assertIsNone(self.commit(cast))
  # New publication echoes old records, but only previously committed retirement may compact.
  live=deepcopy(self.character);live['relationships']={'old_0':'Former research partner'}
  mixed=dict(cast,may=live)
  self.assertIsNone(self.commit(mixed,self.npc,'tick'))
  self.assertEqual(set(records(self.server.module_state)),{'may'})
  self.assertEqual(self.server.module_state['world_character_archive_refs']['old_0']['name'],'old_0')
  self.assertEqual(self.server.db.execute('SELECT count(*) FROM historical_characters').fetchone()[0],32)
  from world.character_actions import validate_actions
  evidence=self.server.memory.history()['events'][-1]['seq']
  action=dict(id='may',expected_version=1,evidence=[evidence],reason='Continue a remembered partnership',changes={'goals':['Reflect on research']},object=self.npc)
  context=dict(state=self.server.module_state,objects=self.server.objects,world_memory=dict(recent=[{'seq':evidence}]))
  self.assertEqual(validate_actions([action],context),[action])
  saved=recall(self.server,None,None,dict(identity='old_0',after=''))
  self.assertEqual(saved['record'],cast['old_0'])
  self.server.close();self.server=self.open()
  self.assertEqual(recall(self.server,None,None,dict(identity='old_0',after='')),saved)
  # Exact old retired echo is harmless; it cannot consume live capacity again.
  self.assertIsNone(self.commit(mixed,self.npc,'tick'))
  self.assertEqual(len(records(self.server.module_state)),1)
  resurrect=deepcopy(mixed);resurrect['old_0']['status']='active'
  self.assertIn('cannot be changed or reused',self.commit(resurrect,self.npc,'tick'))
  self.assertEqual(recall(self.server,None,None,dict(identity='old_0',after='')),saved)
 def test_failed_admission_does_not_archive(self):
  cast={'old':self.retired('old')};self.assertIsNone(self.commit(cast))
  bad=deepcopy(self.character);bad['relationships']={'forged':'Never registered'}
  self.assertIsNotNone(self.commit({'may':bad},self.npc,'tick'))
  self.assertEqual(self.server.db.execute('SELECT count(*) FROM historical_characters').fetchone()[0],0)
  self.assertIn('old',records(self.server.module_state))
 def test_transaction_rollback_after_archive_insert(self):
  from unittest.mock import patch
  cast={'old':self.retired('old')};self.assertIsNone(self.commit(cast))
  with patch('world.character_companions.commit',side_effect=ValueError('forced downstream failure')):
   self.assertIn('forced downstream failure',self.commit({},kind='tick'))
  self.assertIn('old',records(self.server.module_state))
  self.assertEqual(self.server.db.execute('SELECT count(*) FROM historical_characters').fetchone()[0],0)
  self.assertEqual(self.server.db.execute("SELECT count(*) FROM events WHERE kind='world_memory' AND json_extract(data,'$.event')='character_archived'").fetchone()[0],0)
  self.assertIsNone(self.commit({},kind='deploy'))
  self.assertEqual(recall(self.server,None,None,dict(identity='old',after=''))['record'],cast['old'])
 def test_paged_recall_and_live_identity_not_archived(self):
  cast={f'old_{i:02}':self.retired(f'old_{i:02}') for i in range(17)};self.assertIsNone(self.commit(cast));self.assertIsNone(self.commit({},kind='tick'))
  ids=[];cursor=''
  while True:
   page=recall(self.server,None,None,dict(identity='',after=cursor));ids.extend(x['id'] for x in page['characters'])
   self.assertLessEqual(len(page['characters']),8)
   if not page['has_more']:break
   cursor=page['after']
  self.assertEqual(ids,sorted(cast))
  with self.assertRaises(ValueError):recall(self.server,None,None,dict(identity='missing',after=''))
  self.assertIsNone(self.commit({'may':self.character},self.npc,'tick'))
  self.assertIn('must be retained',self.commit({},kind='tick'))
