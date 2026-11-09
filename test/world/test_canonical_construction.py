"""Actual autonomous map mutation, no player quest or simulated character travel."""
from copy import deepcopy
import json,tempfile,unittest
from unittest.mock import patch
import test_canonical_cast as fixture
from test_frontier_outposts import base,plan
from world import canonical_construction as build,canonical_cast as cast,character_reactions as reactions
from world.runtime_gm import IntentQueue

class CastConstructionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.blob=base();self.previous=self.s._replace_cave(self.blob,label='Existing Frontier')
  self.place=self.s.memory.place(self.previous)
  self.action=self.f.action();self.action['id']='canon_briney'
  self.action['changes'].update(goal='Make a connected resting courtyard for this frontier',
      dialogue='I have planned a small courtyard off the existing path.',
      worksite=dict(revision=self.previous,label='Briney Courtyard',plan=plan()),
      intentions=[dict(id='resting_court',kind='construction',target=self.previous,
          reason='Provide a usable courtyard without interrupting explorers.')])
  self.f.apply(self.action)
 def test_actual_geometry_commits_without_players_and_informs_owner(self):
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_briney','Reflect on actual work, not imagined travel.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.fetch),[]) # authority owns construction, not model polling
    out=build.step(self.s,now=10);self.assertEqual(out['status'],'completed')
    new=self.s.shared_cave.identity;self.assertNotEqual(new,self.previous)
    self.assertTrue(self.s.shared_cave.walkable(18,23));self.assertTrue(self.s.shared_cave.walkable(15,23))
    self.assertFalse(self.s.shared_cave.walkable(15,22))
    for i,tile in enumerate(self.blob[8:]):
     if tile==ord('.'):self.assertEqual(self.s.shared_cave._rows[i//127][i%127],ord('.'))
    self.assertEqual(self.s.memory.place(new),self.place)
    receipt=self.s.db.execute('SELECT revision,seq FROM canonical_construction_receipts').fetchone()
    self.assertEqual(receipt[0],new)
    event=self.s.memory.history()['events'][-1]
    self.assertEqual((event['event'],event['outcome']),('canonical_construction_completed','connected_courtyard_committed'))
    self.assertEqual(event['character_id'],'canon_briney');self.assertEqual(self.s.objects,[])
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_sessions').fetchone()[0],0)
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    item=q.claim();ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    reaction=reactions.prepare(ctx,self.f.fetch)
    done=deepcopy(self.action);done['expected_version']=1
    done['changes'].update(goal='Consider how the courtyard connects to future routes',
         dialogue='The courtyard is now connected. I am considering where another path would be useful.',
         evidence=[receipt[1]],intentions=[],worksite=None)
    reactions.check_response(dict(canonical_actions=[done],tests='assert True'),reaction);self.f.apply(done)
    self.assertIsNone(build.step(self.s,now=20))
   finally:q.close()
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server
  self.assertEqual(self.s.shared_cave.identity,new)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_construction_receipts').fetchone()[0],1)
  self.assertTrue(self.s.shared_cave.walkable(18,23));self.assertIsNone(build.step(self.s,now=30))
 def test_occupied_waits_then_runs_once_without_player_work(self):
  self.s.peers['Explorer']=dict(id='Explorer',closing=False,in_generated_cave=True,state=None,out=bytearray())
  history=self.s.memory.history()
  out=build.step(self.s,now=10);self.assertEqual(out['status'],'waiting');self.assertIn('occupied',out['reason'])
  self.assertEqual(self.s.shared_cave.identity,self.previous);self.assertEqual(self.s.memory.history(),history)
  self.assertIsNone(build.step(self.s,now=11))
  self.s.peers.pop('Explorer')
  self.assertEqual(build.step(self.s,now=16)['status'],'completed')
  self.assertIsNone(build.step(self.s,now=22));self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_construction_receipts').fetchone()[0],1)
 def test_receipt_failure_rolls_back_geometry_and_history(self):
  history=self.s.memory.history()
  with patch('world.canonical_construction.persist',side_effect=ValueError('receipt rejected')):
   result=build.step(self.s,now=10)
  self.assertEqual(result['status'],'waiting')
  self.assertEqual(self.s.shared_cave.identity,self.previous)
  self.assertEqual(self.s.db.execute('SELECT template FROM generated_cave').fetchone()[0],self.blob)
  self.assertEqual(self.s.memory.history(),history)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_construction_receipts').fetchone()[0],0)
 def test_withdrawal_stale_source_and_manual_success_are_refused(self):
  wrong=deepcopy(self.action);wrong['expected_version']=1
  wrong['changes']['worksite']['revision']='0'*64;self.f.apply(wrong)
  self.assertEqual(build.step(self.s,now=10)['status'],'waiting')
  self.assertEqual(self.s.shared_cave.identity,self.previous)
  fake=deepcopy(wrong);fake['expected_version']=2;fake['changes'].update(fulfill='resting_court',intentions=[])
  with self.assertRaisesRegex(ValueError,'authority geometry'):
   cast.compile_actions([fake],self.f.context())
  withdrawn=deepcopy(wrong);withdrawn['expected_version']=2;withdrawn['changes'].update(intentions=[],worksite=None)
  self.f.apply(withdrawn);self.assertIsNone(build.step(self.s,now=20))
 def test_authority_loop_contains_dispatch_after_mechanics(self):
  import inspect
  source=inspect.getsource(type(self.s)._loop)
  self.assertLess(source.index('self._poll_mechanics()'),source.index('step_cast_construction(self)'))
