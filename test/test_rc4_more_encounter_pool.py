"""Execute production encounter/DexNav C seams. Not native gameplay evidence.

Only disposable C harnesses are compiled; this does not build the game.
"""
from pathlib import Path
import json
import subprocess
import unittest
from test_dexnav_lifecycle import function

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'build/rc4-more-pool'


def source(path):
    return (ROOT / path).read_text()


def run_c(name, code):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / name
    path.with_suffix('.c').write_text(code)
    build = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                            '-DPORTABLE', '-iquote', str(ROOT / 'include'),
                            str(path.with_suffix('.c')), '-o', str(path)],
                           capture_output=True, text=True)
    if build.returncode:
        raise AssertionError(build.stderr)
    result = subprocess.run([str(path)], capture_output=True, text=True)
    path.with_suffix('.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise AssertionError(result.stderr)


def policy():
    s = source('src/platform/expanded_species.c')
    playable = function(s, 'ExpandedSpecies_IsPlayable').replace(
        '"../data/pokemon/expanded/playable_cases.inc"',
        '"' + str(ROOT / 'src/data/pokemon/expanded/playable_cases.inc') + '"')
    return playable + '\n' + function(s, 'ExpandedSpecies_ResolveEncounter')


PREAMBLE = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "constants/species.h"
#include "constants/maps.h"
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef u8 bool8;
#define TRUE 1
#define FALSE 0
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define WORLD_RULE_EXPANDED_ROSTER 16
static bool8 enabled;
static unsigned draws;
static u16 roll;
u16 Random(void){++draws;return roll;}
static bool8 WorldRules_Enabled(unsigned rule){assert(rule==16);return enabled;}
static struct {struct {u8 mapGroup,mapNum;}location;} save,*gSaveBlock1Ptr=&save;
'''


class MoreEncounterPool(unittest.TestCase):
    def test_ordinary_pool_retains_original_with_one_opt_in_draw(self):
        wild = source('src/wild_encounter.c')
        code = PREAMBLE + policy() + r'''
static u16 finalSpecies;
static u8 finalLevel;
static unsigned exact;
static void CreateWildMonExact(u16 s,u8 l){finalSpecies=s;finalLevel=l;exact++;}
''' + function(wild, 'CreateWildMon') + r'''
static void check(u16 original,u16 extra,u8 group,u8 num){
 unsigned before;
 save.location.mapGroup=group;save.location.mapNum=num;
 enabled=FALSE;before=draws;
 CreateWildMon(original,4);assert(finalSpecies==original && finalLevel==4 && draws==before);
 enabled=TRUE;
 assert(ExpandedSpecies_ResolveEncounter(original,group,num)==extra);
 assert(draws==before); /* policy is pure */
 roll=0;CreateWildMon(original,4);assert(finalSpecies==original && draws==before+1);
 roll=1;CreateWildMon(original,4);assert(finalSpecies==extra && draws==before+2);
}
int main(void){
 check(SPECIES_ZIGZAGOON,SPECIES_GIMMIGHOUL_ROAMING,MAP_GROUP(MAP_ROUTE101),MAP_NUM(MAP_ROUTE101));
 check(SPECIES_POOCHYENA,SPECIES_COSMOEM,MAP_GROUP(MAP_ROUTE101),MAP_NUM(MAP_ROUTE101));
 check(SPECIES_WURMPLE,SPECIES_MELTAN,MAP_GROUP(MAP_ROUTE101),MAP_NUM(MAP_ROUTE101));
 check(SPECIES_RALTS,SPECIES_TYPE_NULL,MAP_GROUP(MAP_ROUTE102),MAP_NUM(MAP_ROUTE102));
 check(SPECIES_ZIGZAGOON,SPECIES_TURTWIG,MAP_GROUP(MAP_ROUTE103),MAP_NUM(MAP_ROUTE103));
 check(SPECIES_POOCHYENA,SPECIES_CHESPIN,MAP_GROUP(MAP_ROUTE103),MAP_NUM(MAP_ROUTE103));
 save.location.mapNum=MAP_NUM(MAP_ROUTE104);unsigned before=draws;
 CreateWildMon(SPECIES_ZIGZAGOON,5);assert(finalSpecies==SPECIES_ZIGZAGOON && draws==before);
 save.location.mapNum=MAP_NUM(MAP_ROUTE101);
 CreateWildMon(SPECIES_RALTS,5);assert(finalSpecies==SPECIES_RALTS && draws==before);
 assert(exact==20);puts("original/extra outcomes and conditional RNG verified");return 0;
}
'''
        run_c('ordinary', code)


    def test_dexnav_enumerates_complete_real_route_pools_and_levels(self):
        native = source('src/platform/dexnav_native.c')
        dex = source('src/dexnav.c')
        data = json.loads(source('src/data/wild_encounters.json'))
        routes = data['wild_encounter_groups'][0]['encounters']
        bindings = {
            'MAP_ROUTE101': {'SPECIES_ZIGZAGOON': 'SPECIES_GIMMIGHOUL_ROAMING',
                             'SPECIES_POOCHYENA': 'SPECIES_COSMOEM', 'SPECIES_WURMPLE': 'SPECIES_MELTAN'},
            'MAP_ROUTE102': {'SPECIES_RALTS': 'SPECIES_TYPE_NULL'},
            'MAP_ROUTE103': {'SPECIES_ZIGZAGOON': 'SPECIES_TURTWIG', 'SPECIES_POOCHYENA': 'SPECIES_CHESPIN'},
        }
        code = PREAMBLE + r'''
#define DEXNAV_HEADER_NONE 65535
#define NUM_LAND_MONS_ENCOUNTER_SLOTS 12
#define NUM_WATER_MONS_ENCOUNTER_SLOTS 5
#define NUM_HIDDEN_MONS_ENCOUNTER_SLOTS 3
#define MAX_LEVEL 100
#define MON_LEVEL_NONEXISTENT 255
struct WildPokemon {u8 minLevel,maxLevel;u16 species;};
struct WildPokemonInfo {u8 encounterRate;const struct WildPokemon *wildPokemon;};
static struct {const struct WildPokemonInfo *landMonsInfo,*waterMonsInfo;}gWildMonHeaders[1];
static struct {u16 landSpecies[12],waterSpecies[5],hiddenSpecies[3];}ui,*sDexNavUiDataPtr=&ui;
enum EncounterType {ENCOUNTER_TYPE_LAND,ENCOUNTER_TYPE_WATER,ENCOUNTER_TYPE_HIDDEN};
static struct {enum EncounterType environment;}search,*sDexNavSearchDataPtr=&search;
static bool8 sFailed;
u16 SpeciesToNationalPokedexNum(u16 species){return species;}
static u16 DexNavNative_GetHeader(void){return 0;}
static const struct WildPokemonInfo *DexNavNative_GetHiddenInfo(u16 h){(void)h;return NULL;}
''' + policy() + '\n' + function(native, 'DexNavNative_ResolveSpecies') + '\n'
        code += function(native, 'DexNavNative_CollectSpecies') + '\n'
        code += '\n'.join(function(dex, name) for name in
                          ('DexNavLoadEncounterData', 'GetEncounterLevelFromMapData'))
        code += r'''
static u16 finalSpecies;
static u8 finalLevel;
static void CreateWildMonExact(u16 s,u8 l){finalSpecies=s;finalLevel=l;}
''' + function(source('src/wild_encounter.c'), 'CreateWildMon')
        code += '\nint main(void){ roll=0;\n'
        counts = []
        for route in routes:
            map_ = route['map']
            code += '{\nsave.location.mapGroup=MAP_GROUP(' + map_ + ');save.location.mapNum=MAP_NUM(' + map_ + ');\n'
            for field, member, env, capacity in [('land_mons', 'land', 'LAND', 12), ('water_mons', 'water', 'WATER', 5)]:
                info = route.get(field)
                if info is None:
                    code += f'gWildMonHeaders[0].{member}MonsInfo=NULL;\n'
                    continue
                mons = info['mons']
                initial = ','.join('{%d,%d,%s}' % (m['min_level'], m['max_level'], m['species']) for m in mons)
                code += f'static const struct WildPokemon {member}Mons[]={{' + initial + '};\n'
                code += f'static const struct WildPokemonInfo {member}Info={{' + str(info['encounter_rate']) + f',{member}Mons}};\n'
                code += f'gWildMonHeaders[0].{member}MonsInfo=&{member}Info;\n'
            for flag in [0, 1]:
                code += f'enabled={flag};unsigned before{flag}=draws;DexNavLoadEncounterData();assert(!sFailed && draws==before{flag});\n'
                for field, member, env, capacity in [('land_mons', 'land', 'LAND', 12), ('water_mons', 'water', 'WATER', 5)]:
                    info = route.get(field)
                    if info:
                        for mon in info['mons']:
                            original = mon['species']
                            extra = bindings.get(map_, {}).get(original, original) if flag else original
                            for random_value, target in [(0, original), (1, extra)]:
                                calls = int(extra != original)
                                code += '{unsigned before=draws;roll=' + str(random_value) + ';'
                                code += f'CreateWildMon({original},{mon["min_level"]});'
                                code += f'assert(finalSpecies=={target} && finalLevel=={mon["min_level"]} && draws==before+{calls});}}\n'
                    originals = list(dict.fromkeys(m['species'] for m in info['mons'])) if info and info['encounter_rate'] else []
                    expected = list(originals)
                    if flag:
                        expected += [v for k, v in bindings.get(map_, {}).items() if k in originals and v not in expected]
                    self.assertLessEqual(len(expected), capacity, map_)
                    if flag and field == 'land_mons':
                        counts.append({'map': map_, 'base': len(originals), 'more': len(expected), 'capacity': capacity})
                    # Stable base ordering, extras may follow source-slot order.
                    for i, species in enumerate(originals):
                        code += f'assert(ui.{member}Species[{i}]=={species});\n'
                    for species in expected:
                        code += '{unsigned j;for(j=0;j<' + str(capacity) + f';++j)if(ui.{member}Species[j]=={species})break;assert(j<{capacity});}}\n'
                        matching = [m for m in info['mons'] if m['species'] == species or (flag and bindings.get(map_, {}).get(m['species']) == species)]
                        low = min(m['min_level'] for m in matching)
                        high = max(m['max_level'] for m in matching)
                        code += f'roll=0;assert(GetEncounterLevelFromMapData({species},ENCOUNTER_TYPE_{env})=={low});\n'
                        code += f'roll={high-low};assert(GetEncounterLevelFromMapData({species},ENCOUNTER_TYPE_{env})=={high});\n'
                    code += '{unsigned j,n=0;for(j=0;j<' + str(capacity) + f';++j)if(ui.{member}Species[j])++n;assert(n=={len(expected)});}}\n'
            code += '}\n'
        code += 'assert(GetEncounterLevelFromMapData(SPECIES_QUILLADIN,ENCOUNTER_TYPE_LAND)==MON_LEVEL_NONEXISTENT);puts("all route base/extra pools and levels verified");return 0;}\n'
        run_c('dexnav-pools', code)
        (ARTIFACTS / 'route-capacity.json').write_text(json.dumps(counts, indent=2) + '\n')


    def test_captured_all_symbols_require_native_and_extra(self):
        dex = source('src/dexnav.c')
        native = source('src/platform/dexnav_native.c')
        code = PREAMBLE + r'''
#define FLAG_GET_CAUGHT 1
#define NUM_LAND_MONS_ENCOUNTER_SLOTS 12
#define NUM_WATER_MONS_ENCOUNTER_SLOTS 5
#define NUM_HIDDEN_MONS_ENCOUNTER_SLOTS 3
struct WildPokemon {u8 minLevel,maxLevel;u16 species;};
struct WildPokemonInfo {u8 encounterRate;const struct WildPokemon *wildPokemon;};
static struct {const struct WildPokemonInfo *landMonsInfo,*waterMonsInfo;}gWildMonHeaders[1];
static const struct WildPokemonInfo *hiddenInfo;
static const struct WildPokemonInfo *DexNavNative_GetHiddenInfo(u16 h){(void)h;return hiddenInfo;}
static bool8 caught[SPECIES_TABLE_COUNT];
static u16 SpeciesToNationalPokedexNum(u16 s){return s;}
static bool8 DexNavGetPokedexFlag(u16 s,u8 mode){assert(mode==FLAG_GET_CAUGHT);return caught[s];}
''' + policy() + '\n' + function(native, 'DexNavNative_ResolveSpecies') + '\n'
        code += '\n'.join(function(dex, name) for name in
                          ('CapturedAllLandMons', 'CapturedAllWaterMons', 'CapturedAllHiddenMons'))
        code += r'''
int main(void){
 struct WildPokemon slots[12];unsigned i;
 for(i=0;i<12;++i)slots[i]=(struct WildPokemon){2,3,SPECIES_ZIGZAGOON};
 const struct WildPokemonInfo info={20,slots};
 gWildMonHeaders[0].landMonsInfo=&info;gWildMonHeaders[0].waterMonsInfo=&info;hiddenInfo=&info;
 save.location.mapGroup=MAP_GROUP(MAP_ROUTE103);save.location.mapNum=MAP_NUM(MAP_ROUTE103);
 enabled=TRUE;caught[SPECIES_TURTWIG]=TRUE;
 assert(!CapturedAllLandMons(0));assert(!CapturedAllWaterMons(0));assert(!CapturedAllHiddenMons(0));
 caught[SPECIES_TURTWIG]=FALSE;caught[SPECIES_ZIGZAGOON]=TRUE;
 assert(!CapturedAllLandMons(0));assert(!CapturedAllWaterMons(0));assert(!CapturedAllHiddenMons(0));
 enabled=FALSE;
 assert(CapturedAllLandMons(0));assert(CapturedAllWaterMons(0));assert(CapturedAllHiddenMons(0));
 enabled=TRUE;caught[SPECIES_TURTWIG]=TRUE;
 assert(CapturedAllLandMons(0));assert(CapturedAllWaterMons(0));assert(CapturedAllHiddenMons(0));
 assert(draws==0 && roll==0);return 0;
}
'''
        run_c('captured-all', code)


    def test_exact_hunt_never_selects_variant_or_consumes_overlay_rng(self):
        wild = source('src/wild_encounter.c')
        native = source('src/platform/dexnav_native.c')
        code = PREAMBLE + policy() + r'''
static int gEnemyParty[1];
static u16 finalSpecies;
static u8 finalLevel;
static unsigned exact;
static u32 CalculateDexNavShinyRolls(void){return 0;}
static bool8 IsMonShiny(int *m){(void)m;return FALSE;}
static void CreateWildMonExact(u16 s,u8 l){finalSpecies=s;finalLevel=l;++exact;}
''' + function(native, 'DexNavNative_ResolveSpecies') + '\n'
        code += function(wild, 'WildEncounter_CreateDexNavMon') + r'''
int main(void){
 u16 species[]={SPECIES_WURMPLE,SPECIES_ZIGZAGOON,SPECIES_POOCHYENA,SPECIES_RALTS,
 SPECIES_GIMMIGHOUL_ROAMING,SPECIES_COSMOEM,SPECIES_MELTAN,SPECIES_TYPE_NULL,SPECIES_TURTWIG,SPECIES_CHESPIN};
 u8 maps[]={MAP_NUM(MAP_ROUTE101),MAP_NUM(MAP_ROUTE102),MAP_NUM(MAP_ROUTE103)};
 unsigned i,j;save.location.mapGroup=MAP_GROUP(MAP_ROUTE101);enabled=TRUE;
 for(j=0;j<ARRAY_COUNT(maps);++j){save.location.mapNum=maps[j];
  for(i=0;i<ARRAY_COUNT(species);++i){unsigned before=exact;
   /* The stable lookup remains separately callable, not a hunt mutation. */
   (void)DexNavNative_ResolveSpecies(species[i]);
   WildEncounter_CreateDexNavMon(species[i],7);
   assert(finalSpecies==species[i] && finalLevel==7 && exact==before+1);
  }
 }
 assert(draws==0 && roll==0);
 assert(SPECIES_TABLE_COUNT==947);
 u16 selected[]={SPECIES_GIMMIGHOUL_ROAMING,SPECIES_COSMOEM,SPECIES_MELTAN,SPECIES_TYPE_NULL,
 SPECIES_TURTWIG,SPECIES_GROTLE,SPECIES_TORTERRA,SPECIES_CHESPIN,SPECIES_QUILLADIN,
 SPECIES_ARROKUDA,SPECIES_KUBFU};
 assert(ARRAY_COUNT(selected)==11);
 for(i=0;i<ARRAY_COUNT(selected);++i)assert(ExpandedSpecies_IsPlayable(selected[i]));
 puts("intentional targets are exact; all 11 selected generated species playable");return 0;
}
'''
        run_c('exact-hunts', code)

    def test_collection_overflow_is_explicit_and_never_overwrites_base(self):
        native = source('src/platform/dexnav_native.c')
        code = PREAMBLE + r'''
struct WildPokemon {u8 minLevel,maxLevel;u16 species;};
struct WildPokemonInfo {u8 encounterRate;const struct WildPokemon *wildPokemon;};
static bool8 sFailed;
static u16 SpeciesToNationalPokedexNum(u16 s){return s;}
''' + policy() + '\n' + function(native, 'DexNavNative_ResolveSpecies') + '\n'
        code += function(native, 'DexNavNative_CollectSpecies') + r'''
int main(void){
 const struct WildPokemon mons[]={{2,3,SPECIES_ZIGZAGOON},{2,3,SPECIES_POOCHYENA},
 {2,3,SPECIES_ZIGZAGOON},{2,3,SPECIES_WURMPLE}};
 const struct WildPokemonInfo info={20,mons};
 struct {u16 out[3];u16 guard;} guarded={{0},0xbeef};
 save.location.mapGroup=MAP_GROUP(MAP_ROUTE101);save.location.mapNum=MAP_NUM(MAP_ROUTE101);
 enabled=FALSE;
 assert(DexNavNative_CollectSpecies(&info,4,guarded.out,3) && !sFailed);
 assert(guarded.out[0]==SPECIES_ZIGZAGOON && guarded.out[1]==SPECIES_POOCHYENA && guarded.out[2]==SPECIES_WURMPLE);
 enabled=TRUE;
 assert(!DexNavNative_CollectSpecies(&info,4,guarded.out,3) && sFailed);
 assert(guarded.guard==0xbeef && guarded.out[0]==SPECIES_ZIGZAGOON && guarded.out[1]==SPECIES_POOCHYENA && guarded.out[2]==SPECIES_WURMPLE);
 assert(draws==0 && roll==0);
 return 0;
}
'''
        run_c('overflow', code)


if __name__ == '__main__':
    unittest.main()
