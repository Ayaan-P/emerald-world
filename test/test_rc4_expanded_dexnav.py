"""RC4 production-C DexNav seams. Disposable fixtures, not gameplay evidence."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_dexnav_lifecycle import function

ROOT = Path(__file__).resolve().parents[1]


def run_c(code, args=(), extra=()):
    with tempfile.TemporaryDirectory(prefix='rc4-dexnav-') as tmp:
        p = Path(tmp)
        (p / 'test.c').write_text(code)
        compiled = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                                   '-DPORTABLE', '-iquote', str(ROOT / 'include'),
                                   str(p / 'test.c'), *extra, '-o', str(p / 'test')],
                                  capture_output=True, text=True)
        if compiled.returncode:
            raise AssertionError(compiled.stderr)
        result = subprocess.run([str(p / 'test'), *args], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)


class ExpandedDexNav(unittest.TestCase):
    def test_versioned_supplement_restart_and_legacy_journal(self):
        import re
        from test_dexnav_progress import c_function
        native = (ROOT / 'src/platform/dexnav_native.c').read_text()
        dex = (ROOT / 'include/dexnav.h').read_text()
        header = (ROOT / 'include/platform/dexnav_native.h').read_text()
        state = header[header.index('struct DexNavNativeState\n'):header.index('extern struct DexNavNativeState')]
        globals_ = native[native.index('static u8 sTrainer[4]'):native.index('static u16 sBgPalette')]
        names = ('ProgressChecksum', 'ValidProgress', 'ProgressSequence', 'NewestProgressSlot',
                 'ExpandedProgressSize', 'ExpandedProgressChecksum', 'ValidExpandedProgress',
                 'LoadExpandedProgress', 'PersistExpandedProgress',
                 'BindTrainer', 'DexNavNative_Init', 'DexNavNative_Persist')
        bodies = '\n'.join((c_function if n == 'ProgressSequence' else function)(native, n) for n in names)
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "constants/species.h"
#include "platform/native_save.h"
typedef uint8_t u8;typedef uint16_t u16;typedef int16_t s16;typedef uint32_t u32;typedef u8 bool8;
#define TRUE 1
#define FALSE 0
static struct {u8 playerTrainerId[4];}trainer,*gSaveBlock2Ptr=&trainer;
static u16 sBattleOwner;
''' + re.search(r'enum EncounterType\s*\{.*?\};', dex, re.S).group() + '\n' + re.search(r'^#define DEXNAV_MASK_SPECIES\s+\S+', dex, re.M).group() + '\n' + state + '\nstatic struct DexNavNativeState gDexNavNativeState;\n' + globals_ + '\n' + bodies + r'''
int main(int argc,char **argv){
 assert(argc==3);memcpy(trainer.playerTrainerId,"ABCD",4);
 if(!strcmp(argv[2],"other"))trainer.playerTrainerId[0]='Z';
 DexNavNative_Init(argv[1],TRUE);BindTrainer();
 if(!strcmp(argv[2],"seed")){
  gDexNavNativeState.registeredSpecies=SPECIES_POOCHYENA;
  gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]=7;
  DexNavNative_Persist();
 }else if(!strcmp(argv[2],"write")){
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]==7);
  gDexNavNativeState.registeredSpecies=SPECIES_MELTAN;
  gDexNavNativeState.dexNavSearchLevels[SPECIES_MELTAN]=4;
  gDexNavNativeState.dexNavSearchLevels[SPECIES_GIMMIGHOUL_ROAMING]=3;
  gDexNavNativeState.dexNavSearchLevels[SPECIES_COSMOEM]=2;
  DexNavNative_Persist();
  gDexNavNativeState.dexNavSearchLevels[SPECIES_MELTAN]=5;
  DexNavNative_Persist();
 }else if(!strcmp(argv[2],"read")){
  assert(gDexNavNativeState.registeredSpecies==SPECIES_MELTAN);
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_MELTAN]==5);
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_GIMMIGHOUL_ROAMING]==3);
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_COSMOEM]==2);
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]==7);
  assert(!gDexNavNativeState.dexNavChain && !sBattleOwner);
 }else if(!strcmp(argv[2],"recover")){
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_MELTAN]==4);
  assert(!gDexNavNativeState.registeredSpecies); /* mismatched base sequence */
 }else if(!strcmp(argv[2],"smaller")){
  u32 size=16+SPECIES_COSMOEM+1-NUM_SPECIES;
  u8 oldJournal[2*(16+SPECIES_COSMOEM+1-NUM_SPECIES)];u16 sum;
  memset(oldJournal,0,sizeof(oldJournal));memcpy(oldJournal,"DNX1ABCD",8);
  oldJournal[8]=(SPECIES_COSMOEM+1)&255;oldJournal[9]=(SPECIES_COSMOEM+1)>>8;
  oldJournal[14+SPECIES_GIMMIGHOUL_ROAMING-NUM_SPECIES]=9;
  sum=ExpandedProgressChecksum(oldJournal,size);
  oldJournal[size-2]=sum&255;oldJournal[size-1]=sum>>8;
  memcpy(oldJournal+size,oldJournal,size);
  assert(NativeSave_Write(sExpandedFile,oldJournal,sizeof(oldJournal)));
 }else if(!strcmp(argv[2],"readsmall")){
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_GIMMIGHOUL_ROAMING]==9);
  assert(!gDexNavNativeState.dexNavSearchLevels[SPECIES_MELTAN]);
  DexNavNative_Persist();
 }else if(!strcmp(argv[2],"emptyadded")){
  assert(!gDexNavNativeState.dexNavSearchLevels[SPECIES_GIMMIGHOUL_ROAMING]);
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]==7);
 }else if(!strcmp(argv[2],"other")){
  assert(!gDexNavNativeState.dexNavSearchLevels[SPECIES_MELTAN]);
  assert(!gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]);
  assert(!gDexNavNativeState.registeredSpecies);
 }else assert(0);
 assert(ValidProgress(sDiskProgress));return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='rc4-dexnav-restart-') as tmp:
            p = Path(tmp)
            (p / 'test.c').write_text(code)
            result = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                                     '-DPORTABLE', '-iquote', str(ROOT / 'include'), str(p / 'test.c'),
                                     str(ROOT / 'src/platform/native_save.c'), '-o', str(p / 'test')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            save = p / 'trainer.sav'
            save.write_bytes(b'original save')
            def run(mode):
                result = subprocess.run([str(p / 'test'), str(save), mode], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            run('seed')
            # Existing RC3-only profile: no supplement is required for legacy import.
            supplement = Path(str(save) + '.dexnavx')
            supplement.unlink()
            run('write'); run('read'); run('other'); run('read')
            legacy = Path(str(save) + '.dexnav').read_bytes()
            self.assertEqual(len(legacy), 2 * (16 + 412))
            self.assertEqual(legacy[:4], b'DNV2')
            self.assertEqual(legacy[16 + 412:20 + 412], b'DNV2')
            self.assertEqual(save.read_bytes(), b'original save')
            self.assertEqual(supplement.stat().st_mode & 0o777, 0o600)
            data = bytearray(supplement.read_bytes())
            size = len(data) // 2
            sequences = [int.from_bytes(data[i * size + 12:i * size + 14], 'little') for i in range(2)]
            newest = sequences.index(max(sequences))
            data[newest * size + 14] ^= 1
            supplement.write_bytes(data)
            run('recover')
            supplement.unlink()
            run('smaller'); run('readsmall'); run('readsmall')
            # A malformed supplemental count must never copy beyond runtime state.
            data = bytearray(supplement.read_bytes())
            size = len(data) // 2
            for offset in (0, size):
                data[offset + 8:offset + 10] = b'\xff\xff'
            supplement.write_bytes(data)
            run('emptyadded')

    def test_expanded_seen_flags_are_forwarded_to_existing_dex_seam(self):
        native = (ROOT / 'src/platform/expanded_species.c').read_text()
        dex = (ROOT / 'src/dexnav.c').read_text()
        mapping = (ROOT / 'src/data/pokemon/expanded/dex_map.inc').read_text()
        code = r'''
#include <assert.h>
#include <stdint.h>
#include "constants/species.h"
#include "constants/pokedex.h"
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef u8 bool8;
#define FALSE 0
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
static const struct {u16 species,dexNumber;}sExpandedDexMap[]={
''' + mapping + r'''
};
static unsigned forwarded;
static bool8 GetSetPokedexFlag(u16 no,u8 mode){(void)no;(void)mode;forwarded++;return 1;}
''' + function(native, 'ExpandedSpecies_FromNationalDexNumber') + '\n' + function(dex, 'DexNavGetPokedexFlag') + r'''
int main(void){
 assert(DexNavGetPokedexFlag(NATIONAL_DEX_GIMMIGHOUL,0));
 assert(DexNavGetPokedexFlag(NATIONAL_DEX_COSMOEM,0));
 assert(DexNavGetPokedexFlag(NATIONAL_DEX_MELTAN,0));
 assert(DexNavGetPokedexFlag(1,0));assert(forwarded==4);
 assert(!DexNavGetPokedexFlag(0,0));assert(!DexNavGetPokedexFlag(65535,0));
 assert(forwarded==4);return 0;
}
'''
        run_c(code)

    def test_runtime_capacity_and_added_battle_credit(self):
        native = (ROOT / 'src/platform/dexnav_native.c').read_text()
        header = (ROOT / 'include/platform/dexnav_native.h').read_text()
        state = header[header.index('struct DexNavNativeState\n'):header.index('extern struct DexNavNativeState')]
        code = r'''
#include <assert.h>
#include <stdint.h>
#include "constants/species.h"
#include "constants/battle.h"
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef u8 bool8;
#define TRUE 1
#define FALSE 0
#define MON_DATA_SPECIES 0
#define MON_DATA_PERSONALITY 1
struct Mon {u16 species;u32 personality;}gEnemyParty[1];
static u16 sBattleOwner,gDexNavSpecies;static u32 sBattlePersonality;
static unsigned persisted;
static u32 GetMonData(struct Mon *m,unsigned f){return f==MON_DATA_SPECIES?m->species:m->personality;}
static void IncrementDexNavChain(void);
static void DexNavNative_Persist(void){persisted++;}
''' + state + r'''
static struct DexNavNativeState gDexNavNativeState;
static void IncrementDexNavChain(void){gDexNavNativeState.dexNavChain++;}
''' + '\n'.join(function(native, n) for n in ('DexNavNative_SetBattleOwner', 'DexNavNative_OwnsWildMon', 'DexNavNative_BattleFinished')) + '\n#define USE_DEXNAV_SEARCH_LEVELS TRUE\n' + function((ROOT / 'src/dexnav.c').read_text(), 'GetSearchLevel') + r'''
int main(void){
 u16 species[]={SPECIES_GIMMIGHOUL_ROAMING,SPECIES_COSMOEM,SPECIES_MELTAN};unsigned i;
 assert(sizeof(gDexNavNativeState.dexNavSearchLevels)==SPECIES_TABLE_COUNT);
 gDexNavNativeState.searching=TRUE;
 assert(GetSearchLevel(SPECIES_TABLE_COUNT)==0);
 assert(GetSearchLevel(65535)==0);
 for(i=0;i<3;i++){
  gEnemyParty[0]=(struct Mon){species[i],123};DexNavNative_SetBattleOwner(species[i]);
  DexNavNative_BattleFinished(B_OUTCOME_WON);DexNavNative_BattleFinished(B_OUTCOME_WON);
  assert(gDexNavNativeState.dexNavSearchLevels[species[i]]==1);
  DexNavNative_SetBattleOwner(species[i]);DexNavNative_BattleFinished(B_OUTCOME_CAUGHT);
  assert(gDexNavNativeState.dexNavSearchLevels[species[i]]==2);
  DexNavNative_SetBattleOwner(species[i]);DexNavNative_BattleFinished(B_OUTCOME_RAN);
  assert(gDexNavNativeState.dexNavSearchLevels[species[i]]==2 && !gDexNavNativeState.dexNavChain);
 }
 assert(persisted==6);return 0;
}
'''
        run_c(code)

    def test_effective_enumeration_and_level_lookup(self):
        native = (ROOT / 'src/platform/dexnav_native.c').read_text()
        dex = (ROOT / 'src/dexnav.c').read_text()
        resolver = (ROOT / 'src/platform/expanded_species.c').read_text()
        playable = function(resolver, 'ExpandedSpecies_IsPlayable').replace(
            '"../data/pokemon/expanded/playable_cases.inc"',
            '"' + str(ROOT / 'src/data/pokemon/expanded/playable_cases.inc') + '"')
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include "constants/species.h"
#include "constants/maps.h"
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef u8 bool8;
#define TRUE 1
#define FALSE 0
#define WORLD_RULE_EXPANDED_ROSTER 16
#define DEXNAV_HEADER_NONE 65535
#define NUM_LAND_MONS_ENCOUNTER_SLOTS 12
#define NUM_WATER_MONS_ENCOUNTER_SLOTS 5
#define NUM_HIDDEN_MONS_ENCOUNTER_SLOTS 3
#define MAX_LEVEL 100
#define MON_LEVEL_NONEXISTENT 255
#define ARRAY_COUNT(a) (sizeof(a) / sizeof((a)[0]))
static bool8 enabled, sFailed;
static bool8 WorldRules_Enabled(unsigned rule) { assert(rule == 16); return enabled; }
static struct { struct {u8 mapGroup,mapNum;} location;} save,*gSaveBlock1Ptr=&save;
enum EncounterType {ENCOUNTER_TYPE_LAND,ENCOUNTER_TYPE_WATER,ENCOUNTER_TYPE_HIDDEN};
struct WildPokemon {u8 minLevel,maxLevel;u16 species;};
struct WildPokemonInfo {u8 encounterRate;const struct WildPokemon *wildPokemon;};
static struct {const struct WildPokemonInfo *landMonsInfo,*waterMonsInfo;} gWildMonHeaders[1];
static struct {u16 landSpecies[12],waterSpecies[5],hiddenSpecies[3];} ui,*sDexNavUiDataPtr=&ui;
struct DexNavSearch {enum EncounterType environment;u16 species;u8 fldEffSpriteId,windowId,iconSpriteId,itemSpriteId,eyeSpriteId,ownedIconSpriteId,exclamationSpriteId,starSpriteIds[3],isHiddenMon,monLevel,hiddenSearch;};
static struct DexNavSearch *sDexNavSearchDataPtr;
static struct {u8 dexNavChain;bool8 searching;}gDexNavNativeState;
static u16 DexNavNative_GetHeader(void){return 0;}
static const struct WildPokemonInfo *DexNavNative_GetHiddenInfo(u16 h){(void)h;return 0;}
static u16 SpeciesToNationalPokedexNum(u16 s){return s;}
static u16 Random(void){return 0;}
''' + playable + '\n' + function(resolver, 'ExpandedSpecies_ResolveEncounter') + '\n' + '\n'.join(function(native, n) for n in ('DexNavNative_ResolveSpecies', 'DexNavNative_CollectSpecies')) + '\n' + '\n'.join(function(dex, n) for n in ('DexNavLoadEncounterData', 'GetEncounterLevelFromMapData', 'DexNavTryGenerateMonLevel')) + r'''
#define PLAYER_AVATAR_FLAG_SURFING 1
#define MAX_SPRITES 64
#define WINDOW_NONE 255
#define FLAG_GET_CAUGHT 1
static const u8 EventScript_NotFoundNearby[]={1},EventScript_TooDark[]={2};
static void ScriptContext_SetupScript(const u8 *s){(void)s;}
static bool8 TestPlayerAvatarFlags(unsigned f){(void)f;return FALSE;}
static void *AllocZeroed(unsigned size){return calloc(1,size);}
static void EndDexNavSearch(void){free(sDexNavSearchDataPtr);sDexNavSearchDataPtr=0;gDexNavNativeState.searching=FALSE;}
static void DexNavSearchBail(const u8 *s){(void)s;EndDexNavSearch();}
static u8 GetFlashLevel(void){return 0;}
static bool8 DexNavGetPokedexFlag(u16 n,u8 m){(void)n;(void)m;return TRUE;}
static bool8 DexNavNative_AcquireFieldResources(u16 s,bool8 owned,bool8 hidden){(void)owned;(void)hidden;return s<SPECIES_TABLE_COUNT;}
static bool8 TryStartHiddenMonFieldEffect(unsigned e,unsigned x,unsigned y,bool8 h){(void)e;(void)x;(void)y;(void)h;return TRUE;}
static void SetUpDexNavSearch(void){sDexNavSearchDataPtr->windowId=0;}
static bool8 DexNavNative_ResourcesFailed(void){return FALSE;}
''' + function(dex, 'InitDexNavSearch') + r'''
static u16 finalSpecies;
static int gEnemyParty[1];
static u32 CalculateDexNavShinyRolls(void){return 0;}
static void CreateWildMonExact(u16 s,u8 l){(void)l;finalSpecies=s;}
static bool8 IsMonShiny(int *m){(void)m;return FALSE;}
''' + function((ROOT / 'src/wild_encounter.c').read_text(), 'WildEncounter_CreateDexNavMon') + r'''
int main(void){
 struct WildPokemon slots[12];unsigned i;
 struct WildPokemonInfo info={20,slots};
 save.location.mapGroup=MAP_GROUP(MAP_ROUTE101);save.location.mapNum=MAP_NUM(MAP_ROUTE101);
 for(i=0;i<12;i++)slots[i]=(struct WildPokemon){2,3,i%3==0?SPECIES_ZIGZAGOON:i%3==1?SPECIES_POOCHYENA:SPECIES_WURMPLE};
 gWildMonHeaders[0].landMonsInfo=&info;
 DexNavLoadEncounterData();assert(ui.landSpecies[0]==SPECIES_ZIGZAGOON);
 enabled=1;DexNavLoadEncounterData();
 assert(ui.landSpecies[0]==SPECIES_ZIGZAGOON);
 assert(ui.landSpecies[1]==SPECIES_POOCHYENA);assert(ui.landSpecies[2]==SPECIES_WURMPLE);
 assert(ui.landSpecies[3]==SPECIES_GIMMIGHOUL_ROAMING);
 assert(ui.landSpecies[4]==SPECIES_COSMOEM);assert(ui.landSpecies[5]==SPECIES_MELTAN);assert(!ui.landSpecies[6]);
 assert(GetEncounterLevelFromMapData(SPECIES_GIMMIGHOUL_ROAMING,ENCOUNTER_TYPE_LAND)==2);
 assert(GetEncounterLevelFromMapData(SPECIES_COSMOEM,ENCOUNTER_TYPE_LAND)==2);
 assert(GetEncounterLevelFromMapData(SPECIES_MELTAN,ENCOUNTER_TYPE_LAND)==2);
 assert(GetEncounterLevelFromMapData(SPECIES_ZIGZAGOON,ENCOUNTER_TYPE_LAND)==2);
 for(i=0;i<6;i++){
  assert(!InitDexNavSearch(ui.landSpecies[i],ENCOUNTER_TYPE_LAND));
  assert(gDexNavNativeState.searching && sDexNavSearchDataPtr->species==ui.landSpecies[i]);
  assert(sDexNavSearchDataPtr->monLevel==12);
  WildEncounter_CreateDexNavMon(sDexNavSearchDataPtr->species,sDexNavSearchDataPtr->monLevel);
  assert(finalSpecies==ui.landSpecies[i]);EndDexNavSearch();
 }
 WildEncounter_CreateDexNavMon(SPECIES_ZIGZAGOON,2);assert(finalSpecies==SPECIES_ZIGZAGOON);
 assert(!InitDexNavSearch(SPECIES_TABLE_COUNT,ENCOUNTER_TYPE_LAND));assert(!sDexNavSearchDataPtr);
 enabled=0;assert(GetEncounterLevelFromMapData(SPECIES_MELTAN,ENCOUNTER_TYPE_LAND)==255);
 assert(InitDexNavSearch(SPECIES_MELTAN,ENCOUNTER_TYPE_LAND));assert(!sDexNavSearchDataPtr);
 return 0;
}
'''
        run_c(code)


if __name__ == '__main__':
    unittest.main()
