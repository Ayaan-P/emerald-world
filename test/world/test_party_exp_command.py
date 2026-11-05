"""Compile real EXP command calculation/dispatch cases with isolated battle stubs.

This is a component harness, not a native game build or multiplayer acceptance.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

PRELUDE=r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int32_t s32; typedef uint8_t bool8;
#define TRUE 1
#define FALSE 0
#define SPECIES_NONE 0
#define PARTY_SIZE 6
#define MAX_LEVEL 100
#define ITEM_ENIGMA_BERRY 999
#define HOLD_EFFECT_EXP_SHARE 1
#define HOLD_EFFECT_LUCKY_EGG 2
#define BATTLE_TYPE_TRAINER 1
#define BATTLE_TYPE_DOUBLE 2
#define BATTLE_TYPE_INGAME_PARTNER 4
#define STRINGID_EMPTYSTRING4 0
#define STRINGID_ABOOSTED 1
#define STRINGID_PKMNGAINEDEXP 2
#define MUS_VICTORY_WILD 1
#define PREPARE_MON_NICK_WITH_PREFIX_BUFFER(...) ((void)0)
#define PREPARE_STRING_BUFFER(...) ((void)0)
#define PREPARE_WORD_NUMBER_BUFFER(...) ((void)0)
#define SAFE_DIV(a,b) ((b)?(a)/(b):0)
#include "party_exp.h"
enum {MON_DATA_SPECIES, MON_DATA_HP, MON_DATA_HELD_ITEM, MON_DATA_LEVEL, MON_DATA_IS_EGG};
struct Pokemon {u16 species,hp,item,level,egg;};
struct Pokemon gPlayerParty[6];
struct Battle {u16 expValue; u8 expGetterMonId, sentInPokes, expGetterBattlerId, wildVictorySong;};
struct Battle battle,*gBattleStruct=&battle;
struct {u8 getexpState;} gBattleScripting;
struct {u16 species, level, hp;} gBattleMons[4];
struct {u16 expYield;} gSpeciesInfo[2];
struct {struct {u8 holdEffect;} enigmaBerry;} save1,*gSaveBlock1Ptr=&save1;
u16 gBitTable[]={1,2,4,8,16,32};
u16 gExpShareExp; s32 gBattleMoveDamage; u32 gBattleTypeFlags;
u8 gBattlerFainted=1, gBattleControllerExecFlags, gAbsentBattlerFlags, gBattlerPartyIndexes[4];
int modern, evCount[6];
static int GetMonData(struct Pokemon *p,int field) {
 switch(field) {case MON_DATA_SPECIES:return p->species; case MON_DATA_HP:return p->hp;
 case MON_DATA_HELD_ITEM:return p->item;case MON_DATA_LEVEL:return p->level;
 case MON_DATA_IS_EGG:return p->egg;default:return 0;}}
static int GetItemHoldEffect(int item) {return item;}
static int IsTradedMon(struct Pokemon *p) {(void)p;return 0;}
static void BattleStopLowHpSound(void) {}
static void PlayBGM(int n) {(void)n;}
static void PrepareStringBattle(int n,int b) {(void)n;(void)b;}
static void MonGainEVs(struct Pokemon *p,int s) {(void)s;evCount[p-gPlayerParty]++;}
'''

class CommandTests(unittest.TestCase):
    def test_real_calculation_and_award_dispatch(self):
        source=(ROOT/'src/battle_script_commands.c').read_text()
        body=source.split('static void Cmd_getexp(void)\n{',1)[1]
        cases=body.split('    case 1: // calculate experience points to redistribute',1)[1].split('    case 3: // Set stats and give exp',1)[0]
        cases='    case 1: // calculate experience points to redistribute'+cases
        fn=r'''
static void command(int sentIn) {
 u16 item; s32 i,viaExpShare=0;u8 holdEffect;
 bool8 partyExpShare=modern && !(gBattleTypeFlags & BATTLE_TYPE_INGAME_PARTNER);
 u16 *exp=&gBattleStruct->expValue;
 switch(gBattleScripting.getexpState) {
'''+cases+r'''
 default:break;
 }
}
static int award(unsigned i) {
 battle.expGetterMonId=i;gBattleScripting.getexpState=2;gBattleMoveDamage=-1;
 command(0);return gBattleMoveDamage;
}
int main(void) {
 gSpeciesInfo[1].expYield=70;gBattleMons[1].species=1;gBattleMons[1].level=10;
 gBattleMons[0].hp=10;
 gPlayerParty[0]=(struct Pokemon){1,20,0,10,0};
 gPlayerParty[1]=(struct Pokemon){1,20,0,10,0};
 gPlayerParty[2]=(struct Pokemon){1,0,0,10,0};
 gPlayerParty[3]=(struct Pokemon){1,20,0,10,1};
 gPlayerParty[4]=(struct Pokemon){1,20,1,10,0};
 modern=1;gBattleScripting.getexpState=1;command(1);
 assert(gBattleMoveDamage==100 && evCount[0]==1);
 assert(award(1)==50 && evCount[1]==1);
 assert(award(2)==0 && evCount[2]==0);
 assert(award(3)==0 && evCount[3]==0);
 assert(award(4)==50 && evCount[4]==1);
 assert(award(5)==0 && evCount[5]==0);
 memset(evCount,0,sizeof(evCount));modern=0;
 gBattleScripting.getexpState=1;command(1);
 assert(gBattleMoveDamage==50 && evCount[0]==1);
 assert(award(1)==0 && evCount[1]==0);
 assert(award(4)==50 && evCount[4]==1);
 /* A co-op owner with no participation mask still gets a bench share. */
 memset(evCount,0,sizeof(evCount));modern=1;
 gBattleScripting.getexpState=1;command(0);
 assert(gBattleMoveDamage==50 && evCount[0]==1);
 assert(award(1)==50 && evCount[1]==1);
 /* NPC partner uses the unmodified vanilla held-share rules. */
 memset(evCount,0,sizeof(evCount));gBattleTypeFlags=BATTLE_TYPE_INGAME_PARTNER;
 gBattleScripting.getexpState=1;command(1);
 assert(gBattleMoveDamage==50);
 assert(award(1)==0 && evCount[1]==0);
 /* Ordinary native item and trainer multipliers remain after the base share. */
 gBattleTypeFlags=BATTLE_TYPE_TRAINER;gPlayerParty[1].item=HOLD_EFFECT_LUCKY_EGG;
 gBattleScripting.getexpState=1;command(1);
 assert(award(1)==112);
 gPlayerParty[1].level=MAX_LEVEL;gBattleScripting.getexpState=1;command(1);
 assert(award(1)==0);
 return 0;
}'''
        with tempfile.TemporaryDirectory() as d:
            c=Path(d)/'t.c';exe=Path(d)/'t';c.write_text(PRELUDE+fn)
            result=subprocess.run(['cc','-std=c99','-I',str(ROOT/'include'),str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
