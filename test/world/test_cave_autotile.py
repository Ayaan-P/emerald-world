"""Native cave autotiling preserves the validated geometry and collision bits."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from test_save_isolation import function
from world.cave_blueprint import proposal_from_blueprint
from scripts.export_generated_cave import encode

ROOT=Path(__file__).resolve().parents[2]

class CaveAutotile(unittest.TestCase):
    def test_real_autotiler_and_prepared_identity(self):
        source=(ROOT/'src/platform/generated_map.c').read_text()
        code=r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int16_t s16;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 1
#define GENERATED_MAP_AUTOTILE 1
#define GEN_SIDE 31
#define GEN_CELLS 961
#define GEN_FLOOR 0x3333
#define GEN_WALL 0x0722
#define GEN_EXIT 0x3323
#define GEN_AUTOFLOOR 0x331b
static u16 sTiles[GEN_CELLS];static u8 sTemplate[GEN_CELLS];static bool8 sHasTemplate,sPrepared,sSeenInside;
struct Warp {int mapGroup,mapNum,warpId,x,y;};
static struct Warp sReturn,sPreviousDynamicWarp;
static struct Save {struct Warp location,dynamicWarp;} save,*gSaveBlock1Ptr=&save;
static struct {u32 vblankCounter1;} gMain;
#define WARP_ID_NONE (-1)
#define MAP_GENERATED_WORLD_CAVE 0
#define MAP_GROUP(x) (0)
#define MAP_NUM(x) (0)
static bool8 GeneratedMap_CanEnter(void){return TRUE;}
static bool8 GetReturnCoords(s16 *x,s16 *y){*x=3;*y=4;return TRUE;}
static bool8 WorldBridge_Enabled(void){return TRUE;}
static bool8 Platform_ReloadGeneratedMap(void){return TRUE;}
static void SetDynamicWarpWithCoords(int a,int b,int c,int d,int e,int f){(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;}
static void SetWarpDestination(int a,int b,int c,int d,int e){(void)a;(void)b;(void)c;(void)d;(void)e;}
static void StoreInitialPlayerAvatarState(void){}
static void DoWarp(void){}
static void BuildMaze(u32 seed){(void)seed;}
static bool8 GeneratedMap_IsInside(void){return TRUE;}
static bool8 GeneratedMap_EntryPending(void){return FALSE;}
''' + function(source,'GeneratedMap_StageTemplate') + function(source,'GeneratedMap_Autotile') + function(source,'GeneratedMap_Enter') + function(source,'GeneratedMap_MatchesPrepared') + r'''
int main(void) {
 u8 input[GEN_CELLS];unsigned n=0,i,mask;static const u16 walls[16]={0x322,0x332,0x322,0x31a,0x329,0x329,0x32a,0x330,0x320,0x318,0x322,0x330,0x328,0x330,0x330,0x330};
 /* Exercise each neighbor mask at the center, separately from valid-map tests. */
 for(mask=0;mask<16;mask++) {
  for(i=0;i<GEN_CELLS;i++)sTiles[i]=GEN_WALL;
  if(mask&1)sTiles[15*31+15-31]=GEN_FLOOR;
  if(mask&2)sTiles[15*31+15+1]=GEN_FLOOR;
  if(mask&4)sTiles[15*31+15+31]=GEN_FLOOR;
  if(mask&8)sTiles[15*31+15-1]=GEN_FLOOR;
  GeneratedMap_Autotile();if(sTiles[15*31+15]!=(0x400|walls[mask]))return 1;
 }
 while(fread(input,1,sizeof(input),stdin)==sizeof(input)) {
  if(!GeneratedMap_StageTemplate(input,sizeof(input)))return 2;
  if(!GeneratedMap_Enter() || !sPrepared)return 9;
  if(!GeneratedMap_MatchesPrepared(input,sizeof(input)))return 3;
  for(i=0;i<GEN_CELLS;i++) {
   if(i==29*31+29) {if(sTiles[i]!=GEN_EXIT)return 4;}
   else if(input[i]=='.') {if(sTiles[i]!=GEN_AUTOFLOOR || ((sTiles[i]>>10)&3))return 5;}
   else if(((sTiles[i]>>10)&3)!=1 || sTiles[i]>>12)return 6;
  }
  input[1*31+1]='#';if(GeneratedMap_MatchesPrepared(input,sizeof(input)))return 7;
  n++;
 }
 return n==200 ? 0 : 8;
}
'''
        docs=[]
        for style in ('rooms','rounded','organic','maze'):
            for seed in range(50):
                docs.append({'rooms':[[2,2,12,12],[16,16,12,12]],'links':[[0,1]],'entrance_room':0,'exit_room':1,'style':style,'seed':seed,'corridor_width':seed%3+1})
        data=b''.join(encode(proposal_from_blueprint(d))[8:] for d in docs)
        with tempfile.TemporaryDirectory() as temp:
            c,exe=Path(temp)/'test.c',Path(temp)/'test';c.write_text(code)
            for flags in ([],['-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie']):
                build=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',*flags,str(c),'-o',str(exe)],capture_output=True,text=True)
                self.assertEqual(build.returncode,0,build.stderr)
                result=subprocess.run([str(exe)],input=data,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr.decode() or str(result.returncode))

    def test_floor_preserves_encounter_behavior_and_exit_warp(self):
        attrs=(ROOT/'data/tilesets/secondary/cave/metatile_attributes.bin').read_bytes()
        def behavior(tile):return struct.unpack_from('<H',attrs,2*(tile-512))[0]&255
        self.assertEqual(behavior(0x31b),behavior(0x333))
        self.assertEqual(behavior(0x31b),8)
        self.assertEqual(behavior(0x323),0x65)

if __name__=='__main__':unittest.main()
