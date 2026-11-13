import pathlib,re,subprocess,tempfile,unittest
from test_apprentice import function
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/load_save.c').exists() else ROOT/'engines/expansion-native'
class Walking(unittest.TestCase):
 def test_actual_walk_save_load_collision_on_off(self):
  source=NATIVE/'src/world/world_apprentice_walk.c';s=source.read_text();save=(NATIVE/'src/load_save.c').read_text();movement=(NATIVE/'src/event_object_movement.c').read_text()
  funcs='\n'.join([function(save,'void SaveObjectEvents(void)'),function(save,'void LoadObjectEvents(void)'),function(movement,'u32 GetObjectObjectCollidesWith(struct ObjectEvent *objectEvent, s16 x, s16 y, bool32 addCoords)')])
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp)
   for h in re.findall(r'#include "([^"]+)"',s):
    p=d/h;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('')
   text=(ROOT/'test/native_apprentice_walk.c').read_text().replace('ACTUAL_SOURCE',str(source)).replace('ACTUAL_SAVE_COLLISION',funcs).replace('ACTUAL_GRAPHICS',function((NATIVE/'src/apprentice.c').read_text(),'u16 Apprentice_GetOutingGraphics(u8 apprentice)'));(d/'test.c').write_text(text)
   for enabled in (0,1):
    subprocess.run(['cc','-std=gnu99','-DPORTABLE',f'-DEW_APPRENTICE_WALKING={enabled}','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_native_lifecycle_and_template_hooks(self):
  m=(NATIVE/'src/event_object_movement.c').read_text();self.assertIn('WorldApprenticeWalk_Forget()',function(m,'void ResetObjectEvents(void)'));self.assertIn('WorldApprenticeWalk_Template(',function(m,'const struct ObjectEventTemplate *GetObjectEventTemplateByLocalIdAndMap(u8 localId, u8 mapNum, u8 mapGroup)'))
  s=(NATIVE/'src/overworld.c').read_text();self.assertIn('WorldApprenticeWalk_LeaveField()',function(s,'void CleanupOverworldWindowsAndTilemaps(void)'))
  c=(NATIVE/'src/world/world_core_story.c').read_text();self.assertIn('WorldApprenticeWalk_Update()',function(c,'void WorldCoreStory_Update(void)'))
 def test_no_saved_follower_backend(self):
  s=(NATIVE/'src/world/world_apprentice_walk.c').read_text();self.assertNotIn('gSaveBlock3Ptr',s);self.assertNotIn('SetFollowerNPCData(',s);self.assertNotIn('FlagSet(',s);self.assertIn('SpawnSpecialObjectEvent(&sWalk.template)',s);self.assertIn('GetCollisionAtCoords(npc,x,y,dir)',s)
if __name__=='__main__':unittest.main()
