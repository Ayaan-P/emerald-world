import ast, importlib.util, pathlib, subprocess, sys, tempfile, time, types, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class InvitationTests(unittest.TestCase):
 def test_native_queue_and_cancellation(self):
  with tempfile.TemporaryDirectory() as d:
   for flag in (0,1):
    exe=pathlib.Path(d)/str(flag)
    native=ROOT/'src/world/wally_invitation.inc.c'
    if not native.exists():native=ROOT/'engines/expansion-native/src/world/wally_invitation.inc.c'
    fixture=ROOT/'tests/native_invitation.c'
    if not fixture.exists():fixture=ROOT/'test/native_invitation.c'
    source=pathlib.Path(d)/'fixture.c'
    source.write_text(fixture.read_text().replace('../src/world/wally_invitation.inc.c',str(native)))
    subprocess.run(['cc','-std=c99','-fsanitize=undefined',f'-DEW_WALLY_INVITATION={flag}',str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
 def test_exact_authority_gate(self):
  # Execute the existing real handler, without constructing unrelated world systems.
  pkg=types.ModuleType('wallyfixture');pkg.__path__=[];sys.modules['wallyfixture']=pkg
  cast=types.ModuleType('wallyfixture.canonical_cast');sys.modules[cast.__name__]=cast
  cast.records=lambda state:state
  cast.check_actor_location=lambda server,conn,actor: None if conn['map']=='VictoryRoad_1F' else (_ for _ in ()).throw(ValueError('map'))
  path=ROOT/'world/core_story.py'
  if not path.exists():path=ROOT/'world/core_story.py'
  spec=importlib.util.spec_from_file_location('wallyfixture.core_story',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  run='a'*32;conn={'id':'owner','core_story_capable':True,'core_active_run':run,'state':[0]*6+[1], 'map':'VictoryRoad_1F','canonical_location':dict(actor='canon_wally',map='VictoryRoad_1F',run=run,version=2,expires=time.monotonic()+60)}
  server=types.SimpleNamespace(peers={'owner':conn},module_state={'canon_wally':dict(rematch='wally_native',version=2)})
  handler=m.CoreStory.__new__(m.CoreStory);handler.s=server
  call=lambda:handler.handle(conn,['CORE',run,'REMATCH','wally','confirm'])
  self.assertEqual(call(),{'ok':True})
  for field,value in [('version',1),('run','b'*32),('expires',0),('map','VerdanturfTown_WandasHouse')]:
   old=conn['canonical_location'][field];conn['canonical_location'][field]=value
   with self.assertRaises(ValueError):call()
   conn['canonical_location'][field]=old
  server.module_state['canon_wally'].pop('rematch')
  with self.assertRaises(ValueError):call()
  server.module_state['canon_wally']['rematch']='wally_native';conn['state'][6]=0
  with self.assertRaises(ValueError):call()
  conn['state'][6]=1;server.peers['owner']=dict(conn)
  with self.assertRaises(ValueError):call()
 def test_production_wiring(self):
  native=ROOT/'src/world/world_core_story.c'
  if not native.exists():native=ROOT/'engines/expansion-native/src/world/world_core_story.c'
  s=native.read_text();self.assertIn('#include "wally_invitation.inc.c"',s)
  self.assertIn('WallyInvitation_Update();',s)
  self.assertIn('if(sCore.rematchPending && !WallyInvitation_Pending())',s)
  self.assertIn('if(WallyInvitation_Frame())return TRUE;',s)
  self.assertIn('if(WallyInvitation_OwnsInput())return keys&(A_BUTTON|B_BUTTON);',s)
  self.assertIn('EW_WALLY_INVITATION ?= 0',(ROOT/'engines/expansion.mk').read_text())
  self.assertIn('EW_WALLY_INVITATION={int(args.experimental_wally_invitation)}',(ROOT/'scripts/build_expansion.py').read_text())
if __name__=='__main__':unittest.main()
