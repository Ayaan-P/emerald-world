"""Production biome autotiling preserves geometry, encounter and exit semantics."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from test_save_isolation import function
from world.cave_blueprint import proposal_from_blueprint
from scripts.export_generated_cave import encode

ROOT=Path(__file__).resolve().parents[2]

class CaveBiomes(unittest.TestCase):
    def test_production_biomes_preserve_geometry_and_profile_identity(self):
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
#define GENERATED_CAVE_PROFILES 1
#define GENERATED_CAVE_BIOMES 1
#define GEN_SIDE 31
#define GEN_CELLS 961
#define GEN_FLOOR 0x3333
#define GEN_WALL 0x0722
#define GEN_EXIT 0x3323
#define GEN_AUTOFLOOR 0x331b
static u16 sTiles[GEN_CELLS];static u8 sTemplate[GEN_CELLS],sEncounterProfile;static bool8 sHasTemplate,sPrepared,sSharedEncounterProfile;
static bool8 GeneratedMap_IsInside(void){return TRUE;}
static bool8 GeneratedMap_EntryPending(void){return FALSE;}
''' + function(source,'GeneratedMap_StageTemplate') + function(source,'GeneratedMap_Autotile') + function(source,'GeneratedMap_MatchesPrepared') + function(source,'GeneratedMap_MatchesPreparedProfile') + r'''
int main(void){u8 input[GEN_CELLS];unsigned n=0,i,p;u16 saved[4][GEN_CELLS];
 const u16 floors[4]={0x3201,0x331b,0x3385,0x3201};
 const u16 exits[4]={0x3207,0x3323,0x3386,0x3207};
 while(fread(input,1,sizeof(input),stdin)==sizeof(input)){
  for(p=0;p<4;p++){
   if(!GeneratedMap_StageTemplate(input,sizeof(input)))return 1;
   for(i=0;i<GEN_CELLS;i++)sTiles[i]=input[i]=='.'?GEN_FLOOR:GEN_WALL;
   sTiles[29*31+29]=GEN_EXIT;sEncounterProfile=p;sPrepared=TRUE;
   GeneratedMap_Autotile();
   if(!GeneratedMap_MatchesPrepared(input,sizeof(input)) || !GeneratedMap_MatchesPreparedProfile(input,sizeof(input),p))return 2;
   if(GeneratedMap_MatchesPreparedProfile(input,sizeof(input),(p+1)%4))return 3;
   for(i=0;i<GEN_CELLS;i++){
    if(i==29*31+29){if(sTiles[i]!=exits[p])return 4;}
    else if(input[i]=='.'){if(sTiles[i]!=floors[p] || ((sTiles[i]>>10)&3))return 5;}
    else if(((sTiles[i]>>10)&3)!=1 || sTiles[i]>>12)return 6;
   }
   memcpy(saved[p],sTiles,sizeof(sTiles));
  }
  if(!memcmp(saved[0],saved[1],sizeof(sTiles)) || !memcmp(saved[0],saved[2],sizeof(sTiles)))return 7;
  if(memcmp(saved[0],saved[3],sizeof(sTiles)))return 8;
  n++;
 }
 return n==100 ? 0 : 9;}
'''
        docs=[]
        for style in ('rooms','rounded','organic','maze'):
            for seed in range(25):
                docs.append({'rooms':[[2,2,12,12],[16,16,12,12]],'links':[[0,1]],'entrance_room':0,'exit_room':1,'style':style,'seed':seed,'corridor_width':seed%3+1})
        data=b''.join(encode(proposal_from_blueprint(d))[8:] for d in docs)
        with tempfile.TemporaryDirectory() as tmp:
            c,exe=Path(tmp)/'test.c',Path(tmp)/'test';c.write_text(code)
            for flags in ([],['-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie']):
                build=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',*flags,str(c),'-o',str(exe)],capture_output=True,text=True)
                self.assertEqual(build.returncode,0,build.stderr)
                result=subprocess.run([str(exe)],input=data,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr.decode() or str(result.returncode))

    def test_all_biome_floors_encounter_and_exits_warp(self):
        attrs=(ROOT/'data/tilesets/secondary/cave/metatile_attributes.bin').read_bytes()
        def behavior(tile):return struct.unpack_from('<H',attrs,2*(tile-512))[0]&255
        for floor in (0x201,0x31b,0x385):self.assertEqual(behavior(floor),8)
        for exit in (0x207,0x323,0x386):self.assertEqual(behavior(exit),0x65)

if __name__=='__main__':unittest.main()
