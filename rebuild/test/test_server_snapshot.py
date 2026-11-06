"""Exercise the real authority's snapshot formatting without opening sockets."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
REPO=Path(os.environ.get('EW_REPO_ROOT',ROOT.parent)).resolve()
sys.path.insert(0,str(REPO))
# Compile the actual snapshot method alone so the test does not start a server.
module=ast.parse((REPO/'world/server.py').read_text())
server_class=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='WorldServer')
method=next(n for n in server_class.body if isinstance(n,ast.FunctionDef) and n.name=='_snapshot')
namespace={'MAX_PEERS':8}
exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(REPO/'world/server.py'),'exec'),namespace)
class WorldServer:
 _snapshot=namespace['_snapshot']

class SnapshotInterop(unittest.TestCase):
 def test_real_snapshot_survives_fragmented_wire_input(self):
  server=WorldServer.__new__(WorldServer)
  server.revision=42;server.cave_map=None;server.wilds_map=None;server.shared_cave=None
  server.tiles=[];server.objects=[]
  class Rally:
   def snapshot(self,conn):return []
  server.rally=Rally()
  alice={'id':'Alice','state':[0,9,4,6,1,7,1],'social':True,'field':True,'peer_limit':8}
  bob={'id':'Bob','state':[0,9,5,6,2,7,1],'field':True,'closing':False}
  server.peers={'Alice':alice,'Bob':bob}
  snapshot=server._snapshot(alice)
  with tempfile.TemporaryDirectory() as d:
   binary=Path(d)/'reader'
   build=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'overlay/include'),str(ROOT/'overlay/src/world/presence_wire.c'),str(ROOT/'test/wire_reader.c'),'-o',str(binary)],capture_output=True,text=True)
   self.assertEqual(build.returncode,0,build.stderr)
   run=subprocess.run([str(binary)],input='WELCOME 1 Alice 42\n'+snapshot,text=True,capture_output=True)
   self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stdout,'1 Bob 5 6\n')
if __name__=='__main__':unittest.main()
