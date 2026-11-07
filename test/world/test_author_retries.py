"""Opt-in bounded model candidate retries; all provider calls mocked."""
import json,unittest
from unittest.mock import patch
from world import author_cave
from test_author_cave import wire
from test_xl_model_events import DOC
PAINT=[{'x':30,'y':30,'width':5,'height':4,'terrain':'tall_grass'}]
def catalog():return json.dumps({'models':[{'slug':'gpt-6-luna'}]}).encode()
class AuthorRetries(unittest.TestCase):
 def test_invalid_candidate_retried_without_echo_then_valid_succeeds(self):
  bad={**DOC,'paint':[{'x':1,'y':1,'width':1,'height':1,'terrain':'water'}],'secret_extra':'DO_NOT_ECHO'};good={**DOC,'paint':PAINT}
  with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog(),wire(bad),wire(good)]) as run:
   _,blob=author_cave.author('an island',large=True,wilds=True,xl=True,cast=True,events=True,painted=True,attempts=2)
  self.assertEqual(blob[:8],b'EWGMAP0E');self.assertEqual(run.call_count,4);retry=run.call_args_list[-1].args[1]
  self.assertIn('previous candidate failed validation',retry);self.assertNotIn('DO_NOT_ECHO',retry)
 def test_tool_activity_and_provider_failure_never_retry(self):
  for bad in (b'{"type":"item.completed","item":{"type":"tool_call"}}\n{"type":"turn.completed"}',b'{"type":"turn.failed"}',b'not json'):
   with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog(),bad]) as run:
    with self.assertRaises(author_cave.AuthorTransportError):author_cave.author('island',attempts=3)
    self.assertEqual(run.call_count,3)
 def test_limits_and_default_one_candidate(self):
  with patch('world.author_cave.gm._run_author') as run:
   for count in (0,4,True):
    with self.assertRaises(ValueError):author_cave.author('x',attempts=count)
   run.assert_not_called()
  with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog(),wire({'bad':'schema'})]) as run:
   with self.assertRaises(ValueError):author_cave.author('x')
   self.assertEqual(run.call_count,3)
 def test_timeout_never_retries(self):
  with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog(),TimeoutError()]) as run:
   with self.assertRaises(TimeoutError):author_cave.author('x',attempts=3)
   self.assertEqual(run.call_count,3)
 def test_failed_candidates_never_replace_existing_output(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as t:
   out=Path(t)/'map';out.write_bytes(b'old')
   with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog(),wire({'bad':'one'}),wire({'bad':'two'})]),patch('builtins.print'):
    self.assertEqual(author_cave.main(['island','--xl-painted-events-output',str(out),'--replace-output','--attempts','2']),1)
   self.assertEqual(out.read_bytes(),b'old')
