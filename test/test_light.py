import ast,importlib.util,pathlib,sys,subprocess,tempfile,time,types,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/world/world_cave_light.c').exists() else ROOT/'engines/expansion-native'
spec=importlib.util.spec_from_file_location('light',ROOT/'world/cave_light.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Light(unittest.TestCase):
 def setUp(self):
  self.a={'id':'a','sock':1,'presence':{'state':[24,2,0,0,1,0,1],'state_time':time.monotonic(),'cave_light_visit':1}}
  self.b={'id':'b','sock':2,'presence':{'state':[24,2,2,0,1,0,1],'state_time':time.monotonic(),'cave_light_visit':1}}
  tag=types.SimpleNamespace(active=True,coop_wire=None,participants=('a','b'))
  self.s=types.SimpleNamespace(peers={'a':self.a['presence'],'b':self.b['presence']},connections={1,2},link_channels={'a':self.a,'b':self.b},link_protocol=types.SimpleNamespace(_tags={'tag':tag},_tag_actor={'a':'tag','b':'tag'},sessions=types.SimpleNamespace(_locks={}),_encounters={}))
 def send(self,c,lit=0,enabled=1,epoch=1):return m.handle(self.s,c,f'FL STATE {epoch} {enabled} {lit}'.encode())
 def test_light_is_opt_in_nearby_and_tagged(self):
  self.send(self.a,1);self.assertEqual(self.send(self.b),'FL LIGHT 1 1\n');self.assertEqual(self.send(self.b,enabled=0),'FL LIGHT 1 0\n');self.b['presence']['state'][2]=6;self.assertEqual(self.send(self.b),'FL LIGHT 1 0\n');self.b['presence']['state'][2]=2;self.s.link_protocol._tags['tag'].active=False;self.assertEqual(self.send(self.b),'FL LIGHT 1 0\n')
 def test_map_visit_and_timeout(self):
  self.send(self.a,1);self.a['presence']['cave_light_visit']=2;self.assertEqual(self.send(self.b),'FL LIGHT 1 0\n');self.send(self.a,1,epoch=2);self.assertEqual(self.send(self.b),'FL LIGHT 1 1\n');self.a['cave_light']['time']-=2;self.assertEqual(self.send(self.b),'FL LIGHT 1 0\n')
 def test_session_and_battle(self):
  self.send(self.a,1);self.s.link_protocol._encounters['a']=object();self.assertEqual(self.send(self.b),'FL LIGHT 1 0\n');self.s.link_protocol._encounters.clear();self.s.connections.remove(1);self.assertEqual(self.send(self.b),'FL LIGHT 1 0\n');self.assertEqual(self.send(dict(self.b)),'FL FAIL\n')
 def test_native_lifecycle(self):
  with tempfile.TemporaryDirectory() as path:
   d=pathlib.Path(path);(d/'platform').mkdir();(d/'constants').mkdir()
   for h in ['global.h','main.h','overworld.h','event_data.h','script.h','palette.h','platform/world_cave_light.h','platform/world_bridge.h','platform/native_link.h','platform/generated_map.h','constants/maps.h','constants/flags.h']:(d/h).write_text('')
   (d/'test.c').write_text((ROOT/'test/native_light.c').read_text().replace('ACTUAL_SOURCE',str(NATIVE/'src/world/world_cave_light.c')))
   for flag in (0,1):
    subprocess.run(['cc','-std=c99','-DPORTABLE',f'-DEW_SHARED_CAVE_LIGHT={flag}','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_actual_server_dispatch(self):
  package=types.ModuleType('fixture');package.__path__=[];sys.modules['fixture']=package;sys.modules['fixture.cave_light']=m
  method=next(n for n in ast.walk(ast.parse((ROOT/'world/server.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='_link_line');ns={'__package__':'fixture'};exec(compile(ast.Module(body=[method],type_ignores=[]),'dispatch','exec'),ns)
  out=[];self.s._queue=lambda c,v:out.append(v);self.s._error=lambda *a:None;ns['_link_line'](self.s,self.a,b'FL STATE 1 1 1');self.assertEqual(out,['FL LIGHT 1 0\n'])
 def test_actual_runtime_renderer_has_no_save_mutation(self):
  code=(NATIVE/'src/field_screen_effect.c').read_text();body=code[code.index('int WorldLight_Render(int bright)'):]
  harness="""
#include <assert.h>
typedef unsigned char u8;
#define DISPLAY_WIDTH 240
#define DISPLAY_HEIGHT 160
static int level=1,task,drawn=-1,copied,restored;
static int gMaxFlashLevel=8,sFlashLevelToRadius[]={200,72,64,56,48,40,32,24,0};
static unsigned short gScanlineEffectRegBuffers[2][960];
int GetFlashLevel(void){return level;}
void UpdateFlashLevelEffect(void){}
int FuncIsActiveTask(void(*fn)(void)){(void)fn;return task;}
void SetFlashScanlineEffectWindowBoundaries(void*p,int x,int y,int radius){(void)p;assert(x==120&&y==80);drawn=radius;}
void CpuFastSet(void*a,void*b,int n){(void)a;(void)b;assert(n==480);copied++;}
void WriteFlashScanlineEffectBuffer(int l){assert(l==level);restored++;}
"""+body+"""
int main(void){assert(WorldLight_Render(1));assert(drawn==200&&copied==1&&level==1);assert(WorldLight_Render(0)&&restored==1&&level==1);task=1;assert(!WorldLight_Render(1)&&copied==1);task=0;level=0;assert(!WorldLight_Render(1));return 0;}
"""
  with tempfile.TemporaryDirectory() as path:
   d=pathlib.Path(path);(d/'test.c').write_text(harness);subprocess.run(['cc','-DPORTABLE','-DEW_SHARED_CAVE_LIGHT=1','-fsanitize=undefined',str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_original_flash_function_preserved(self):
  import hashlib
  data=(NATIVE/'src/fldeff_flash.c').read_text().replace('#include "platform/world_cave_light.h"\n','').replace('    WorldLight_FlashStarted();\n','').encode()
  self.assertEqual(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),'34694fe2e4007e3e322da1b37e1333de6eba1124')
  self.assertIn('EW_SHARED_CAVE_LIGHT ?= 0',(ROOT/'engines/expansion.mk').read_text())
if __name__=='__main__':unittest.main()
