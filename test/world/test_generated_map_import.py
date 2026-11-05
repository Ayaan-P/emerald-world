"""Exercise proposal export and the actual native template loader."""
from pathlib import Path
import importlib.util, json, subprocess, tempfile, unittest
from test_save_isolation import function
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('cave_export',ROOT/'scripts/export_generated_cave.py')
export=importlib.util.module_from_spec(spec);spec.loader.exec_module(export)

class GeneratedMapImport(unittest.TestCase):
 def setUp(self):
  self.rows=['#'*31]+['#'+'.'*29+'#']*29+['#'*31]
  self.doc={'rows':self.rows,'spawn':[1,1],'exit':[29,29]}
 def test_validation_rejects_disconnected_and_bad_payloads(self):
  encoded=export.encode(self.doc);self.assertEqual(len(encoded),969);self.assertTrue(encoded.startswith(b'EWGMAP01'))
  for change in ({'spawn':[True,1]}, {'exit':[3,3]}, {'unexpected':1}, {'rows':['.'*31]*31}):
   with self.subTest(change=change),self.assertRaises(ValueError): export.encode({**self.doc,**change})
  rows=[list(x) for x in self.rows]
  for x,y in ((9,10),(11,10),(10,9),(10,11)): rows[y][x]='#'
  with self.assertRaises(ValueError): export.encode({**self.doc,'rows':[''.join(row) for row in rows]})
 def test_cli_wont_overwrite_existing_file(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'in.json').write_text(json.dumps(self.doc));(p/'out.bin').write_bytes(b'keep')
   q=subprocess.run(['python3',str(ROOT/'scripts/export_generated_cave.py'),str(p/'in.json'),str(p/'out.bin')],capture_output=True)
   self.assertNotEqual(q.returncode,0);self.assertEqual((p/'out.bin').read_bytes(),b'keep')
   q=subprocess.run(['python3',str(ROOT/'scripts/export_generated_cave.py'),'--replace',str(p/'in.json'),str(p/'out.bin')],capture_output=True)
   self.assertEqual(q.returncode,0,q.stderr);self.assertEqual((p/'out.bin').read_bytes(),export.encode(self.doc))
   original=(p/'in.json').read_bytes()
   q=subprocess.run(['python3',str(ROOT/'scripts/export_generated_cave.py'),'--replace',str(p/'in.json'),str(p/'in.json')],capture_output=True)
   self.assertNotEqual(q.returncode,0);self.assertEqual((p/'in.json').read_bytes(),original)
   (p/'out.bin').unlink();q=subprocess.run(['python3',str(ROOT/'scripts/export_generated_cave.py'),str(p/'in.json'),str(p/'out.bin')],capture_output=True)
   self.assertEqual(q.returncode,0,q.stderr);self.assertEqual((p/'out.bin').read_bytes(),export.encode(self.doc))
 def test_native_loader_checks_magic_exact_length_and_stage(self):
  source=(ROOT/'src/platform/sdl2.c').read_text()
  body=function(source,'LoadGeneratedMapTemplate')+function(source,'Platform_ReloadGeneratedMap')
  code=r'''
#include <assert.h>
#include <stdio.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;typedef int bool8;
#define FALSE 0
#define GENERATED_MAP_TEMPLATE_BYTES 961
static int stageCalls;
static const char *sGeneratedMapPath;
FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
bool8 GeneratedMap_StageTemplate(const u8 *p,unsigned n){stageCalls++;return n==961 && p[0]=='#';}
'''+body+r'''
int main(int argc,char **argv){
 assert(argc==4);assert(Platform_ReloadGeneratedMap() && !stageCalls);
 sGeneratedMapPath=argv[1];assert(Platform_ReloadGeneratedMap() && stageCalls==1);
 assert(!LoadGeneratedMapTemplate(argv[2])&&stageCalls==1);assert(!LoadGeneratedMapTemplate(argv[3])&&stageCalls==1);
 FILE *f=fopen(argv[1],"wb");assert(f);assert(fwrite("invalid",1,7,f)==7);assert(!fclose(f));
 assert(!Platform_ReloadGeneratedMap() && stageCalls==1);return 0;
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code);(p/'ok').write_bytes(export.encode(self.doc));(p/'bad').write_bytes(b'BADMAGIC'+b'#'*961);(p/'long').write_bytes(export.encode(self.doc)+b'x')
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test'),str(p/'ok'),str(p/'bad'),str(p/'long')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
