"""Production faint-friendship/controller contract, without launching a game.

The shared engine adjusts friendship on its own party copy. Its normal absolute
SETMONDATA command must carry that value to both human controllers before their
private-party restoration. Friendship arithmetic and modifiers, faint processing,
the controller setter cases and the packet boundary come from production code.
Pokemon accessors and unrelated engine services are fixtures. These tests do not
establish native gameplay or save acceptance.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def definition(source, name):
    match = re.search(r'\bvoid ' + name + r'\([^;]*?\)\n\{', source)
    if not match:
        raise AssertionError(name)
    start = match.start()
    end = source.index('\n}', match.end()) + 2
    return source[start:end]


class CoopFaintFriendship(unittest.TestCase):
    def test_friendship_command_survives_real_native_packet_boundary(self):
        import test_link_battle_payloads as payloads
        payloads.LinkBattlePayloadTests().run_c(r'''
 coopMode=TRUE;
 localPlayer=0;
 gBattleTypeFlags |= BATTLE_TYPE_IS_MASTER | BATTLE_TYPE_LINK;
 gActiveBattler=2;
 u8 friendship=99;
 BtlController_EmitSetMonData(B_COMM_TO_CONTROLLER, REQUEST_FRIENDSHIP_BATTLE, 0, 1, &friendship);
 assert(!aborted && gTasks[sLinkSendTaskId].tCurrentBlock_End==16);
 assert(gLinkBattleSendBuffer[0]==B_COMM_TO_CONTROLLER);
 assert(gLinkBattleSendBuffer[1]==2);
 assert(gLinkBattleSendBuffer[8]==CONTROLLER_SETMONDATA);
 assert(gLinkBattleSendBuffer[9]==REQUEST_FRIENDSHIP_BATTLE);
 assert(gLinkBattleSendBuffer[10]==0 && gLinkBattleSendBuffer[11]==99);
 /* Consume the real master's record on the owner's slave client. */
 source=0; localPlayer=1; gBattleTypeFlags &= ~BATTLE_TYPE_IS_MASTER;
 memcpy(gBlockRecvBuffer[source], gLinkBattleSendBuffer, 16);
 TryReceiveLinkBattleData();
 assert(!aborted && resets==1);
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && dispatched==1);
 assert(gBattleBufferA[2][0]==CONTROLLER_SETMONDATA);
 assert(gBattleBufferA[2][1]==REQUEST_FRIENDSHIP_BATTLE);
 assert(gBattleBufferA[2][2]==0 && gBattleBufferA[2][3]==99);
 assert(!gBattleBufferA[0][0] && !gBattleBufferA[1][0] && !gBattleBufferA[3][0]);
 ''', emitters=('BtlController_EmitSetMonData',))

    def test_absolute_friendship_sync_targets_only_fainted_owned_slot(self):
        source = (ROOT / 'src/battle_util2.c').read_text()
        pokemon = (ROOT / 'src/pokemon.c').read_text()
        start = pokemon.index('static const s8 sFriendshipEventModifiers[][3] =')
        modifiers = pokemon[start:pokemon.index('\n};', start) + 3]
        stock_friendship = definition(pokemon, 'AdjustFriendship').replace('void AdjustFriendship(', 'static void StockAdjustFriendship(')
        setters = []
        for filename in ['battle_controller_player.c', 'battle_controller_link_partner.c']:
            controller = (ROOT / 'src' / filename).read_text()
            match = re.search(r'case REQUEST_FRIENDSHIP_BATTLE:\s*SetMonData\([^;]+;\s*break;', controller)
            if match is None:
                self.fail('missing production friendship setter in ' + filename)
            setters.append(match.group())
        fixture = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "constants/pokemon.h"
#include "constants/items.h"
#include "constants/hold_effects.h"
#include "constants/trainers.h"
typedef uint8_t u8; typedef uint16_t u16; typedef int8_t s8; typedef int16_t s16;
#define PORTABLE 1
#define BATTLE_TYPE_DOUBLE 1
#define BATTLE_TYPE_TRAINER 8
#define B_POSITION_OPPONENT_LEFT 1
#define B_POSITION_OPPONENT_RIGHT 3
#define MON_DATA_FRIENDSHIP 9
#define MON_DATA_SPECIES_OR_EGG 10
#define MON_DATA_HELD_ITEM 11
#define MON_DATA_POKEBALL 12
#define MON_DATA_MET_LOCATION 13
#define SPECIES_EGG 412
#define REQUEST_FRIENDSHIP_BATTLE 18
#define B_COMM_TO_CONTROLLER 0
struct Pokemon {u8 friendship;};
struct Pokemon gPlayerParty[6];
struct {u8 level, friendship;} gBattleMons[4];
u8 gBattlerPartyIndexes[4], gActiveBattler, gBattleBufferA[4][16];
unsigned gBattleTypeFlags, execFlags;
static int coop, sends, adjustments, lastEvent;
static u8 sentBattler, sentValue;
int WorldCoop_IsBattle(void) {return coop;}
u8 GetBattlerAtPosition(u8 position) {return position;}
unsigned GetMonData(struct Pokemon *mon, int field, ...) {
 if(field==MON_DATA_FRIENDSHIP)return mon->friendship;
 if(field==MON_DATA_SPECIES_OR_EGG)return 1;
 return 0;
}
void SetMonData(struct Pokemon *mon, int field, const void *value) {
 assert(field==MON_DATA_FRIENDSHIP); mon->friendship=*(const u8*)value;
}
struct {u8 inBattle;} gMain={1};
struct {u8 holdEffect;} gEnigmaBerries[1];
static struct {struct {u8 holdEffect;} enigmaBerry;} saveBlock;
static __typeof__(saveBlock) *gSaveBlock1Ptr=&saveBlock;
struct {u8 trainerClass;} gTrainers[1];
u16 gTrainerBattleOpponent_A;
static int ShouldSkipFriendshipChange(void) {return 0;}
static u8 GetItemHoldEffect(u16 heldItem) {(void)heldItem;return 0;}
static u16 Random(void) {return 0;}
static u8 GetCurrentRegionMapSectionId(void) {return 0;}
void AdjustFriendship(struct Pokemon *mon, u8 event);
void BtlController_EmitSetMonData(u8 destination, u8 request, u8 mask, u8 size, const void *data) {
 assert(destination==B_COMM_TO_CONTROLLER && request==REQUEST_FRIENDSHIP_BATTLE);
 assert(mask==0 && size==1);
 sends++; sentBattler=gActiveBattler; sentValue=*(const u8*)data;
}
void MarkBattlerForControllerExec(u8 battler) {execFlags|=1u<<battler;}
'''
        fixture += modifiers + '\n' + stock_friendship + '\n'
        fixture += 'void AdjustFriendship(struct Pokemon *mon, u8 event) {adjustments++;lastEvent=event;StockAdjustFriendship(mon,event);}'
        fixture += definition(source, 'AdjustFriendshipOnBattleFaint')
        for number, case in enumerate(setters):
            fixture += '\nstatic void Setter%d(u8 monId) {switch(REQUEST_FRIENDSHIP_BATTLE){%s}}\n' % (number, case)
        fixture += r'''
static void reset(void) {
 memset(gBattleMons,0,sizeof(gBattleMons));
 for(int i=0;i<6;i++)gPlayerParty[i].friendship=100+i;
 gBattleTypeFlags=BATTLE_TYPE_DOUBLE; coop=1; sends=adjustments=execFlags=0;
 gBattleMons[0].level=gBattleMons[2].level=5;
 gBattleMons[1].level=8;gBattleMons[3].level=0;
 gActiveBattler=3;
}
int main(void) {
 for(int battler=0;battler<=2;battler+=2) {
  for(int relative=0;relative<3;relative++) {
   reset(); int slot=(battler/2)*3+relative;
   gBattlerPartyIndexes[battler]=slot;
   AdjustFriendshipOnBattleFaint(battler);
   assert(adjustments==1 && lastEvent==FRIENDSHIP_EVENT_FAINT_SMALL);
   assert(sends==1 && sentBattler==battler && sentValue==99+slot);
   assert(execFlags==(1u<<battler) && gActiveBattler==3);
   assert(gBattleMons[battler].friendship==sentValue);
   for(int i=0;i<6;i++) assert(gPlayerParty[i].friendship==(i==slot?99+i:100+i));
   /* Run each real controller friendship setter on a fresh recipient copy.
    * Absolute duplicate delivery cannot apply the faint penalty twice. */
   for(int receiver=0;receiver<2;receiver++) {
    for(int i=0;i<6;i++)gPlayerParty[i].friendship=100+i;
    gActiveBattler=battler;gBattleBufferA[battler][3]=sentValue;
    if(receiver==0){Setter0(slot);Setter0(slot);}else{Setter1(slot);Setter1(slot);}
    for(int i=0;i<6;i++)assert(gPlayerParty[i].friendship==(i==slot?sentValue:100+i));
   }
  }
 }
 reset();gBattlerPartyIndexes[2]=4;gBattleMons[1].level=40;
 AdjustFriendshipOnBattleFaint(2);
 assert(lastEvent==FRIENDSHIP_EVENT_FAINT_LARGE && sentValue==99);
 for(int levelGap=0;levelGap<=35;levelGap+=35) {
  const u8 values[]={0,1,99,100,199,200,255};
  for(unsigned n=0;n<sizeof(values);n++) {
   reset();gBattlerPartyIndexes[2]=4;gPlayerParty[4].friendship=values[n];
   gBattleMons[1].level=5+levelGap;
   AdjustFriendshipOnBattleFaint(2);
   unsigned loss=levelGap>29?(values[n]>=200?10:5):1;
   unsigned expected=values[n]>loss?values[n]-loss:0;
   assert(sentValue==expected && gPlayerParty[4].friendship==expected);
  }
 }
 reset();gBattlerPartyIndexes[0]=0;gPlayerParty[0].friendship=0;
 AdjustFriendshipOnBattleFaint(0);assert(sentValue==0 && sends==1);
 /* Stock solo/PvP/GBA semantics stay local and do not emit extra commands. */
 reset();coop=0;gBattlerPartyIndexes[0]=1;
 AdjustFriendshipOnBattleFaint(0);assert(adjustments==1 && sends==0 && execFlags==0);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='coop-faint-friendship-') as directory:
            path = Path(directory)
            (path / 'fixture.c').write_text(fixture)
            compiled = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-iquote', str(ROOT / 'include'),
                                       '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                                       '-fno-pie', '-no-pie', str(path / 'fixture.c'), '-o', str(path / 'fixture')],
                                      capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run([str(path / 'fixture')], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stderr)


if __name__ == '__main__':
    unittest.main()
