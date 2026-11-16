import ast, pathlib,sqlite3,sys,tempfile,time,types,unittest,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/world/world_berry_care.c').exists() else ROOT/'engines/expansion-native'
pkg=types.ModuleType('soil_fixture');pkg.__path__=[str(ROOT/'world')];sys.modules['soil_fixture']=pkg
from soil_fixture import berry_care as r
class Care(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=pathlib.Path(self.tmp.name)/'world.db';self.db=sqlite3.connect(self.path);self.addCleanup(self.db.close)
  self.peer={'id':'a','state':[0,19,34,7,2,0,1],'state_time':time.monotonic()};self.ch={'id':'a','presence':self.peer,'sock':1};self.out=[]
  self.s=types.SimpleNamespace(db=self.db,peers={'a':self.peer},link_channels={'a':self.ch},connections={1:True},link_protocol=types.SimpleNamespace(sessions=types.SimpleNamespace(_locks={}),_encounters={}),_queue=lambda c,text:self.out.append(text))
 def test_persistence_replay_and_expiration(self):
  self.assertEqual(r.handle(self.s,self.ch,b'BC WATER 1 8 1'),'BC STORED 1\n');before=self.db.execute('select expires from shared_soil_care').fetchone()[0]
  self.assertEqual(r.handle(self.s,self.ch,b'BC WATER 1 8 1'),'BC STORED 1\n');self.assertEqual(before,self.db.execute('select expires from shared_soil_care').fetchone()[0])
  other=sqlite3.connect(self.path);self.assertEqual(other.execute('select plot,stage from shared_soil_care').fetchone(),(8,1));other.close()
  self.assertEqual(r.handle(self.s,self.ch,b'BC GET 2 8 1'),'BC CARE 2 8 1\n');self.assertEqual(r.handle(self.s,self.ch,b'BC GET 3 8 2'),'BC NONE 3\n')
  self.db.execute('update shared_soil_care set expires=0');self.assertEqual(r.handle(self.s,self.ch,b'BC GET 4 8 1'),'BC NONE 4\n')
 def test_authentication_native_context_and_facing(self):
  for line in [b'BC WATER 1 127 1',b'BC WATER 1 8 5',b'BC WATER 0 8 1',b'BC WATER 4294967296 8 1']:self.assertEqual(r.handle(self.s,self.ch,line),'BC FAIL\n')
  self.peer['state'][4]=1;self.assertEqual(r.handle(self.s,self.ch,b'BC WATER 1 8 1'),'BC FAIL\n');self.peer['state'][4]=2
  self.s.link_protocol._encounters['a']=object();self.assertEqual(r.handle(self.s,self.ch,b'BC WATER 1 8 1'),'BC FAIL\n');self.s.link_protocol._encounters.clear()
  self.s.link_channels['a']=dict(self.ch);self.assertEqual(r.handle(self.s,self.ch,b'BC WATER 1 8 1'),'BC FAIL\n')
 def test_actual_dispatch_queues_response(self):
  sys.modules['soil_fixture.combined_regions']=types.SimpleNamespace(pending=lambda *args:False)
  tree=ast.parse((ROOT/'world/server.py').read_text());method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_link_line');ns={'__package__':'soil_fixture'};exec(compile(ast.Module(body=[method],type_ignores=[]),'actual_dispatch','exec'),ns)
  ns['_link_line'](self.s,self.ch,b'BC WATER 1 8 1');self.assertEqual(self.out,['BC STORED 1\n'])
 def test_native_core_enabled_disabled(self):
  with tempfile.TemporaryDirectory() as name:
   d=pathlib.Path(name);(d/'platform').mkdir();(d/'constants').mkdir()
   for p in ['global.h','main.h','overworld.h','script.h','palette.h','event_object_movement.h','field_player_avatar.h','platform/world_berry_care.h','platform/native_link.h','platform/generated_map.h','platform/world_bridge.h','constants/maps.h']:(d/p).write_text('')
   (d/'platform/berry_care_plots.h').write_text((NATIVE/'include/platform/berry_care_plots.h').read_text())
   (d/'test.c').write_text((ROOT/'test/native_care.c').read_text().replace('ACTUAL_SOURCE',str(NATIVE/'src/world/world_berry_care.c')))
   for enabled in (0,1):
    subprocess.run(['cc','-std=c99','-DPORTABLE',f'-DEW_SHARED_SOIL_CARE={enabled}','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_actual_stock_yield_and_source_preservation(self):
  import hashlib
  source=(NATIVE/'src/berry.c').read_text()
  original=source.replace('#include "platform/world_berry_care.h"\n','').replace('    WorldBerryCare_Watered(GetObjectEventBerryTreeId(gSelectedObjectEvent), tree->stage);\n','')
  data=original.encode();self.assertEqual(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),'3b461f96ca9968a0186cb9d4dd8352f15ec05239')
  def function(name):
   start=source.index(name+'\n{');begin=source.rfind('static ',0,start);end=source.index('\n}',start)+2;return source[begin:end]
  helpers=function('BerryTreeGetNumStagesWatered(struct BerryTree *tree)')+'\n'+function('CalcBerryYieldInternal(u16 max, u16 min, u8 water)')
  fixture='#include <assert.h>\ntypedef unsigned char u8;typedef unsigned short u16;typedef unsigned u32;struct BerryTree{unsigned watered;};\n#define OW_BERRY_MOISTURE 0\n#define NUM_WATER_STAGES 4\nstatic unsigned rng;static unsigned Random(void){return rng;}\n'+helpers+'\nint main(void){struct BerryTree t={0};assert(CalcBerryYieldInternal(6,2,BerryTreeGetNumStagesWatered(&t))==2);t.watered=15;for(rng=0;rng<100;rng++)assert(CalcBerryYieldInternal(6,2,BerryTreeGetNumStagesWatered(&t))>=5);return 0;}'
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);(d/'test.c').write_text(fixture);subprocess.run(['cc','-fsanitize=undefined',str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_hooks_and_private_ownership(self):
  berry=(NATIVE/'src/berry.c').read_text();self.assertEqual(berry.count('WorldBerryCare_Watered('),1)
  water=berry[berry.index('bool32 ObjectEventInteractionWaterBerryTree(void)'):berry.index('bool8 IsPlayerFacingEmptyBerryTreePatch')];self.assertIn('default:\n        return FALSE;',water);self.assertLess(water.index('default:'),water.index('WorldBerryCare_Watered'))
  source=(NATIVE/'src/world/world_berry_care.c').read_text();self.assertNotIn('AddBagItem',source);self.assertNotIn('RemoveBagItem',source);self.assertIn('tree->watered|=1U<<(stage-1)',source)
  transport=(NATIVE/'src/world/link_transport.c').read_text()
  for hook in ['WorldBerryCare_Pump();','WorldBerryCare_Reset();','WorldBerryCare_Line(n,t);']:self.assertIn(hook,transport)
  chat=(NATIVE/'src/world/world_chat.c').read_text();self.assertLess(chat.index('EW_SHARED_SOIL_CARE && !WorldFieldUI_Active() && event'),chat.index('    if (WorldFieldUI_Active()) {'))
if __name__=='__main__':unittest.main()
