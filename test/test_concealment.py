import hashlib,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/world/world_concealment.c').exists() else ROOT/'engines/expansion-native'
class Concealment(unittest.TestCase):
 def test_actual_native_engine_on_off(self):
  native=NATIVE/'src/world/world_concealment.c'
  with tempfile.TemporaryDirectory() as path:
   d=pathlib.Path(path);(d/'platform').mkdir();(d/'constants').mkdir()
   for p in ['global.h','main.h','pokemon.h','overworld.h','script.h','palette.h','field_player_avatar.h','field_effect.h','event_object_movement.h','sound.h','platform/native_link.h','platform/generated_map.h','platform/world_concealment.h','constants/moves.h','constants/maps.h','constants/map_types.h','constants/trainer_types.h','constants/field_effects.h']:(d/p).write_text('')
   source=(ROOT/'test/native_concealment.c').read_text().replace('ACTUAL_SOURCE',str(native))
   (d/'test.c').write_text(source)
   for flag in (0,1):
    subprocess.run(['cc','-std=c99','-DPORTABLE',f'-DEW_FIELD_CONCEALMENT={flag}','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
   # Execute the actual new field UI branch against the actual core controller.
   ui=(NATIVE/'src/world/world_field_ui.c').read_text();block=ui[ui.index(' if(s.state==60){'):ui.index(' if(s.state==19){')]
   test='''
#undef main
static struct {unsigned state,selected,party,slot,move;}s;
static int same=1;
static int Field(void){return 1;}static int Same(void){return same;}
static void WorldFieldUI_Reset(void){s.state=0;}
static void key(int key){UI_BRANCH}
int main(void){baseline();s.state=60;s.selected=1;s.move=5;
key(2);assert(s.state==0&&gParties[0][0].data[8]==3);
s.state=60;key(-1);assert(s.selected==0);same=0;key(2);assert(s.state==62&&gParties[0][0].data[8]==3);
same=1;s.state=60;key(2);assert(s.state==61&&gParties[0][0].data[8]==2);key(2);assert(gParties[0][0].data[8]==2);return 0;}
'''.replace('UI_BRANCH',block)
   (d/'ui.c').write_text('#define main core_main\n'+source+test)
   subprocess.run(['cc','-std=c99','-DPORTABLE','-DEW_FIELD_CONCEALMENT=1','-fsanitize=undefined','-iquote',str(d),str(d/'ui.c'),'-o',str(d/'ui')],check=True);subprocess.run([str(d/'ui')],check=True)
 def test_stock_detection_and_avatar_source_preserved(self):
  for path,hook,sha in [('src/trainer_see.c','    approachDistance = WorldConceal_Filter(&gObjectEvents[objectEventId], approachDistance);','86fef99242b1107120ce9a8a648558e21a10873d'),('src/field_player_avatar.c','    WorldConceal_Reset();','aca54d3b61940e995c7424be606a748ab8adc8d4')]:
   source=(NATIVE/path).read_text().replace('#include "platform/world_concealment.h"\n','').replace('#if defined(PORTABLE) && EW_FIELD_CONCEALMENT\n'+hook+'\n#endif\n','');raw=source.encode();self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),sha)
 def test_original_field_menu_not_replaced_by_concealment(self):
  p=(NATIVE/'src/party_menu.c').read_text()
  self.assertIn('if ((FieldSkills_Enabled() || WorldFieldUI_Enabled())',p)
  self.assertIn('if ((WorldFieldUI_Enabled() || WorldFieldUI_ConcealAvailable(slotId))',p)
  self.assertIn('&& (WorldFieldUI_Enabled() || WorldConceal_Eligible(',p)
  ui=(NATIVE/'src/world/world_field_ui.c').read_text()
  self.assertIn('int WorldFieldUI_Enabled(void){return WORLD_FIELD_MOVES_EXPERIMENT && WORLD_CHAT_HEIGHT && WorldBridge_Enabled();}',ui)
  self.assertIn('!WORLD_FIELD_MOVES_EXPERIMENT||!WorldFieldUI_Enabled()',ui)
 def test_entry_and_build_are_opt_in_without_missing_transport(self):
  ui=(NATIVE/'src/world/world_field_ui.c').read_text();self.assertIn('(!WORLD_FIELD_MOVES_EXPERIMENT&&!WorldConceal_Eligible(s.move))',ui)
  self.assertIn('s.state=WorldConceal_Eligible(s.move)?60:19;s.selected=s.state==60?1:0;',ui)
  branch=ui[ui.index(' if(s.state==60){'):ui.index(' if(s.state==19){')];self.assertNotIn('Send',branch)
  self.assertIn('WorldConceal_Pump();',ui);self.assertIn('EW_FIELD_CONCEALMENT ?= 0',(ROOT/'engines/expansion.mk').read_text())
  self.assertIn('if args.experimental_field_concealment and not args.development:',(ROOT/'scripts/build_expansion.py').read_text())
if __name__=='__main__':unittest.main()
