"""Model wire is untrusted data. No real provider call or publication."""
import json
import unittest
from unittest.mock import patch
from world import author_cave
from scripts.export_generated_cave import encode

DOC={'rooms':[[2,2,4,4],[20,20,5,5]], 'links':[[0,1]], 'entrance_room':0, 'exit_room':1}
def wire(doc=DOC):
 return '\n'.join(json.dumps(x) for x in [
  {'type':'item.completed','item':{'type':'agent_message','text':json.dumps(doc)}},
  {'type':'turn.completed'}]).encode()

class CaveAuthor(unittest.TestCase):
 def test_success_uses_locked_model_and_validates(self):
  catalog=json.dumps({'models':[{'slug':'gpt-6-luna'}]}).encode()
  with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog,wire()]) as run:
   proposal, blob=author_cave.author('icy chamber')
  self.assertEqual(blob,encode(proposal)); self.assertEqual(run.call_count,3)
  final=run.call_args_list[-1];self.assertIn('features.shell_tool=false',final.args[0]);self.assertIn('icy chamber',final.args[1]);self.assertIn('web_search="disabled"',final.args[0])
 def test_rejects_failed_or_tool_events_and_invalid_geometry(self):
  bad=[b'',b'{"type":"turn.failed"}', b'{"type":"item.completed","item":{"type":"tool_call"}}',wire({**DOC,'links':[]}),wire({**DOC,'exec':'evil'})]
  for item in bad:
   with self.subTest(item=item),self.assertRaises(ValueError):author_cave.decode_blueprint_events(item)
 def test_no_provider_call_for_invalid_theme_or_unsafe_version(self):
  with patch('world.author_cave.gm._run_author') as run:
   with self.assertRaises(ValueError):author_cave.author('x'*2001)
   run.assert_not_called()
  with patch('world.author_cave.gm._run_author',return_value=b'codex-cli unknown') as run:
   with self.assertRaises(ValueError):author_cave.author('theme')
   self.assertEqual(run.call_count,1)
 def test_preview_vs_explicit_publish(self):
  with patch('world.author_cave.author',return_value=({'rows':[]},b'blob')), patch('world.author_cave.publish_bytes') as pub, patch('builtins.print'):
   self.assertEqual(author_cave.main(['theme']),0);pub.assert_not_called()
   pub.return_value='id';self.assertEqual(author_cave.main(['theme','--admin-socket','/tmp/admin.sock']),0);pub.assert_called_once()

if __name__ == '__main__':unittest.main()
