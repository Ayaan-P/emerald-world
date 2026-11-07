"""Mock model-authored XL state graph; no real provider invocation."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_author_cave import wire
from world import author_cave,xl_wilds_events
DOC={'rooms':[[1,1,125,125]],'links':[],'entrance_room':0,'exit_room':0,'cast':[{'gfx':'boy','x':2,'y':1,'text':'Hello!'}, {'gfx':'girl','x':75,'y':20,'text':'Hello!'}], 'events':{'initial':0,'rules':[{'state':0,'npc':1,'next':1,'text':'Find my friend.'},{'state':1,'npc':2,'next':2,'text':'I am fine!'}]}}
class XLModelEvents(unittest.TestCase):
 def test_model_output_builds_a_valid_event_map(self):
  catalog=json.dumps({'models':[{'slug':'gpt-6-luna'}]}).encode()
  with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog,wire(DOC)]) as run:
   proposal,blob=author_cave.author('an island mystery',large=True,wilds=True,xl=True,cast=True,events=True)
  self.assertEqual(blob[:8],b'EWGMAP0C');self.assertEqual(len(blob),17787);self.assertEqual(len(proposal['rows']),127)
  prompt=run.call_args_list[-1].args[1];self.assertIn('events.rules',prompt);self.assertIn('an island mystery',prompt);self.assertIn('"events"',prompt)
 def test_invalid_rules_or_unsafe_text_are_rejected(self):
  bad=[{'initial':0,'rules':[{'state':0,'npc':3,'next':1,'text':'hello'}]}, {'initial':0,'rules':[{'state':0,'npc':1,'next':1,'text':'<script>'}]}, {'initial':0,'rules':[DOC['events']['rules'][0]]*2}]
  for graph in bad:
   with self.assertRaises(ValueError):author_cave.decode_blueprint_events(wire({**DOC,'events':graph}),large=True,xl=True,cast=True,events=True)
 def test_cli_requires_explicit_output(self):
  with tempfile.TemporaryDirectory() as t:
   out=Path(t)/'map.bin'
   with patch('world.author_cave.author',return_value=({'rows':[]},b'map')) as a,patch('builtins.print'):
    self.assertEqual(author_cave.main(['theme','--xl-events-wilds-output',str(out)]),0)
    self.assertTrue(a.call_args.kwargs['events']);self.assertTrue(a.call_args.kwargs['xl']);self.assertTrue(a.call_args.kwargs['cast']);self.assertEqual(out.read_bytes(),b'map')
