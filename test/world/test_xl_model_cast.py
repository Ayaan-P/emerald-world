"""Mocked model generation of agent-placed XL cast; no provider calls."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from world import author_cave,xl_wilds_cast
from test_author_cave import wire
DOC={'rooms':[[1,1,125,125]],'links':[],'entrance_room':0,'exit_room':0,'cast':[{'gfx':'boy','x':2,'y':1,'text':'Welcome!'},{'gfx':'girl','x':80,'y':20,'text':'Far away!'}]}
class XLModelCast(unittest.TestCase):
 def test_provider_output_is_validated_and_emits_cast_map(self):
  catalog=json.dumps({'models':[{'slug':'gpt-6-luna'}]}).encode()
  with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog,wire(DOC)]) as run:
   proposal,blob=author_cave.author('island village',large=True,wilds=True,xl=True,cast=True)
  parsed,cast=xl_wilds_cast.validate_wire(blob);self.assertEqual(proposal,parsed);self.assertEqual((cast[1]['x'],cast[1]['y']),(80,20))
  prompt=run.call_args_list[-1].args[1];self.assertIn('"x":2,"y":2',prompt);self.assertIn('distinct integer x and y',prompt)
 def test_invalid_characters_never_compile(self):
  for char in ({'gfx':'boy','x':125,'y':125,'text':'hi'},{'gfx':'boy','x':2,'y':1,'text':'<script>'},{'gfx':'boy','x':2,'y':1,'text':'hi','exec':'bad'}):
   with self.assertRaises(ValueError):author_cave.decode_blueprint_events(wire({**DOC,'cast':[char]}),large=True,xl=True,cast=True)
 def test_cli_explicit_xl_cast_target(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/'world.bin'
   with patch('world.author_cave.author',return_value=({'rows':[]},b'world')) as a,patch('builtins.print'):
    self.assertEqual(author_cave.main(['theme','--xl-cast-wilds-output',str(path)]),0)
    self.assertTrue(a.call_args.kwargs['xl']);self.assertTrue(a.call_args.kwargs['cast']);self.assertEqual(path.read_bytes(),b'world')
