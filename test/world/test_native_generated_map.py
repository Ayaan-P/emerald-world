"""Compile the native generated-map implementation with disposable engine stubs."""
from pathlib import Path
from test_save_isolation import function
import json, subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[2]

class NativeGeneratedMap(unittest.TestCase):
 def test_exit_tile_uses_real_cave_south_warp_behavior(self):
  entry=json.loads((ROOT/'data/maps/GeneratedWorld_Cave/map.json').read_text())
  self.assertEqual(entry['warp_events'],[{'x':x,'y':x,'elevation':3,'dest_map':'MAP_DYNAMIC','dest_warp_id':'WARP_ID_DYNAMIC'} for x in (29,61)])
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
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include "global.h"
#include "platform/generated_map.h"
struct Task {int isActive;};struct Task gTasks[16];
struct Save save,*gSaveBlock1Ptr=&save;
struct { u32 vblankCounter1; } gMain;
struct { int mapType; struct MapLayout *mapLayout; } gMapHeader;
static int online,foot=1,warps,linkPending,rallyReturn; static struct WarpData destination;
static const char *sGeneratedMapPath;
static s16 playerX=15,playerY=16;
void PlayerGetDestCoords(s16 *x,s16 *y){*x=playerX;*y=playerY;}
const char *LinkTransport_TagPeer(void){return 0;}
const void *LinkTransport_PendingTag(void){return linkPending ? &linkPending : 0;}
const void *LinkTransport_PendingInvitation(void){return 0;}
struct WorldRallySnapshot{unsigned id;};
int WorldRally_HasReturn(void){return rallyReturn;}int WorldRally_GetSnapshot(struct WorldRallySnapshot *r){(void)r;return 0;}
int WorldBridge_Enabled(void){return online;}
int WorldBridge_GeneratedCaveReady(void){return 0;}
int IsMapTypeOutdoors(int x){return x==1;}
int TestPlayerAvatarFlags(int f){return f==1 && foot;}
void SetWarpDestination(s8 g,s8 n,s8 w,s8 x,s8 y){destination=(struct WarpData){g,n,w,x,y};}
void SetDynamicWarpWithCoords(int unused,s8 g,s8 n,s8 w,s8 x,s8 y){(void)unused;save.dynamicWarp=(struct WarpData){g,n,w,x,y};}
void StoreInitialPlayerAvatarState(void){}
void DoWarp(void){warps++;}
FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
/* LOADER_BODY */
int main(int argc, char **argv){
 assert(argc==2);
 u16 seen[961], queue[961], first[961]; struct MapLayout base={19,26,0,0,0,0};
 for(unsigned seed=1;seed<=100;seed++){
  save.location=(struct WarpData){3,4,0,8,9};save.dynamicWarp=(struct WarpData){7,8,9,10,11};save.pos.x=2;save.pos.y=3;gMain.vblankCounter1=seed;gMapHeader.mapType=1;gMapHeader.mapLayout=&base;playerX=15;playerY=16;
  online=1;assert(!GeneratedMap_CanEnter()&&!GeneratedMap_Enter());online=0;
  foot=0;assert(!GeneratedMap_CanEnter());foot=1;
  linkPending=1;assert(!GeneratedMap_CanEnter());linkPending=0;
  rallyReturn=1;assert(!GeneratedMap_CanEnter());rallyReturn=0;
  sGeneratedMapPath="/nonexistent-generated-map-fixture";int oldWarps=warps;assert(!GeneratedMap_Enter() && warps==oldWarps && save.dynamicWarp.mapGroup==7);
  sGeneratedMapPath=NULL;assert(GeneratedMap_Enter());
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
 playerX=135;assert(!GeneratedMap_CanEnter());playerX=15;
 /* A model-proposed row grid becomes an inert native template only after
  * full validation. A failed replacement must preserve the prior template. */
 u8 proposal[961], bad[961];
 for(int i=0;i<961;i++) proposal[i] = (first[i] == 0x3333 || first[i] == 0x3323) ? '.' : '#';
 assert(GeneratedMap_StageTemplate(proposal,961));
 memcpy(bad,proposal,961);bad[0]='.';assert(!GeneratedMap_StageTemplate(bad,961));
 memcpy(bad,proposal,961);bad[28*31+29]='#';assert(!GeneratedMap_StageTemplate(bad,961));
 memcpy(bad,proposal,961);bad[1]='X';assert(!GeneratedMap_StageTemplate(bad,961));
 memset(bad,'#',961);
 for(int y=1;y<=29;y++)bad[y*31+1]='.';
 for(int x=1;x<=29;x++)bad[29*31+x]='.';
 bad[28*31+29]='.';bad[10*31+10]='.'; /* isolated floor */
 assert(!GeneratedMap_StageTemplate(bad,961));
 assert(!GeneratedMap_StageTemplate(proposal,960));
 save.location=(struct WarpData){3,4,0,8,9};save.dynamicWarp=(struct WarpData){7,8,9,10,11};
 assert(GeneratedMap_Enter());save.location=destination;
 const struct MapLayout *templated=GeneratedMap_ResolveLayout(&base);
 for(int i=0;i<961;i++)assert((templated->map[i]==0x3333 || templated->map[i]==0x3323)==(proposal[i]=='.'));
 assert(GeneratedMap_Leave());save.location=destination;GeneratedMap_ResolveLayout(&base);
 /* The actual SDL loader stages a file from the Python exporter into the
  * actual native map generator, with no emulator or rendering involved. */
 assert(LoadGeneratedMapTemplate(argv[1]));sGeneratedMapPath=argv[1];
 assert(GeneratedMap_Enter());save.location=destination;
 templated=GeneratedMap_ResolveLayout(&base);
 for(int y=1;y<30;y++)for(int x=1;x<30;x++)
  assert(templated->map[y*31+x]==((x==29 && y==29)?0x3323:0x3333));
 assert(GeneratedMap_Leave());save.location=destination;GeneratedMap_ResolveLayout(&base);
 /* Updating the template while the client is running is observed on the
  * next entry; the loaded map itself is never changed underneath a player. */
 FILE *f=fopen(argv[1],"r+b");assert(f && !fseek(f,8+2*31+2,SEEK_SET));assert(fputc('#',f)=='#');assert(!fclose(f));
 assert(GeneratedMap_Enter());save.location=destination;templated=GeneratedMap_ResolveLayout(&base);
 assert(templated->map[2*31+2]==0x0722);
 assert(GeneratedMap_Leave());save.location=destination;GeneratedMap_ResolveLayout(&base);
 return 0;
}'''
  source=(ROOT/'src/platform/sdl2.c').read_text()
  loader=function(source,'LoadGeneratedMapTemplate')+function(source,'Platform_ReloadGeneratedMap')
  harness=harness.replace('/* LOADER_BODY */',loader)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'platform').mkdir();(p/'constants').mkdir();(p/'global.h').write_text('#ifndef G\n#define G\n'+global_h+'\n#endif\n')
   for name in ('main.h','overworld.h','field_screen_effect.h','field_player_avatar.h','fieldmap.h'):
    (p/name).write_text('#include "global.h"\nint IsMapTypeOutdoors(int); int TestPlayerAvatarFlags(int); void SetWarpDestination(s8,s8,s8,s8,s8); void SetDynamicWarpWithCoords(int,s8,s8,s8,s8,s8); void PlayerGetDestCoords(s16*,s16*); void StoreInitialPlayerAvatarState(void); void DoWarp(void);\n#define MAP_OFFSET 7\n')
   (p/'task.h').write_text('struct Task {int isActive;}; extern struct Task gTasks[16];\n#define NUM_TASKS 16\n')
   (p/'platform/world_rally.h').write_text('struct WorldRallySnapshot{unsigned id;}; int WorldRally_HasReturn(void); int WorldRally_GetSnapshot(struct WorldRallySnapshot *);\n')
   (p/'platform/link_transport.h').write_text('const char *LinkTransport_TagPeer(void); const void *LinkTransport_PendingTag(void); const void *LinkTransport_PendingInvitation(void);\n')
   (p/'platform/world_bridge.h').write_text('int WorldBridge_Enabled(void); int WorldBridge_GeneratedCaveReady(void);\n')
   (p/'platform/generated_map.h').write_text((ROOT/'include/platform/generated_map.h').read_text())
   (p/'constants/maps.h').write_text(f'#define MAP_GENERATED_WORLD_CAVE ({group}<<8)\n#define MAP_GROUP(x) ((x)>>8)\n#define MAP_NUM(x) ((x)&255)\n#define WARP_ID_NONE (-1)\n')
   # Anonymous extern structs must be defined in the same translation unit.
   (p/'test.c').write_text(('#define EXPECTED_GROUP '+str(group)+'\n')+harness.replace('struct { u32 vblankCounter1; } gMain;','__typeof__(gMain) gMain;').replace('struct { int mapType; struct MapLayout *mapLayout; } gMapHeader;','__typeof__(gMapHeader) gMapHeader;'))
   q=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-I',str(p),str(ROOT/'src/platform/generated_map.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
   rows=['#'*31]+['#'+'.'*29+'#']*29+['#'*31]
   (p/'proposal.json').write_text(json.dumps({'rows':rows,'spawn':[1,1],'exit':[29,29]}))
   q=subprocess.run(['python3',str(ROOT/'scripts/export_generated_cave.py'),str(p/'proposal.json'),str(p/'cave.bin')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test'),str(p/'cave.bin')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__': unittest.main()
