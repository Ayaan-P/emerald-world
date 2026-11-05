"""Offline profile formats, native loader and curated encounter selection."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_save_isolation import function
from world import cave_blueprint, author_cave, offline_cave
from scripts import export_generated_cave

ROOT=Path(__file__).resolve().parents[2]
BLUEPRINT={'rooms':[[2,2,12,12],[16,16,12,12]],'links':[[0,1]],'entrance_room':0,'exit_room':1,'style':'organic','seed':42}
PROPOSAL=cave_blueprint.proposal_from_blueprint(BLUEPRINT)

class CaveEcology(unittest.TestCase):
    def test_versioned_offline_encoding_and_legacy_separation(self):
        old=export_generated_cave.encode(PROPOSAL)
        self.assertEqual(old[:8],b'EWGMAP01')
        for name,number in offline_cave.PROFILES.items():
            with self.subTest(name=name):
                blob=offline_cave.encode_profile(PROPOSAL,name)
                self.assertEqual(blob,export_generated_cave.encode(PROPOSAL,encounter_profile=name))
                self.assertEqual(blob[:9],b'EWGMAP02'+bytes([number]))
                self.assertEqual(blob[9:],old[8:])
                self.assertEqual(offline_cave.SharedCave(blob).profile,number)
        for bad in ('unknown',True,None,1):
            with self.assertRaises(ValueError):offline_cave.encode_profile(PROPOSAL,bad)
        bad={**PROPOSAL,'spawn':[True,1]}
        with self.assertRaises(ValueError):offline_cave.encode_profile(bad,'meteor')
        bad={**PROPOSAL,'rows':[PROPOSAL['rows'][0][:-1],PROPOSAL['rows'][1]+'#',*PROPOSAL['rows'][2:]]}
        with self.assertRaises(ValueError):offline_cave.encode_profile(bad,'meteor')

    def test_model_offline_ecology_is_explicit_and_bounded(self):
        def wire(doc):
            return ('\n'.join(json.dumps(e) for e in [
                {'type':'item.completed','item':{'type':'agent_message','text':json.dumps(doc)}},
                {'type':'turn.completed'}])).encode()
        selected={**BLUEPRINT,'encounter_profile':'meteor'}
        proposal,profile=author_cave.decode_blueprint_events(wire(selected),offline_ecology=True)
        self.assertEqual(profile,'meteor');self.assertEqual(offline_cave.encode_profile(proposal,profile)[8],1)
        with self.assertRaises(ValueError):author_cave.decode_blueprint_events(wire(selected))
        for profile in ('command',True,None):
            with self.assertRaises(ValueError):author_cave.decode_blueprint_events(wire({**selected,'encounter_profile':profile}),offline_ecology=True)
        self.assertIn('encounter_profile',author_cave.prompt_for('meteor',offline_ecology=True))
        self.assertNotIn('encounter_profile',author_cave.prompt_for('meteor'))
        catalog=json.dumps({'models':[{'slug':'gpt-6-luna'}]}).encode()
        with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog,wire(selected)]):
            proposal,blob=author_cave.author('meteor',offline_ecology=True)
        self.assertEqual(blob,offline_cave.encode_profile(proposal,'meteor'))

    def test_offline_author_output_does_not_publish_or_overwrite(self):
        blob=offline_cave.encode_profile(PROPOSAL,'ice')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cave.bin'
            with patch('world.author_cave.author',return_value=(PROPOSAL,blob)) as author, \
                 patch('world.author_cave.publish_bytes') as publish, patch('builtins.print'):
                self.assertEqual(author_cave.main(['icy theme','--offline-output',str(path)]),0)
                self.assertEqual(path.read_bytes(),blob)
                self.assertTrue(author.call_args.kwargs['offline_ecology'])
                publish.assert_not_called()
                self.assertEqual(author_cave.main(['icy theme','--offline-output',str(path)]),1)
                self.assertEqual(path.read_bytes(),blob)
                publish.assert_not_called()

    def test_real_loader_and_profile_lifecycle(self):
        generated=(ROOT/'src/platform/generated_map.c').read_text()
        sdl=(ROOT/'src/platform/sdl2.c').read_text()
        code=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int16_t s16;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 1
#define GENERATED_CAVE_PROFILES 1
#define GEN_SIDE 31
#define GEN_CELLS 961
#define GENERATED_MAP_TEMPLATE_BYTES 961
#define GENERATED_WILDLIFE_BYTES 37
static u8 sTemplate[GEN_CELLS];static bool8 sHasTemplate,sPrepared,inside=1,online;
static u8 sEncounterProfile;static bool8 sSharedEncounterProfile;
static bool8 GeneratedMap_IsInside(void){return inside;}
static bool8 WorldBridge_Enabled(void){return online;}
static FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
''' + ''.join(function(generated,n) for n in ('GeneratedMap_StageTemplate','GeneratedMap_SetEncounterProfile','GeneratedMap_SetSharedEncounterProfile','GeneratedMap_EncounterProfile')) + function(sdl,'LoadGeneratedMapTemplate') + r'''
int main(int argc,char **argv){u8 old[961];if(argc!=5)return 1;
 if(!LoadGeneratedMapTemplate(argv[1]))return 2;sPrepared=1;
 if(GeneratedMap_EncounterProfile()!=1)return 3;
 online=1;if(GeneratedMap_EncounterProfile())return 4;
 if(!GeneratedMap_SetSharedEncounterProfile(1) || GeneratedMap_EncounterProfile()!=1)return 10;
 online=0;inside=0;if(GeneratedMap_EncounterProfile())return 5;inside=1;
 memcpy(old,sTemplate,sizeof(old));
 if(LoadGeneratedMapTemplate(argv[2]) || memcmp(old,sTemplate,sizeof(old)) || GeneratedMap_EncounterProfile()!=1)return 6;
 if(LoadGeneratedMapTemplate(argv[3]) || memcmp(old,sTemplate,sizeof(old)) || GeneratedMap_EncounterProfile()!=1)return 7;
 if(!LoadGeneratedMapTemplate(argv[4]) || GeneratedMap_EncounterProfile())return 8;
 if(GeneratedMap_SetEncounterProfile(4) || GeneratedMap_EncounterProfile())return 9;
 return 0;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); c=root/'test.c';exe=root/'test';c.write_text(code)
            v2=offline_cave.encode_profile(PROPOSAL,'meteor');v1=export_generated_cave.encode(PROPOSAL)
            files=[root/'v2',root/'bad_id',root/'too_long',root/'v1']
            for path,data in zip(files,[v2,v2[:8]+b'\xff'+v2[9:],v2+b'x',v1]):path.write_bytes(data)
            build=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            run=subprocess.run([str(exe),*map(str,files)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr or str(run.returncode))

    def test_real_wild_header_selection(self):
        source=(ROOT/'src/wild_encounter.c').read_text()
        code=r"""
#include <stdint.h>
typedef uint8_t u8;typedef uint16_t u16;
#define PORTABLE 1
#define GENERATED_CAVE_PROFILES 1
#define MAP_UNDEFINED 0xff00
#define MAP_ALTERING_CAVE 0x0701
#define MAP_METEOR_FALLS_1F_1R 0x0201
#define MAP_SHOAL_CAVE_LOW_TIDE_ICE_ROOM 0x0301
#define MAP_VICTORY_ROAD_1F 0x0401
#define MAP_GROUP(x) ((x)>>8)
#define MAP_NUM(x) ((x)&255)
#define VAR_ALTERING_CAVE_WILD_SET 0
#define NUM_ALTERING_CAVE_TABLES 9
#define HEADER_NONE 0xffff
struct WildPokemonHeader {u8 mapGroup,mapNum;};
static const struct WildPokemonHeader gWildMonHeaders[]={{1,1},{2,1},{3,1},{4,1},{0xff,0}};
static struct Save {struct {int mapGroup,mapNum;} location;} save,*gSaveBlock1Ptr=&save;
static u8 profile;
static u8 GeneratedMap_EncounterProfile(void){return profile;}
static u16 VarGet(int x){(void)x;return 0;}
""" + function(source,'GetCurrentMapWildMonHeaderId') + r"""
int main(void){save.location.mapGroup=1;save.location.mapNum=1;
 for(profile=0;profile<=3;profile++)if(GetCurrentMapWildMonHeaderId()!=profile)return 1;
 profile=0;save.location.mapGroup=5;if(GetCurrentMapWildMonHeaderId()!=HEADER_NONE)return 2;
 return 0;}
"""
        with tempfile.TemporaryDirectory() as tmp:
            c,exe=Path(tmp)/'select.c',Path(tmp)/'select';c.write_text(code)
            build=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_dexnav_encounter_entrypoints_remain_linkable(self):
        source=(ROOT/'src/wild_encounter.c').read_text()
        code=r"""
#include <stdint.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;
static int calls;static int gEnemyParty[1];
static u16 GetCurrentMapWildMonHeaderId(void){return 23;}
static u32 CalculateDexNavShinyRolls(void){return 2;}
static void CreateWildMon(u16 species,u8 level){(void)species;(void)level;calls++;}
static int IsMonShiny(const int *p){(void)p;return calls==3;}
""" + function(source,'WildEncounter_GetDexNavHeader') + function(source,'WildEncounter_CreateDexNavMon') + r"""
int main(void){if(WildEncounter_GetDexNavHeader()!=23)return 1;
 WildEncounter_CreateDexNavMon(41,7);return calls==3?0:2;}
"""
        with tempfile.TemporaryDirectory() as tmp:
            c,exe=Path(tmp)/'dex.c',Path(tmp)/'dex';c.write_text(code)
            build=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_old_loader_rejects_profile_format(self):
        source=(ROOT/'src/platform/sdl2.c').read_text()
        code=r"""
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef int bool8;
#define FALSE 0
#define GENERATED_CAVE_PROFILES 0
#define GENERATED_MAP_TEMPLATE_BYTES 961
#define GENERATED_WILDLIFE_BYTES 37
static FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
static bool8 GeneratedMap_StageTemplate(const u8 *p,unsigned n){return n==961 && p[0]=='#';}
""" + function(source,'LoadGeneratedMapTemplate') + r"""
int main(int argc,char **argv){if(argc!=3)return 1;
 return !LoadGeneratedMapTemplate(argv[1]) || LoadGeneratedMapTemplate(argv[2]);}
"""
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c=root/'test.c';exe=root/'test';c.write_text(code)
            (root/'v1').write_bytes(export_generated_cave.encode(PROPOSAL))
            (root/'v2').write_bytes(offline_cave.encode_profile(PROPOSAL,'meteor'))
            build=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe),str(root/'v1'),str(root/'v2')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_curated_tables_exist(self):
        data=json.loads((ROOT/'src/data/wild_encounters.json').read_text())
        names={entry.get('map') for group in data['wild_encounter_groups'] for entry in group.get('encounters',[]) if entry.get('land_mons')}
        for name in ('MAP_GENERATED_WORLD_CAVE','MAP_METEOR_FALLS_1F_1R','MAP_SHOAL_CAVE_LOW_TIDE_ICE_ROOM','MAP_VICTORY_ROAD_1F'):
            self.assertIn(name,names)

if __name__=='__main__':unittest.main()
