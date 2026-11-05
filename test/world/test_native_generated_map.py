"""Compile the native generated-map implementation with disposable engine stubs."""
from pathlib import Path
import json, subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[2]

class NativeGeneratedMap(unittest.TestCase):
 def test_exit_tile_uses_real_cave_south_warp_behavior(self):
  entry=json.loads((ROOT/'data/maps/GeneratedWorld_Cave/map.json').read_text())
  self.assertEqual(entry['warp_events'],[{'x':29,'y':29,'elevation':3,'dest_map':'MAP_DYNAMIC','dest_warp_id':'WARP_ID_DYNAMIC'}])
  # 0x3323 packs cave metatile 0x323, collision 0 and elevation 3.
  attr=(ROOT/'data/tilesets/secondary/cave/metatile_attributes.bin').read_bytes()
  offset=(0x323-512)*2
  self.assertEqual(int.from_bytes(attr[offset:offset+2],'little') & 0xff,0x65) # MB_SOUTH_ARROW_WARP
  self.assertEqual((0x3323 >> 10)&3,0)
  self.assertEqual((0x3323 >> 12)&15,3)
 def test_connected_cave_and_return_across_seeds(self):
  groups = json.loads((ROOT/'data/maps/map_groups.json').read_text())
  group = groups['group_order'].index('gMapGroup_GeneratedWorld')
  global_h = r'''
#include <stdint.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int8_t s8; typedef int16_t s16; typedef int bool8;
#define TRUE 1
#define FALSE 0
#define PLAYER_AVATAR_FLAG_ON_FOOT 1
struct WarpData { s8 mapGroup,mapNum,warpId; s16 x,y; };
struct MapLayout { int width,height; const u16 *border,*map; const void *primary,*secondary; };
struct Save { struct WarpData location, dynamicWarp; struct { s16 x,y; } pos; };
extern struct Save *gSaveBlock1Ptr;
extern struct { u32 vblankCounter1; } gMain;
extern struct { int mapType; struct MapLayout *mapLayout; } gMapHeader;
'''
  harness = r'''
#include <assert.h>
#include <string.h>
#include "global.h"
#include "platform/generated_map.h"
struct Save save,*gSaveBlock1Ptr=&save;
struct { u32 vblankCounter1; } gMain;
struct { int mapType; struct MapLayout *mapLayout; } gMapHeader;
static int online,foot=1,warps; static struct WarpData destination;
static s16 playerX=15,playerY=16;
void PlayerGetDestCoords(s16 *x,s16 *y){*x=playerX;*y=playerY;}
int WorldBridge_Enabled(void){return online;}
int IsMapTypeOutdoors(int x){return x==1;}
int TestPlayerAvatarFlags(int f){return f==1 && foot;}
void SetWarpDestination(s8 g,s8 n,s8 w,s8 x,s8 y){destination=(struct WarpData){g,n,w,x,y};}
void SetDynamicWarpWithCoords(int unused,s8 g,s8 n,s8 w,s8 x,s8 y){(void)unused;save.dynamicWarp=(struct WarpData){g,n,w,x,y};}
void StoreInitialPlayerAvatarState(void){}
void DoWarp(void){warps++;}
int main(void){
 u16 seen[961], queue[961], first[961]; struct MapLayout base={19,26,0,0,0,0};
 for(unsigned seed=1;seed<=100;seed++){
  save.location=(struct WarpData){3,4,0,8,9};save.dynamicWarp=(struct WarpData){7,8,9,10,11};save.pos.x=2;save.pos.y=3;gMain.vblankCounter1=seed;gMapHeader.mapType=1;gMapHeader.mapLayout=&base;playerX=15;playerY=16;
  online=1;assert(!GeneratedMap_CanEnter()&&!GeneratedMap_Enter());online=0;
  foot=0;assert(!GeneratedMap_CanEnter());foot=1;assert(GeneratedMap_Enter());
  assert(destination.mapGroup==EXPECTED_GROUP && destination.mapNum==0 && destination.x==1 && destination.y==1);
  save.location=destination;assert(GeneratedMap_IsInside());
  const struct MapLayout *map=GeneratedMap_ResolveLayout(&base);assert(map!=&base && map->width==31 && map->height==31);
  if(seed==1)memcpy(first,map->map,sizeof(first));
  if(seed==2)assert(memcmp(first,map->map,sizeof(first)));
  memset(seen,0,sizeof(seen));int start=32,head=0,tail=0;queue[tail++]=start;seen[start]=1;
  while(head<tail){int p=queue[head++],v[4]={p-31,p+1,p+31,p-1};for(int i=0;i<4;i++){int q=v[i];if(q>=0&&q<961&&(map->map[q]==0x3333||map->map[q]==0x3323)&&!seen[q]){seen[q]=1;queue[tail++]=q;}}}
  for(int i=0;i<961;i++){
   if(i<31||i>=930||i%31==0||i%31==30)assert(map->map[i]==0x0722);
   if(map->map[i]==0x3333||map->map[i]==0x3323)assert(seen[i]);
  }
  assert(seen[29*31+29] && map->map[29*31+29]==0x3323);assert(save.dynamicWarp.mapGroup==3);
  if(seed & 1) { assert(GeneratedMap_Leave()); }
  else { destination=save.dynamicWarp; } /* Native arrow-warp resolves the dynamic return. */
  assert(destination.mapGroup==3 && destination.mapNum==4 && destination.warpId==-1 && destination.x==8 && destination.y==9);
  save.location=destination;assert(!GeneratedMap_IsInside() && GeneratedMap_ResolveLayout(&base)==&base);assert(save.dynamicWarp.mapGroup==7 && save.dynamicWarp.mapNum==8 && save.dynamicWarp.x==10);
 }
 playerX=135;assert(!GeneratedMap_CanEnter());
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'platform').mkdir();(p/'constants').mkdir();(p/'global.h').write_text('#ifndef G\n#define G\n'+global_h+'\n#endif\n')
   for name in ('main.h','overworld.h','field_screen_effect.h','field_player_avatar.h','fieldmap.h'):
    (p/name).write_text('#include "global.h"\nint IsMapTypeOutdoors(int); int TestPlayerAvatarFlags(int); void SetWarpDestination(s8,s8,s8,s8,s8); void SetDynamicWarpWithCoords(int,s8,s8,s8,s8,s8); void PlayerGetDestCoords(s16*,s16*); void StoreInitialPlayerAvatarState(void); void DoWarp(void);\n#define MAP_OFFSET 7\n')
   (p/'platform/world_bridge.h').write_text('int WorldBridge_Enabled(void);\n')
   (p/'platform/generated_map.h').write_text((ROOT/'include/platform/generated_map.h').read_text())
   (p/'constants/maps.h').write_text(f'#define MAP_GENERATED_WORLD_CAVE ({group}<<8)\n#define MAP_GROUP(x) ((x)>>8)\n#define MAP_NUM(x) ((x)&255)\n#define WARP_ID_NONE (-1)\n')
   # Anonymous extern structs must be defined in the same translation unit.
   (p/'test.c').write_text(('#define EXPECTED_GROUP '+str(group)+'\n')+harness.replace('struct { u32 vblankCounter1; } gMain;','__typeof__(gMain) gMain;').replace('struct { int mapType; struct MapLayout *mapLayout; } gMapHeader;','__typeof__(gMapHeader) gMapHeader;'))
   q=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-I',str(p),str(ROOT/'src/platform/generated_map.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__': unittest.main()
