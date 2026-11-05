"""Compile production damage calculation with controlled battle stubs."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]

PRELUDE=r'''
#include <assert.h>
#include <stdint.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int32_t s32;typedef uint8_t bool8;
#define FALSE 0
#define UNUSED __attribute__((unused))
#define TYPE_NORMAL 0
#define TYPE_BUG 6
#define TYPE_MYSTERY 9
#define TYPE_FIRE 10
#define TYPE_WATER 11
#define TYPE_GRASS 12
#define TYPE_ELECTRIC 13
#define TYPE_ICE 15
#define TYPE_DARK 17
#define BATTLE_TYPE_LINK 1
#define BATTLE_TYPE_RECORDED 2
#define BATTLE_TYPE_RECORDED_LINK 4
#define BATTLE_TYPE_DOUBLE 8
#define BATTLE_TYPE_FRONTIER 16
#define IS_TYPE_PHYSICAL(t) ((t)<TYPE_MYSTERY)
#define IS_TYPE_SPECIAL(t) ((t)>TYPE_MYSTERY)
#define DYNAMIC_TYPE_MASK 63
#define DEFAULT_STAT_STAGE 6
#define STAT_ATK 0
#define STAT_DEF 1
#define STAT_SPATK 2
#define STAT_SPDEF 3
#define STATUS1_BURN 1
#define SIDE_STATUS_REFLECT 1
#define SIDE_STATUS_LIGHTSCREEN 2
#define B_WEATHER_RAIN_TEMPORARY 1
#define B_WEATHER_RAIN 1
#define B_WEATHER_SUN 2
#define B_WEATHER_SANDSTORM 4
#define B_WEATHER_HAIL 8
#define WEATHER_HAS_EFFECT2 1
#define RESOURCE_FLAG_FLASH_FIRE 1
#define MOVE_TARGET_BOTH 3
#define BATTLE_ALIVE_DEF_SIDE 1
#define EFFECT_EXPLOSION 200
#define ITEM_ENIGMA_BERRY 999
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define ABILITY_ON_FIELD2(x) 0
#define APPLY_STAT_MOD(var,mon,stat,index) (var)=(stat);
'''

class DamageTests(unittest.TestCase):
    def test_real_damage_function_categories_and_type_modifiers(self):
        text=(ROOT/'src/pokemon.c').read_text()
        body=text.split('s32 CalculateBaseDamage(',1)[1].split('\n}',1)[0]
        fn='s32 CalculateBaseDamage('+body+'\n}'
        prefixes=('ABILITY_','HOLD_EFFECT_','SPECIES_','FLAG_BADGE','ABILITYEFFECT_')
        constants=sorted({n for n in re.findall(r'\b[A-Z][A-Z0-9_]+\b',fn)
                          if n.startswith(prefixes) and n not in ('ABILITY_ON_FIELD2',)})
        defines='\n'.join(f'#define {n} {100+i}' for i,n in enumerate(constants))+'\n'
        stubs=r'''
struct BattlePokemon {u16 ability,attack,defense,hp,item,level,maxHP,spAttack,spDefense,species;u8 statStages[8];u32 status1;};
struct BattleMove {u16 power,type,effect,target;};struct BattleMove gBattleMoves[MOVES_COUNT];
struct Berry {u8 holdEffect,holdEffectParam;} gEnigmaBerries[4];
struct Flags {u32 flags[4];};struct Resources {struct Flags *flags;};
struct Flags flags;struct Resources resources={&flags},*gBattleResources=&resources;
u32 gBattleTypeFlags,gBattleWeather,gBattleMovePower;u8 gCritMultiplier=1;u16 gCurrentMove;
static const u16 sHoldEffectToType[][2]={{0,0}};
int flag,linked;
int FlagGet(int id) {(void)id;return flag;}
int NativeLink_IsActive(void) {return linked;}
#include "battle_move_split.h"
int GetItemHoldEffect(int x) {(void)x;return 0;}
int GetItemHoldEffectParam(int x) {(void)x;return 0;}
int ShouldGetStatBadgeBoost(int x,int y) {(void)x;(void)y;return 0;}
int AbilityBattleEffects(int a,int b,int c,int d,int e) {(void)a;(void)b;(void)c;(void)d;(void)e;return 0;}
int CountAliveMonsInBattle(int x) {(void)x;return 1;}
'''
        main=r'''
int main(void) {
 struct BattlePokemon a={0},d={0};
 a.attack=100;a.spAttack=200;a.defense=100;a.spDefense=100;a.level=50;a.hp=a.maxHP=100;
 d.defense=d.spDefense=100;gCurrentMove=MOVE_FIRE_PUNCH;
 gBattleMoves[MOVE_FIRE_PUNCH]=(struct BattleMove){75,TYPE_FIRE,0,0};
 flag=0;assert(CalculateBaseDamage(&a,&d,MOVE_FIRE_PUNCH,0,0,0,0,1)==68);
 d.ability=ABILITY_THICK_FAT;assert(CalculateBaseDamage(&a,&d,MOVE_FIRE_PUNCH,0,0,0,0,1)==35);d.ability=0;
 gBattleWeather=B_WEATHER_SUN;assert(CalculateBaseDamage(&a,&d,MOVE_FIRE_PUNCH,0,0,0,0,1)==101);gBattleWeather=0;
 flag=1;assert(CalculateBaseDamage(&a,&d,MOVE_FIRE_PUNCH,0,0,0,0,1)==35);
 assert(CalculateBaseDamage(&a,&d,MOVE_FIRE_PUNCH,SIDE_STATUS_REFLECT,0,0,0,1)==18);
 a.status1=STATUS1_BURN;assert(CalculateBaseDamage(&a,&d,MOVE_FIRE_PUNCH,0,0,0,0,1)==18);a.status1=0;
 d.ability=ABILITY_THICK_FAT;assert(CalculateBaseDamage(&a,&d,MOVE_FIRE_PUNCH,0,0,0,0,1)==18);d.ability=0;
 gBattleWeather=B_WEATHER_SUN;assert(CalculateBaseDamage(&a,&d,MOVE_FIRE_PUNCH,0,0,0,0,1)==51);
 gBattleWeather=B_WEATHER_RAIN;assert(CalculateBaseDamage(&a,&d,MOVE_FIRE_PUNCH,0,0,0,0,1)==18);
 gBattleWeather=0;flags.flags[0]=RESOURCE_FLAG_FLASH_FIRE;
 assert(CalculateBaseDamage(&a,&d,MOVE_FIRE_PUNCH,0,0,0,0,1)==51);
 flags.flags[0]=0;gCurrentMove=MOVE_RAZOR_WIND;
 gBattleMoves[MOVE_RAZOR_WIND]=(struct BattleMove){80,TYPE_NORMAL,0,0};
 flag=0;assert(CalculateBaseDamage(&a,&d,MOVE_RAZOR_WIND,0,0,0,0,1)==37);
 flag=1;assert(CalculateBaseDamage(&a,&d,MOVE_RAZOR_WIND,0,0,0,0,1)==72);
 assert(CalculateBaseDamage(&a,&d,MOVE_RAZOR_WIND,SIDE_STATUS_LIGHTSCREEN,0,0,0,1)==37);
 a.status1=STATUS1_BURN;
 assert(CalculateBaseDamage(&a,&d,MOVE_RAZOR_WIND,0,0,0,0,1)==72);
 /* Confusion uses Pound even if the selected move was Solar Beam. */
 a.status1=0;gBattleWeather=B_WEATHER_RAIN;gCurrentMove=MOVE_SOLAR_BEAM;
 gBattleMoves[MOVE_POUND]=(struct BattleMove){40,TYPE_NORMAL,0,0};
 assert(CalculateBaseDamage(&a,&d,MOVE_POUND,0,0,0,0,1)==19);
 return 0;
}'''
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'constants').mkdir();(root/'platform').mkdir()
            (root/'event_data.h').write_text('int FlagGet(int);\n')
            (root/'constants/flags.h').write_text('#define FLAG_MODERN_MOVE_SPLIT 1\n')
            (root/'constants/moves.h').write_text((ROOT/'include/constants/moves.h').read_text())
            (root/'platform/native_link.h').write_text('int NativeLink_IsActive(void);\n')
            (root/'battle_move_split.h').write_text((ROOT/'include/battle_move_split.h').read_text())
            c=root/'t.c';exe=root/'t'
            c.write_text(PRELUDE+'#include "constants/moves.h"\n'+defines+stubs+fn+main)
            result=subprocess.run(['cc','-std=c99','-DPORTABLE','-I',str(root),str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
