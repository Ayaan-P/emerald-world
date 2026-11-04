"""Production forced-switch selection with owned and reserved bench slots.

Component fixtures only. This module never launches the native game.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def function(source, name, return_type='void'):
    start = source.index('static ' + return_type + ' ' + name + '(void)\n{')
    end = source.index('\n}', start) + 2
    return source[start:end]


class ForcedReserveTests(unittest.TestCase):
    @staticmethod
    def party_order_function():
        source = (ROOT/'src/party_menu.c').read_text()
        start = source.index('void SwitchPartyOrderLinkMulti(u8 battler, u8 slot, u8 slot2)\n{')
        end = source.index('\n}', start) + 2
        return source[start:end].replace('SwitchPartyOrderLinkMulti', 'ProductionSwitchPartyOrderLinkMulti')

    def test_owned_benches_and_pending_npc_replacement(self):
        source = (ROOT / 'src/battle_script_commands.c').read_text()
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int bool8;
#define TRUE 1
#define FALSE 0
#define PARTY_SIZE 6
#define MULTI_PARTY_SIZE 3
#define B_SIDE_PLAYER 0
#define BIT_FLANK 2
#define BATTLE_PARTNER(b) ((b)^2)
#define MON_DATA_SPECIES 0
#define MON_DATA_IS_EGG 1
#define MON_DATA_HP 2
#define SPECIES_NONE 0
#define DSIZE8BIT 1
#define T1_READ_PTR(p) failure
struct Pokemon {unsigned species,egg,hp;};
struct Pokemon gPlayerParty[6],gEnemyParty[6];
static u8 gBattlerAttacker,gBattlerTarget,gBattlerPartyIndexes[4],gAbsentBattlerFlags;
static struct {u8 level;} gBattleMons[4];
static unsigned gBitTable[4]={1,2,4,8};
static struct {u8 monToSwitchIntoId[4],battlerPartyIndexes[4],battlerPartyOrders[4][3];} battleStruct;
#define gBattleStruct (&battleStruct)
static struct {unsigned faintedHasReplacement;} gSpecialStatuses[4];
static const u8 script[16],failure[1],success[1];
static const u8 *gBattlescriptCurrInstr;
#define BattleScript_SuccessForceOut success
static unsigned rolls,orders,secondOpponent,randomValue;
static unsigned GetBattlerSide(unsigned b){return b&1;}
static unsigned GetBattlerPosition(unsigned b){return b;}
static unsigned WorldCoop_HasSecondOpponent(void){return secondOpponent;}
static unsigned GetMonData(struct Pokemon *m,unsigned field){
    return field==MON_DATA_SPECIES?m->species:field==MON_DATA_IS_EGG?m->egg:m->hp;
}
static unsigned Random(void){rolls++;return randomValue;}
static bool8 IsMultiBattle(void){return TRUE;}
''' + self.party_order_function() + r'''
static void SwitchPartyOrderLinkMulti(unsigned b,unsigned slot,unsigned partner){
    assert(!(b&1));assert(slot<6);assert(partner<2);orders++;
    ProductionSwitchPartyOrderLinkMulti(b,slot,partner);
}
''' + function(source, 'TryDoForceSwitchOut', 'bool8') + function(source, 'CoopForceRandomSwitch') + r'''
static void reset(void){
    memset(gPlayerParty,0,sizeof(gPlayerParty));memset(gEnemyParty,0,sizeof(gEnemyParty));
    memset(gSpecialStatuses,0,sizeof(gSpecialStatuses));
    memset(&battleStruct,6,sizeof(battleStruct));
    gBattlerPartyIndexes[0]=0;gBattlerPartyIndexes[1]=0;
    gBattlerPartyIndexes[2]=3;gBattlerPartyIndexes[3]=1;
    rolls=orders=randomValue=0;secondOpponent=1;
    gBattlerAttacker=0;
    for(unsigned i=0;i<4;i++){
        gBattleMons[i].level=10;
        battleStruct.battlerPartyOrders[i][0]=(i&2)?0x30:0x03;
        battleStruct.battlerPartyOrders[i][1]=(i&2)?0x45:0x12;
        battleStruct.battlerPartyOrders[i][2]=(i&2)?0x12:0x45;
    }
    gAbsentBattlerFlags=0;gBattlescriptCurrInstr=script;
}
int main(void){
    unsigned target,i;
    /* A human can never borrow the other human's reserves. */
    for(target=0;target<=2;target+=2){
        reset();gBattlerTarget=target;
        for(i=0;i<6;i++)gPlayerParty[i]=(struct Pokemon){1,0,10};
        CoopForceRandomSwitch();
        assert(battleStruct.monToSwitchIntoId[target]==(target?4:1));
        assert(orders==2 && rolls==1);
        reset();gBattlerTarget=target;
        for(i=0;i<6;i++)if(i/3!=(target?1:0))gPlayerParty[i]=(struct Pokemon){1,0,10};
        CoopForceRandomSwitch();assert(gBattlescriptCurrInstr==failure && !orders && !rolls);
    }
    /* A double NPC's other fainted battler already owns reserve slot 2.
     * Forced switching must not send the same Pokemon into both positions. */
    reset();gBattlerTarget=1;gEnemyParty[2]=(struct Pokemon){1,0,10};
    gEnemyParty[3]=(struct Pokemon){2,0,10};
    gAbsentBattlerFlags=8;gSpecialStatuses[3].faintedHasReplacement=1;
    battleStruct.monToSwitchIntoId[3]=2;
    CoopForceRandomSwitch();assert(battleStruct.monToSwitchIntoId[1]==3 && !orders);
    /* An exhausted bench must fail before RNG or order mutation. */
    reset();gBattlerTarget=1;gEnemyParty[2]=(struct Pokemon){1,0,10};
    gAbsentBattlerFlags=8;gSpecialStatuses[3].faintedHasReplacement=1;
    battleStruct.monToSwitchIntoId[3]=2;
    CoopForceRandomSwitch();assert(gBattlescriptCurrInstr==failure && !rolls && !orders);
    /* Eggs, fainted and empty slots are not forced-switch candidates. */
    reset();gBattlerTarget=0;gPlayerParty[1]=(struct Pokemon){1,1,10};
    gPlayerParty[2]=(struct Pokemon){1,0,0};
    CoopForceRandomSwitch();assert(gBattlescriptCurrInstr==failure && !rolls && !orders);
    /* Failed stock force-out roll cannot reorder the private bench. */
    reset();gBattlerTarget=2;gPlayerParty[4]=(struct Pokemon){1,0,10};
    gBattleMons[0].level=1;gBattleMons[2].level=100;
    CoopForceRandomSwitch();assert(gBattlescriptCurrInstr==failure && rolls==1 && !orders);
    assert(battleStruct.monToSwitchIntoId[2]==6);
    /* A successful lower-level stock roll proceeds to the owned reserve. */
    randomValue=255;rolls=0;
    CoopForceRandomSwitch();assert(gBattlescriptCurrInstr==success && rolls==2 && orders==2);
    assert(battleStruct.monToSwitchIntoId[2]==4);
    assert(battleStruct.battlerPartyIndexes[2]==3);
    /* Enumerate every bench availability mask for both human owners and
     * both NPC positions, with each partner presence/reservation state.
     * The independent oracle uses a set, not the production scan bounds. */
    for(unsigned mask=0;mask<64;mask++)
    for(target=0;target<4;target++)
    for(unsigned absent=0;absent<2;absent++)
    for(unsigned reserved=0;reserved<2;reserved++)
    for(unsigned roll=0;roll<6;roll++){
        unsigned expected[6],count=0,partner=target^2;
        struct Pokemon before[6];
        reset();gBattlerTarget=target;randomValue=roll;
        gAbsentBattlerFlags=absent?(1u<<partner):0;
        gSpecialStatuses[partner].faintedHasReplacement=reserved;
        battleStruct.monToSwitchIntoId[partner]=(target&1)?2:5;
        struct Pokemon *party=(target&1)?gEnemyParty:gPlayerParty;
        for(i=0;i<6;i++){
            party[i]=(struct Pokemon){1,0,(mask&(1u<<i))?10:0};
            if(!(mask&(1u<<i)))continue;
            if(!(target&1) && i/3!=target/2)continue;
            if(i==gBattlerPartyIndexes[target])continue;
            if(!absent && i==gBattlerPartyIndexes[partner])continue;
            if(reserved && i==battleStruct.monToSwitchIntoId[partner])continue;
            expected[count++]=i;
        }
        memcpy(before,party,sizeof(before));
        CoopForceRandomSwitch();
        assert(!memcmp(before,party,sizeof(before)));
        if(!count){assert(gBattlescriptCurrInstr==failure && !rolls && !orders);}
        else{
            assert(gBattlescriptCurrInstr==success && rolls==1);
            assert(battleStruct.monToSwitchIntoId[target]==expected[roll%count]);
            assert(orders==((target&1)?0:2));
            if(!(target&1)){
                assert(battleStruct.battlerPartyOrders[target][0]>>4==expected[roll%count]);
                assert((battleStruct.battlerPartyOrders[partner][0]&15)==expected[roll%count]);
                for(unsigned b=0;b<4;b+=2){
                    unsigned seen=0;
                    for(unsigned j=0;j<3;j++){
                        seen|=1u<<(battleStruct.battlerPartyOrders[b][j]>>4);
                        seen|=1u<<(battleStruct.battlerPartyOrders[b][j]&15);
                    }
                    assert(seen==63);
                }
            }
        }
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='coop-force-reserves-') as temp:
            root = Path(temp)
            (root / 'force.c').write_text(code)
            result = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra',
                '-Werror', '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                str(root/'force.c'), '-o', str(root/'force')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(root/'force')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
