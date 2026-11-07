"""Mock model revisions preserve existing world story; no provider calls."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_author_cave import wire
from test_xl_wilds_cast import proposal
from test_xl_wilds_events import CAST,EVENTS
from world import xl_painted_events,xl_versioned_world,xl_revision_author,runtime_gm,author_cave
BLUEPRINT={'rooms':[[1,1,125,125]],'links':[],'entrance_room':0,'exit_room':0}
CANDIDATE={**BLUEPRINT,'paint':[{'x':30,'y':30,'width':5,'height':5,'terrain':'water'}]}
def original():return xl_versioned_world.create(xl_painted_events.encode(proposal(),[],CAST,EVENTS),b'1'*16)
def catalog():return json.dumps({'models':[{'slug':'gpt-6-luna'}]}).encode()
class XLRevisionAuthor(unittest.TestCase):
 def test_theme_revises_terrain_preserving_identity_and_story(self):
  with patch('world.author_cave.gm._run_author',side_effect=[runtime_gm.CODEX_VERSION.encode(),catalog(),wire(CANDIDATE)]) as run:
   result=xl_revision_author.author_revision('flooded ruins',original())
  old=xl_versioned_world.decode(original());new=xl_versioned_world.decode(result)
  self.assertEqual(old[0],new[0]);self.assertEqual(old[2:4],new[2:4]);self.assertNotEqual(old[4],new[4]);prompt=run.call_args_list[-1].args[1]
  self.assertIn('flooded ruins',prompt);self.assertIn('"x":75,"y":20',prompt);self.assertNotIn('Find my friend.',prompt)
 def test_retry_invalid_candidate_and_reject_tool_activity(self):
  bad={**CANDIDATE,'paint':[{'x':75,'y':20,'width':1,'height':1,'terrain':'water'}]}
  with patch('world.author_cave.gm._run_author',side_effect=[runtime_gm.CODEX_VERSION.encode(),catalog(),wire(bad),wire(CANDIDATE)]) as run:
   result=xl_revision_author.author_revision('theme',original(),attempts=2)
  self.assertEqual(result[:8],b'EWGMAP0F');self.assertEqual(run.call_count,4)
  with patch('world.author_cave.gm._run_author',side_effect=[runtime_gm.CODEX_VERSION.encode(),catalog(),b'{"type":"item.completed","item":{"type":"tool_call"}}\n{"type":"turn.completed"}']) as run:
   with self.assertRaises(author_cave.AuthorTransportError):xl_revision_author.author_revision('theme',original(),attempts=3)
   self.assertEqual(run.call_count,3)
 def test_bad_source_and_existing_output_do_not_call_model(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);bad=p/'bad';bad.write_bytes(b'invalid');out=p/'out';out.write_bytes(b'old')
   with patch('world.author_cave.gm._run_author') as run,patch('sys.stderr'):
    with self.assertRaises(SystemExit):xl_revision_author.main(['theme','--previous',str(bad),'--output',str(out),'--replace-output'])
    self.assertEqual(out.read_bytes(),b'old');run.assert_not_called()
   good=p/'good';good.write_bytes(original())
   with patch('world.author_cave.gm._run_author') as run,patch('sys.stderr'):
    with self.assertRaises(SystemExit):xl_revision_author.main(['theme','--previous',str(good),'--output',str(out)])
    self.assertEqual(out.read_bytes(),b'old');run.assert_not_called()
 def test_cli_atomic_revision_preserves_story_and_failure_keeps_old(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/'world';path.write_bytes(original());before=path.read_bytes()
   bad={**CANDIDATE,'paint':[{'x':75,'y':20,'width':1,'height':1,'terrain':'water'}]}
   with patch('world.author_cave.gm._run_author',side_effect=[runtime_gm.CODEX_VERSION.encode(),catalog(),wire(bad),wire(bad)]),patch('sys.stderr'):
    with self.assertRaises(SystemExit):xl_revision_author.main(['theme','--previous',str(path),'--output',str(path),'--replace-output','--attempts','2'])
   self.assertEqual(path.read_bytes(),before)
   with patch('world.author_cave.gm._run_author',side_effect=[runtime_gm.CODEX_VERSION.encode(),catalog(),wire(CANDIDATE)]),patch('builtins.print'):
    xl_revision_author.main(['theme','--previous',str(path),'--output',str(path),'--replace-output'])
   self.assertNotEqual(path.read_bytes(),before);self.assertEqual(xl_versioned_world.decode(path.read_bytes())[0],xl_versioned_world.decode(before)[0])
