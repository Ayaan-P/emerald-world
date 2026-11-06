"""Model-to-XL authoring with mocked provider; no network or model calls."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from world import author_cave, xl_wilds
from test_author_cave import wire

DOC={'rooms':[[2,2,8,8],[90,90,12,12]],'links':[[0,1]],'entrance_room':0,'exit_room':1,'style':'organic','seed':44,'corridor_width':2}
class XLModelAuthor(unittest.TestCase):
 def test_model_response_is_checked_and_compiled_to_xl(self):
  catalog=json.dumps({'models':[{'slug':'gpt-6-luna'}]}).encode()
  with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog,wire(DOC)]) as run:
   proposal,blob=author_cave.author('a forest of islands',large=True,wilds=True,xl=True)
  self.assertEqual(blob,xl_wilds.encode(proposal));self.assertEqual(len(blob),16137);self.assertEqual(len(proposal['rows']),127)
  prompt=run.call_args_list[-1].args[1];self.assertIn('inside coordinates 1..125',prompt);self.assertIn('forest of islands',prompt)
  self.assertIn('features.shell_tool=false',run.call_args_list[-1].args[0]);self.assertIn('web_search="disabled"',run.call_args_list[-1].args[0])
 def test_untrusted_model_invalid_content_never_produces_a_map(self):
  for invalid in ({**DOC,'exec':'evil'}, {**DOC,'rooms':[[2,2,128,10]]}, {**DOC,'links':[]}, {**DOC,'seed':-1}):
   with self.assertRaises(ValueError):author_cave.decode_blueprint_events(wire(invalid),large=True,xl=True)
  with self.assertRaises(ValueError):author_cave.author('x',large=True,wilds=True,xl=True,guide=True)
 def test_explicit_output_and_exclusive_creation(self):
  with tempfile.TemporaryDirectory() as t:
   output=Path(t)/'area.bin'
   with patch('world.author_cave.author',return_value=({'rows':[]},b'area')) as a,patch('builtins.print'):
    self.assertEqual(author_cave.main(['theme','--xl-wilds-output',str(output)]),0)
    self.assertTrue(a.call_args.kwargs['xl']);self.assertTrue(a.call_args.kwargs['large']);self.assertTrue(a.call_args.kwargs['wilds']);self.assertEqual(output.read_bytes(),b'area')
    self.assertEqual(author_cave.main(['theme','--xl-wilds-output',str(output)]),1);self.assertEqual(output.read_bytes(),b'area')
