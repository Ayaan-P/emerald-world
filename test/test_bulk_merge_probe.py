import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/bulk_merge_probe.py'
def git(p,*a):return subprocess.run(['git','-C',str(p),*a],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.decode().strip()
def commit(p,msg):
 git(p,'add','-A');git(p,'-c','user.name=Test','-c','user.email=test@invalid','commit','-qm',msg);return git(p,'rev-parse','HEAD')
class BulkMerge(unittest.TestCase):
 def test_carries_clean_change_and_lists_conflict(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);repo=r/'repo';donor=r/'donor';out=r/'out';repo.mkdir();donor.mkdir();git(repo,'init','-q');git(donor,'init','-q')
   (repo/'clean.c').write_text('base\n');(repo/'conflict.c').write_text('base\n');base=commit(repo,'base')
   (repo/'clean.c').write_text('world\n');(repo/'conflict.c').write_text('world\n');world=commit(repo,'world')
   (donor/'clean.c').write_text('base\n');(donor/'conflict.c').write_text('expansion\n');commit(donor,'donor')
   subprocess.run(['python3',str(SCRIPT),'--repo',str(repo),'--donor',str(donor),'--base',base,'--world',world,'--output',str(out)],check=True,stdout=subprocess.PIPE)
   data=json.loads((out/'summary.json').read_text());self.assertEqual(data['conflicted_paths'],1);self.assertIn('conflict.c',(out/'conflicts.txt').read_text())
   patch=(out/'auto-merged.patch').read_text();self.assertIn('+world',patch);self.assertIn('clean.c',patch);self.assertNotIn('conflict.c',patch)
if __name__=='__main__':unittest.main()
