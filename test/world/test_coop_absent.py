"""Production wild-reserve lookup must not resurrect a nonexistent fourth battler."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]

class CoopAbsentOpponent(unittest.TestCase):
    def test_no_link_trainer_lookup_for_wild_opponents(self):
        code = r'''
#include <stdint.h>
#include <assert.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int32_t s32; typedef uint8_t bool8;
#define PORTABLE 1
#define TRUE 1
#define FALSE 0
#define PARTY_SIZE 6
#define MULTI_PARTY_SIZE 3
#define MAX_LINK_PLAYERS 4
#define BATTLE_TYPE_DOUBLE 1
#define BATTLE_TYPE_INGAME_PARTNER 2
#define BATTLE_TYPE_MULTI 4
#define BATTLE_TYPE_TOWER_LINK_MULTI 8
#define BATTLE_TYPE_TWO_OPPONENTS 16
#define BIT_FLANK 2
#define B_SIDE_PLAYER 0
#define B_SIDE_OPPONENT 1
#define B_POSITION_OPPONENT_LEFT 1
#define B_POSITION_OPPONENT_RIGHT 3
#define B_POSITION_PLAYER_LEFT 0
#define B_POSITION_PLAYER_RIGHT 2
#define MON_DATA_HP 1
#define MON_DATA_SPECIES_OR_EGG 2
#define SPECIES_NONE 0
#define SPECIES_EGG 412
struct Pokemon {u16 hp, species;};
static struct Pokemon gPlayerParty[6], gEnemyParty[6];
static struct {u16 id;} gLinkPlayers[4];
static unsigned gBattleTypeFlags;
static u8 gBattlerPartyIndexes[4]={0,0,3,0};
static struct {u8 monToSwitchIntoId[4];} bs, *gBattleStruct=&bs;
static int coop;
static int WorldCoop_IsBattle(void) {return coop;}
static unsigned GetBattlerSide(u8 b) {return b&1;}
static u8 GetBattlerAtPosition(u8 b) {return b;}
static unsigned GetMonData(struct Pokemon *p, unsigned key) {return key==MON_DATA_HP?p->hp:p->species;}
'''
        pokemon = (ROOT/'src/pokemon.c').read_text()
        code += function(pokemon, 'GetLinkTrainerFlankId')
        code += function(pokemon, 'GetBattlerMultiplayerId')
        code += function((ROOT/'src/battle_util.c').read_text(), 'HasNoMonsToSwitch')
        code += r'''
int main(void) {
    coop=1; gBattleTypeFlags=BATTLE_TYPE_DOUBLE|BATTLE_TYPE_MULTI;
    gLinkPlayers[0].id=0; gLinkPlayers[1].id=2;
    gEnemyParty[0]=(struct Pokemon){12,290};
    gPlayerParty[0]=(struct Pokemon){20,255};
    gPlayerParty[3]=(struct Pokemon){20,255};
    /* Only two human link identities exist. Neither wild side owns a bench. */
    assert(HasNoMonsToSwitch(3,6,6));
    assert(HasNoMonsToSwitch(1,6,6));
    assert(!HasNoMonsToSwitch(0,6,6));
    assert(!HasNoMonsToSwitch(2,6,6));
    gPlayerParty[3].hp=0;
    assert(HasNoMonsToSwitch(2,6,6)); /* cannot borrow the other human's party */
    /* The same production predicate used by fainted-actions must retain bit3. */
    unsigned absent=8;
    for (int i=0;i<4;i++)
        if ((absent&(1u<<i)) && !HasNoMonsToSwitch(i,6,6)) absent&=~(1u<<i);
    assert(absent==8);
    /* Ordinary four-human link/multi lookup semantics are unchanged. */
    coop=0;
    for (int i=0;i<4;i++) gLinkPlayers[i].id=i;
    assert(!HasNoMonsToSwitch(3,6,6));
    gBattleTypeFlags=0;
    assert(!HasNoMonsToSwitch(3,6,6));
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='coop-absent-') as directory:
            p=Path(directory); (p/'repro.c').write_text(code)
            compiled=subprocess.run(['cc','-std=gnu99','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie',str(p/'repro.c'),'-o',str(p/'repro')],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            ran=subprocess.run([str(p/'repro')],capture_output=True,text=True)
            self.assertEqual(ran.returncode,0,ran.stderr)

if __name__=='__main__': unittest.main()
