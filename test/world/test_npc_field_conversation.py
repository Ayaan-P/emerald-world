import importlib.util,os,pathlib,subprocess,tempfile,unittest
import test_npc_conversations
from world import actor_runtime as runtime,npc_conversations as speech

class PairedComposerTests(unittest.TestCase):
 def test_actual_c_menu_and_editor_command_authority_reply_wire(self):
  root=pathlib.Path(os.environ.get('EW_NPC_CHAT_NATIVE_SOURCE',pathlib.Path(__file__).resolve().parents[3]/'native-npc-conversation'))
  path=root/'tests/test_npc_composer.py'
  if not path.exists():self.skipTest('Requires paired native NPC composer sources')
  spec=importlib.util.spec_from_file_location('npc_composer_fixture',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as td:
   command=subprocess.run([str(module.build(td))],check=True,capture_output=True,text=True).stdout.strip()
  f=test_npc_conversations.ConversationTests();f.setUp();self.addCleanup(f.doCleanups)
  f.f.send(f.peer,'CHAT %s * %s'%(f.peer['seq']+1,command.encode().hex()))
  seq=f.s.db.execute('SELECT seq FROM npc_public_speech').fetchone()[0]
  f.plan(seq);self.assertEqual(runtime.tick(f.s,now=10)['status'],'succeeded');speech.flush(f.s)
  self.assertIn('considering where'.encode().hex().encode(),f.peer['out'])
