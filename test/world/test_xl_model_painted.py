"""Mock model-authored painted XL story maps; no provider calls."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_author_cave import wire
from test_xl_model_events import DOC
from world import author_cave
PAINT=[{'x':30,'y':30,'width':5,'height':4,'terrain':'tall_grass'}]
class XLModelPainted(unittest.TestCase):
 def test_theme_compiles_bounded_paint_characters_and_graph(self):
  catalog=json.dumps({'models':[{'slug':'gpt-6-luna'}]}).encode()
  with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog,wire({**DOC,'paint':PAINT})]) as run:
   proposal,blob=author_cave.author('a strange island',large=True,wilds=True,xl=True,cast=True,events=True,painted=True)
  self.assertEqual(len(proposal['rows']),127);self.assertEqual(blob[:8],b'EWGMAP0E');self.assertEqual(blob[-16129+30*127+30],ord('t'))
  prompt=run.call_args_list[-1].args[1];self.assertIn('"paint"',prompt);self.assertIn('events.rules',prompt);self.assertIn('a strange island',prompt)
 def test_invalid_paint_never_compiles(self):
  for paint in ([{'x':125,'y':125,'width':1,'height':1,'terrain':'water'}],[{'x':75,'y':20,'width':1,'height':1,'terrain':'water'}],[{'x':1,'y':1,'width':1,'height':1,'terrain':'code'}]):
   with self.assertRaises(ValueError):author_cave.decode_blueprint_events(wire({**DOC,'paint':paint}),large=True,xl=True,cast=True,events=True,painted=True)
 def test_explicit_cli_can_refresh_existing_output(self):
  with tempfile.TemporaryDirectory() as t:
   out=Path(t)/'map';out.write_bytes(b'old')
   with patch('world.author_cave.author',return_value=({'rows':[]},b'new')) as a,patch('builtins.print'):
    self.assertEqual(author_cave.main(['theme','--xl-painted-events-output',str(out),'--replace-output']),0)
    self.assertTrue(a.call_args.kwargs['painted']);self.assertTrue(a.call_args.kwargs['events']);self.assertEqual(out.read_bytes(),b'new')
