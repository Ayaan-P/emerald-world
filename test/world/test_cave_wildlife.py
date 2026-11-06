"""Bounded offline custom encounter tables and actual native component paths."""
from pathlib import Path
import json
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_save_isolation import function
from world import author_cave, cave_blueprint, offline_cave
from world.cave_species import SPECIES
from world.shared_cave import SharedCave

ROOT=Path(__file__).resolve().parents[2]
BLUEPRINT={'rooms':[[2,2,12,12],[16,16,12,12]],'links':[[0,1]],'entrance_room':0,'exit_room':1,'style':'organic','seed':42}
PROPOSAL=cave_blueprint.proposal_from_blueprint(BLUEPRINT)
WILDLIFE=[{'species':'MAGIKARP','level':5} for _ in range(12)]

class CaveWildlife(unittest.TestCase):
    def test_catalog_exactly_matches_real_engine_species(self):
        text=(ROOT/'include/constants/species.h').read_text()
        expected={name:int(number) for name,number in re.findall(r'^#define SPECIES_([A-Z0-9_]+)\s+(\d+)\s*$',text,re.M)
                  if 1<=int(number)<=251 or 277<=int(number)<=411}
        self.assertEqual(SPECIES,expected);self.assertEqual(len(SPECIES),386)
        self.assertNotIn('EGG',SPECIES);self.assertNotIn('OLD_UNOWN_B',SPECIES)

    def test_encoding_is_bounded_and_valid_shared_template(self):
        blob=offline_cave.encode_wildlife(PROPOSAL,'ice',25,WILDLIFE)
        self.assertEqual(len(blob),1007);self.assertEqual(blob[:10],b'EWGMAP03\x02\x19')
        self.assertEqual(blob[10:13],bytes([129,0,5]))
        self.assertEqual(blob[46:],offline_cave.encode_profile(PROPOSAL,'ice')[9:])
        self.assertEqual(SharedCave(blob).version, 3)
        for rate in (0,101,True,None):
            with self.subTest(rate=rate),self.assertRaises(ValueError):offline_cave.encode_wildlife(PROPOSAL,'ice',rate,WILDLIFE)
        for bad in ([], WILDLIFE[:11], WILDLIFE+[WILDLIFE[0]], [{'species':'EGG','level':5}]*12,
                    [{'species':'MISSINGNO','level':5}]*12, [{'species':'MAGIKARP','level':True}]*12,
                    [{'species':'MAGIKARP','level':101}]*12, [{'species':'MAGIKARP','level':5,'extra':1}]*12):
            with self.subTest(bad=bad),self.assertRaises(ValueError):offline_cave.encode_wildlife(PROPOSAL,'ice',10,bad)

    def test_model_wildlife_requires_explicit_opt_in_and_validation(self):
        def wire(doc):
            return ('\n'.join(json.dumps(e) for e in [
                {'type':'item.completed','item':{'type':'agent_message','text':json.dumps(doc)}},
                {'type':'turn.completed'}])).encode()
        selected={**BLUEPRINT,'encounter_profile':'ice','encounter_rate':25,'wildlife':WILDLIFE}
        proposal,profile,rate,roster=author_cave.decode_blueprint_events(wire(selected),custom_wildlife=True)
        self.assertEqual(offline_cave.encode_wildlife(proposal,profile,rate,roster)[:8],b'EWGMAP03')
        with self.assertRaises(ValueError):author_cave.decode_blueprint_events(wire(selected))
        with self.assertRaises(ValueError):author_cave.decode_blueprint_events(wire({**selected,'wildlife':[{'species':'EGG','level':5}]*12}),custom_wildlife=True)
        self.assertIn('MAGIKARP',author_cave.prompt_for('fish cavern',custom_wildlife=True))
        catalog=json.dumps({'models':[{'slug':'gpt-6-luna'}]}).encode()
        with patch('world.author_cave.gm._run_author',side_effect=[b'codex-cli 0.156.1',catalog,wire(selected)]):
            proposal,blob=author_cave.author('fish cavern',custom_wildlife=True)
        self.assertEqual(blob,offline_cave.encode_wildlife(proposal,'ice',25,WILDLIFE))

    def test_offline_author_output_never_publishes_or_overwrites(self):
        blob=offline_cave.encode_wildlife(PROPOSAL,'ice',25,WILDLIFE)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'wild.bin'
            with patch('world.author_cave.author',return_value=(PROPOSAL,blob)) as author, \
                 patch('world.author_cave.publish_bytes') as publish,patch('builtins.print'):
                self.assertEqual(author_cave.main(['fish cave','--offline-wildlife-output',str(path)]),0)
                self.assertTrue(author.call_args.kwargs['custom_wildlife']);publish.assert_not_called()
                self.assertEqual(path.read_bytes(),blob)
                self.assertEqual(author_cave.main(['fish cave','--offline-wildlife-output',str(path)]),1)
                self.assertEqual(path.read_bytes(),blob);publish.assert_not_called()

    def test_native_wildlife_loader_lifecycle_and_atomic_rejection(self):
        generated=(ROOT/'src/platform/generated_map.c').read_text();sdl=(ROOT/'src/platform/sdl2.c').read_text()
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
#define GENERATED_CAVE_WILDLIFE 1
#define GEN_SIDE 31
#define GEN_CELLS 961
#define GENERATED_MAP_TEMPLATE_BYTES 961
#define GENERATED_WILDLIFE_BYTES 37
#define SPECIES_EGG 412
#define SPECIES_OLD_UNOWN_B 252
#define SPECIES_OLD_UNOWN_Z 276
struct WildPokemon {u8 minLevel,maxLevel;u16 species;};
struct WildPokemonInfo {u8 encounterRate;const struct WildPokemon *wildPokemon;};
static u8 sTemplate[GEN_CELLS];static bool8 sHasTemplate,sPrepared,inside=1,online;
static u8 sEncounterProfile;static bool8 sSharedEncounterProfile,sHasWildlife,sSharedWildlife;
static u8 sWildlifeRaw[GENERATED_WILDLIFE_BYTES];
static struct WildPokemon sWildlifeMons[12];static struct WildPokemonInfo sWildlifeInfo;
static bool8 GeneratedMap_IsInside(void){return inside;}
static bool8 WorldBridge_Enabled(void){return online;}
static FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
''' + ''.join(function(generated,n) for n in ('GeneratedMap_StageTemplate','GeneratedMap_SetEncounterProfile','GeneratedMap_ValidateWildlife','GeneratedMap_SetWildlife','GeneratedMap_Wildlife')) + function(sdl,'LoadGeneratedMapTemplate') + r'''
int main(int argc,char **argv){const struct WildPokemonInfo *p;u8 old[961];if(argc!=8)return 1;
 if(!LoadGeneratedMapTemplate(argv[1]))return 2;sPrepared=1;p=GeneratedMap_Wildlife();
 if(!p||p->encounterRate!=25||sEncounterProfile!=2)return 3;
 for(int i=0;i<12;i++)if(p->wildPokemon[i].species!=129||p->wildPokemon[i].minLevel!=5||p->wildPokemon[i].maxLevel!=5)return 4;
 online=1;if(GeneratedMap_Wildlife())return 5;online=0;inside=0;if(GeneratedMap_Wildlife())return 6;inside=1;
 memcpy(old,sTemplate,sizeof(old));
 for(int a=2;a<=6;a++)if(LoadGeneratedMapTemplate(argv[a])||memcmp(old,sTemplate,sizeof(old))||GeneratedMap_Wildlife()!=p)return 7;
 if(!LoadGeneratedMapTemplate(argv[7])||GeneratedMap_Wildlife())return 8;
 return 0;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c=root/'test.c';exe=root/'test';c.write_text(code)
            v3=offline_cave.encode_wildlife(PROPOSAL,'ice',25,WILDLIFE);v2=offline_cave.encode_profile(PROPOSAL,'meteor')
            invalid_rate=v3[:9]+b'\x00'+v3[10:]
            invalid_species=v3[:10]+(252).to_bytes(2,'little')+v3[12:]
            invalid_level=v3[:12]+b'\x00'+v3[13:]
            invalid_geometry=v3[:46]+b'.'+v3[47:]
            files=[root/f'f{i}' for i in range(7)]
            for f,data in zip(files,[v3,invalid_rate,invalid_species,invalid_level,invalid_geometry,v3+b'x',v2]):f.write_bytes(data)
            build=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe),*map(str,files)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr or str(result.returncode))

    def test_profile_only_native_loader_rejects_v3(self):
        source=(ROOT/'src/platform/sdl2.c').read_text()
        code=r"""
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef int bool8;
#define FALSE 0
#define GENERATED_CAVE_PROFILES 1
#define GENERATED_CAVE_WILDLIFE 0
#define GENERATED_MAP_TEMPLATE_BYTES 961
#define GENERATED_WILDLIFE_BYTES 37
static FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
static bool8 GeneratedMap_StageTemplate(const u8 *p,unsigned n){return n==961 && p[0]=='#';}
static bool8 GeneratedMap_SetEncounterProfile(u8 p){return p<=3;}
""" + function(source,'LoadGeneratedMapTemplate') + r"""
int main(int argc,char **argv){if(argc!=3)return 1;
 return !LoadGeneratedMapTemplate(argv[1]) || LoadGeneratedMapTemplate(argv[2]);}
"""
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c=root/'old.c';exe=root/'old';c.write_text(code)
            (root/'v2').write_bytes(offline_cave.encode_profile(PROPOSAL,'ice'))
            (root/'v3').write_bytes(offline_cave.encode_wildlife(PROPOSAL,'ice',25,WILDLIFE))
            build=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe),str(root/'v2'),str(root/'v3')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_native_encounter_dispatch_uses_roster_and_stock_checks(self):
        source=(ROOT/'src/wild_encounter.c').read_text()
        code=r'''
#include <stdint.h>
#include <stddef.h>
typedef int8_t s8;typedef uint16_t u16;typedef uint8_t u8;
#define TRUE 1
#define FALSE 0
#define WILD_AREA_LAND 0
#define WILD_CHECK_REPEL 1
#define WILD_CHECK_KEEN_EYE 2
struct WildPokemonInfo {int encounterRate;};static struct WildPokemonInfo info={25};
static const struct WildPokemonInfo *ptr;static int allowed=1,roll=1,generated=1,battles,flagsSeen;
static const struct WildPokemonInfo *GeneratedMap_Wildlife(void){return ptr;}
static int AllowWildCheckOnNewMetatile(void){return allowed;}
static int WildEncounterCheck(int rate,int flag){return rate==25 && !flag && roll;}
static int TryGenerateWildMon(const struct WildPokemonInfo *p,int area,int flags){flagsSeen=flags;return p==ptr && area==0 && generated;}
static void BattleSetup_StartWildBattle(void){battles++;}
''' + function(source,'TryGeneratedCaveWildEncounter') + function(source,'TryGeneratedCaveSweetScent') + r'''
int main(void){if(TryGeneratedCaveWildEncounter(1,1)!=-1)return 1;ptr=&info;
 allowed=0;if(TryGeneratedCaveWildEncounter(1,2)!=0)return 2;allowed=1;roll=0;
 if(TryGeneratedCaveWildEncounter(1,1)!=0)return 3;roll=1;generated=0;
 if(TryGeneratedCaveWildEncounter(1,1)!=0)return 4;generated=1;
 if(TryGeneratedCaveWildEncounter(1,1)!=1||battles!=1||flagsSeen!=3)return 5;
 ptr=0;if(TryGeneratedCaveSweetScent()!=-1)return 6;ptr=&info;generated=0;
 if(TryGeneratedCaveSweetScent()!=0)return 7;generated=1;
 if(TryGeneratedCaveSweetScent()!=1||battles!=2||flagsSeen!=0)return 8;
 return 0;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            c,exe=Path(tmp)/'test.c',Path(tmp)/'test';c.write_text(code)
            build=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_dexnav_is_disabled_only_for_custom_wildlife(self):
        source=(ROOT/'src/platform/dexnav_native.c').read_text()
        code=r"""
#include <stddef.h>
#include <stdint.h>
typedef uint32_t u32;typedef int bool8;
#define GENERATED_CAVE_WILDLIFE 1
#define TRUE 1
#define FALSE 0
#define FLAG_SYS_POKEDEX_GET 1
#define PYRAMID_LOCATION_NONE 0
#define MAPSEC_BATTLE_FRONTIER 9
#define PARTY_SIZE 6
#define MON_DATA_SPECIES 1
#define MON_DATA_IS_EGG 2
#define MON_DATA_HP 3
struct Pokemon {int unused;};static struct Pokemon gPlayerParty[PARTY_SIZE];
static struct {int inBattle;} gMain;static struct {int regionMapSectionId;} gMapHeader;
static int custom;
static void *GeneratedMap_Wildlife(void){return custom ? &custom : NULL;}
static int FlagGet(int x){(void)x;return 1;}
static int GetSafariZoneFlag(void){return 0;}static int InBattlePike(void){return 0;}
static int CurrentBattlePyramidLocation(void){return 0;}
static int IsOverworldLinkActive(void){return 0;}static int NativeLink_IsActive(void){return 0;}
static int GetMonData(struct Pokemon *p,int what){(void)p;return what==MON_DATA_SPECIES||what==MON_DATA_HP;}
static void BindTrainer(void){}
""" + function(source,'DexNavNative_Available') + r"""
int main(void){custom=1;if(DexNavNative_Available())return 1;
 custom=0;if(!DexNavNative_Available())return 2;return 0;}
"""
        with tempfile.TemporaryDirectory() as tmp:
            c,exe=Path(tmp)/'dex.c',Path(tmp)/'dex';c.write_text(code)
            build=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
