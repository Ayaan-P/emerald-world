"""Sanitized regressions for the actual native battle block consumers.

Only unrelated engine services are stubbed. Function bodies, header offsets,
controller IDs and flag macros come from production sources on every run.
"""
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def function(source, name):
    match = re.search(r'^(?:static )?(?:void|bool8|u16) (?:UNUSED )?' + name + r'\([^;]*?\)\n\{', source, re.M)
    if not match:
        raise AssertionError(name)
    end = source.index('\n}', match.end()) + 2
    return source[match.start():end]


PREAMBLE = r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "constants/pokemon.h"
#include "constants/species.h"
#include "constants/global.h"
#include "constants/moves.h"
#include "constants/items.h"
#include "constants/battle.h"
typedef int8_t s8;
#define TEXT_BUFF_ARRAY_COUNT 16
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int16_t s16; typedef int32_t s32; typedef u8 bool8;
#define TRUE 1
#define UNUSED
#define FALSE 0
#define MAX_BATTLERS_COUNT 4
#define MAX_LINK_PLAYERS 4
#define PARTY_SIZE 6
#define MAX_MON_MOVES 4
#define BLOCK_BUFFER_SIZE 256
#define BATTLE_BUFFER_LINK_SIZE 4096
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
struct Task { s16 data[16]; };
static struct Task gTasks[16];
static u8 sLinkReceiveTaskId, sLinkSendTaskId = 1;
static u8 gLinkBattleSendBuffer[BATTLE_BUFFER_LINK_SIZE];
static u8 sBattleBuffersTransferData[256], gActiveBattler;
static u8 gBattlePartyCurrentOrder[3]={0x10,0x32,0x54};
static u16 gBlockRecvBuffer[5][128];
static u8 gBattleBufferA[4][512], gBattleBufferB[4][512];
/* Party mons have the fixed 100-byte save layout. */
static u8 gPlayerParty[6][100];
static u8 *gLinkBattleRecvBuffer;
static u32 gBattleTypeFlags = BATTLE_TYPE_LINK_IN_BATTLE;
static u32 gBattleControllerExecFlags;
static u8 gReceivedRemoteLinkPlayers = 1, gLinkErrorOccurred;
static u8 gBattlerAttacker, gBattlerTarget, gAbsentBattlerFlags, gEffectBattler;
static u8 gBattlerPartyIndexes[4] = {0,0,3,0};
static unsigned observedMon, observedController;
static u8 observedBattler, observedSlot;
static const u32 gBitTable[4] = {1,2,4,8};
static int active = 1, aborted, dispatched, resets;
static u8 source=1, localPlayer;
static bool8 coopMode;
static u16 receivedSize = 16;
static int NativeLink_IsActive(void) { return active; }
static void NativeLink_Abort(void) { active=0; aborted++; }
static u16 GetBlockReceivedSize(u8 i) { (void)i; return receivedSize; }
/* This extracted fixture explicitly disables the co-op state machine. */
static int WorldCoop_IsBattle(void) { return coopMode; }
static int WorldCoop_ReceiveCompletion(const u8 *p, u16 n, u8 s) { return 0; }
static bool8 WorldCoop_RewardPacketValid(const u8 *p, u16 n) { return FALSE; }
/* Catch semantics are exercised by coop_catching_core.c. These transport
 * fixtures only need the new dispatch hooks to fail closed. */
static bool8 WorldCoop_CatchPacketValid(const u8 *p, u16 n) { return FALSE; }
static bool8 WorldCoop_BallReplyValid(u16 reply) {
    return reply == 0 || (reply >= ITEM_MASTER_BALL && reply <= LAST_BALL && reply != ITEM_SAFARI_BALL);
}
static u8 GetMultiplayerId(void) { return localPlayer; }
static u8 GetLinkPlayerCount(void) { return 2; }
static u8 GetBlockReceivedStatus(void) { return 1 << source; }
static void ResetBlockReceivedFlag(u8 i) { (void)i; resets++; }
static void DestroyTask_RfuIdle(void) {}
static void MarkBattlerReceivedLinkData(u8 i) { (void)i; dispatched++; }
'''


class LinkBattlePayloadTests(unittest.TestCase):
    def run_c(self, body, emitters=()):
        source = (ROOT / 'src/battle_controllers.c').read_text()
        header = (ROOT / 'include/battle_controllers.h').read_text()
        start = source.index('enum\n{\n    LINK_BUFF_BUFFER_ID')
        offsets = source[start:source.index('};', start) + 2]
        macros = source[source.index('#define tInitialDelayTimer'):source.index('//\n// Inbound communications')]
        enums = header[header.index('enum {'):header.index('// Accessors')]
        enums += header[header.index('enum {\n   // For commands'):header.index('enum {\n    RESET_ACTION')]
        enums += header[header.index('enum\n{\n    CONTROLLER_GETMONDATA'):header.index('extern struct UnusedControllerStruct')]
        flags = header[header.index('#define IS_BATTLE_CONTROLLER_ACTIVE_ON_LOCAL'):header.index('// This actually checks')]
        helpers = ''
        if '/* Native battle payload boundary. */' in source:
            helpers = source.split('/* Native battle payload boundary. */', 1)[1].split('/* End native battle payload boundary. */', 1)[0]
        structs = ''
        for filename, names in [('include/battle.h', ['DisableStruct']), ('include/pokemon.h', ['BattlePokemon']), ('include/battle_message.h', ['BattleMsgData']), ('include/battle_controllers.h', ['HpAndStatus', 'ChooseMoveStruct'])]:
            text = (ROOT / filename).read_text()
            for name in names:
                start = text.index('struct ' + name + '\n{')
                structs += text[start:text.index('\n};', start) + 3] + '\n'
        battle = (ROOT / 'include/battle.h').read_text()
        actions = '\n'.join(line for line in battle.splitlines() if line.startswith('#define B_ACTION_')) + '\n'
        state_start = source.index('static bool8 sNativeBattlePayloadFailed;')
        state = source[state_start:source.index('#endif', state_start)]
        code = PREAMBLE + state + actions + structs + enums + flags + macros + offsets + helpers
        code += '''
static void WorldCoop_ObserveMonData(u8 battler, u8 slot, const struct BattlePokemon *mon) {
    (void)mon; observedMon++; observedBattler=battler; observedSlot=slot;
}
static void WorldCoop_ObserveController(u8 battler, const u8 *data) {
    (void)battler; (void)data; observedController++;
}
'''
        code += function(source, 'PrepareBufferDataTransferLink') + '\n'
        if emitters:
            code += function(source, 'PrepareBufferDataTransfer') + '\n'
            code += '\n'.join(function(source, name) for name in emitters) + '\n'
        code += function(source, 'TryReceiveLinkBattleData')
        code += '\n' + function(source, 'Task_HandleCopyReceivedLinkBuffersData')
        code += '\nint main(void) {\n gLinkBattleRecvBuffer=calloc(1,4096);\n' + body + '\n free(gLinkBattleRecvBuffer); return 0; }\n'
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory)
            (path / 'test.c').write_text(code)
            result = subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu99', '-iquote' + str(ROOT / 'include'), '-DPORTABLE', '-DUBFIX', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie', str(path / 'test.c'), '-o', str(path / 'test')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(path / 'test')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_move_reply_cannot_bypass_bounds_with_another_action(self):
        self.run_c(r'''
 for (int coop=0;coop<2;coop++) {
  for (int action=0;action<=B_ACTION_UNK_14;action++) {
   if (action==B_ACTION_USE_MOVE || action==B_ACTION_EXEC_SCRIPT) continue;
   for (int slot=4;slot<256;slot++) {
    memset(gTasks,0,sizeof(gTasks));
    memset(gBattleBufferB,0xA5,sizeof(gBattleBufferB));
    active=1; aborted=resets=0; sNativeBattlePayloadFailed=FALSE;
    coopMode=coop; source=1; localPlayer=0;
    gBattleTypeFlags=BATTLE_TYPE_LINK_IN_BATTLE|BATTLE_TYPE_IS_MASTER;
    u8 battler=coop?2:1;
    sNativeBattleRequestPending[battler]=TRUE;
    sNativeBattleReplyUsed[battler]=FALSE;
    sNativeBattleRequest[battler][0]=CONTROLLER_CHOOSEMOVE;
    u8 *p=(u8 *)gBlockRecvBuffer[source]; memset(p,0,16);
    p[0]=B_COMM_TO_ENGINE; p[1]=battler; p[4]=8;
    p[8]=CONTROLLER_TWORETURNVALUES; p[9]=action; p[10]=slot; p[11]=0;
    TryReceiveLinkBattleData();
    if (!aborted) Task_HandleCopyReceivedLinkBuffersData(0);
    assert(aborted==1 && !sNativeBattleReplyUsed[battler]);
    for(int i=0;i<512;i++) assert(gBattleBufferB[battler][i]==0xA5);
   }
  }
 }
 ''')

    def test_legitimate_move_selection_and_cancel_replies(self):
        self.run_c(r'''
 for (int coop=0;coop<2;coop++) {
  for (int move=0;move<5;move++) {
   for (int target=0;target<4;target++) {
    memset(gTasks,0,sizeof(gTasks));
    active=1; aborted=resets=0; sNativeBattlePayloadFailed=FALSE;
    coopMode=coop; source=1; localPlayer=0;
    gBattleTypeFlags=BATTLE_TYPE_LINK_IN_BATTLE|BATTLE_TYPE_IS_MASTER;
    u8 battler=coop?2:1;
    sNativeBattleRequestPending[battler]=TRUE;
    sNativeBattleReplyUsed[battler]=FALSE;
    sNativeBattleRequest[battler][0]=CONTROLLER_CHOOSEMOVE;
    u8 *p=(u8 *)gBlockRecvBuffer[source]; memset(p,0,16);
    p[0]=B_COMM_TO_ENGINE; p[1]=battler; p[4]=8;
    p[8]=CONTROLLER_TWORETURNVALUES; p[9]=B_ACTION_EXEC_SCRIPT;
    p[10]=move==4?255:move; p[11]=move==4?255:target;
    TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
    assert(!aborted && resets==1 && sNativeBattleReplyUsed[battler]);
    assert(!memcmp(gBattleBufferB[battler],p+8,8));
   }
  }
 }
 ''')

    def test_move_reply_byte_matrix_is_request_bound(self):
        self.run_c(r'''
 u8 data[4]={CONTROLLER_TWORETURNVALUES,0,0,0};
 sNativeBattleRequestPending[0]=TRUE;
 sNativeBattleRequest[0][0]=CONTROLLER_CHOOSEMOVE;
 for(unsigned action=0;action<256;action++) {
  data[1]=action;
  for(unsigned move=0;move<256;move++) {
   data[2]=move;
   for(unsigned target=0;target<256;target++) {
    data[3]=target;
    bool8 expected=action==B_ACTION_EXEC_SCRIPT
       && ((move==255 && target==255) || (move<4 && target<4));
    assert(NativeBattleReplyValid(0,data)==expected);
   }
  }
 }
 // Valid contents do not waive pending-request or one-use requirements.
 data[1]=B_ACTION_EXEC_SCRIPT; data[2]=data[3]=0;
 sNativeBattleRequestPending[0]=FALSE;
 assert(!NativeBattleReplyValid(0,data));
 sNativeBattleRequestPending[0]=TRUE; sNativeBattleReplyUsed[0]=TRUE;
 assert(!NativeBattleReplyValid(0,data));
 ''')

    def test_real_move_reply_emitter_all_owner_mappings(self):
        self.run_c(r'''
 for(int coop=0;coop<2;coop++)
 for(int local=0;local<2;local++)
 for(int master=0;master<2;master++)
 for(int battler=0;battler<4;battler++) {
  if(coop && (battler&1)) continue;
  for(int choice=0;choice<17;choice++) {
   memset(gTasks,0,sizeof(gTasks));
   active=1; aborted=resets=0; sNativeBattlePayloadFailed=FALSE;
   gLinkErrorOccurred=0; coopMode=coop; localPlayer=local;
   gBattleTypeFlags=BATTLE_TYPE_LINK|BATTLE_TYPE_LINK_IN_BATTLE|BATTLE_TYPE_DOUBLE;
   if(master) gBattleTypeFlags|=BATTLE_TYPE_IS_MASTER;
   source=NativeBattleOwner(battler); gActiveBattler=battler;
   sNativeBattleRequestPending[battler]=TRUE;
   sNativeBattleReplyUsed[battler]=FALSE;
   sNativeBattleRequest[battler][0]=CONTROLLER_CHOOSEMOVE;
   u16 selection=choice==16?0xFFFF:((choice/4)<<8)|(choice%4);
   BtlController_EmitTwoReturnValues(B_COMM_TO_ENGINE,B_ACTION_EXEC_SCRIPT,selection);
   receivedSize=gTasks[sLinkSendTaskId].tCurrentBlock_End;
   if(source!=localPlayer) {
    // The real emitter suppresses replies from non-owning mirror controllers.
    assert(receivedSize==0);
    continue;
   }
   assert(receivedSize==16);
   memcpy(gBlockRecvBuffer[source],gLinkBattleSendBuffer,receivedSize);
   TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
   assert(!aborted && !gLinkErrorOccurred && resets==1);
   assert(sNativeBattleReplyUsed[battler]);
   assert(!memcmp(gBattleBufferB[battler],gLinkBattleSendBuffer+8,8));
   // A repeated response in the same request cannot become a second action.
   TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
   assert(aborted==1 && gLinkErrorOccurred);
  }
 }
 ''', emitters=('BtlController_EmitTwoReturnValues',))

    def test_non_move_two_value_requests_keep_existing_semantics(self):
        self.run_c(r'''
 const u8 requests[]={CONTROLLER_CHOOSEACTION,CONTROLLER_EXPUPDATE,
                      CONTROLLER_DRAWPARTYSTATUSSUMMARY};
 u8 data[4]={CONTROLLER_TWORETURNVALUES,B_ACTION_USE_MOVE,0,0};
 sNativeBattleRequestPending[0]=TRUE;
 for(unsigned i=0;i<sizeof(requests);i++) {
  sNativeBattleRequest[0][0]=requests[i];
  assert(NativeBattleReplyValid(0,data));
 }
 sNativeBattleRequest[0][0]=CONTROLLER_OPENBAG;
 assert(!NativeBattleReplyValid(0,data));
 ''')

    def test_remote_cannot_issue_engine_commands(self):
        self.run_c(r'''
 u8 *p=(u8 *)gBlockRecvBuffer[source];
 p[0]=B_COMM_TO_CONTROLLER; p[4]=8; p[8]=CONTROLLER_LOADMONSPRITE;
 gBattleTypeFlags |= BATTLE_TYPE_IS_MASTER;
 TryReceiveLinkBattleData();
 assert(aborted==1 && !resets && !dispatched && !gTasks[0].tCurrentBlock_End);
 ''')

    def test_done_identity_is_bound_to_network_sender(self):
        self.run_c(r'''
 u8 *p=(u8 *)gBlockRecvBuffer[source];
 p[0]=B_COMM_CONTROLLER_IS_DONE; p[4]=8; p[8]=0;
 TryReceiveLinkBattleData();
 assert(aborted==1 && !resets && !gTasks[0].tCurrentBlock_End);
 ''')

    def test_reply_cannot_impersonate_other_battler_owner(self):
        self.run_c(r'''
 u8 *p=(u8 *)gBlockRecvBuffer[source];
 p[0]=B_COMM_TO_ENGINE; p[1]=0; p[4]=8; p[8]=CONTROLLER_TWORETURNVALUES;
 gBattleTypeFlags |= BATTLE_TYPE_IS_MASTER;
 TryReceiveLinkBattleData();
 assert(aborted==1 && !resets && !gTasks[0].tCurrentBlock_End);
 ''')

    def test_solicited_battle_mon_is_validated_before_engine_copy(self):
        for mutation in ['mon.species=65535', 'mon.moves[0]=MOVES_COUNT',
                         'mon.level=101', 'mon.hp=31', 'mon.item=65535']:
            with self.subTest(mutation=mutation):
                self.run_c(r'''
 struct BattlePokemon mon={0};
 mon.species=1; mon.level=10; mon.hp=mon.maxHP=30;
 mon.attack=mon.defense=mon.speed=mon.spAttack=mon.spDefense=20;
 ''' + mutation + r''';
 u8 *p=gLinkBattleRecvBuffer; p[0]=B_COMM_TO_ENGINE; p[1]=1;
 unsigned n=4+sizeof(mon); n=n-n%4+4; p[4]=n;
 p[8]=CONTROLLER_DATATRANSFER; p[10]=sizeof(mon);
 memcpy(p+12,&mon,sizeof(mon));
 gBattleBufferA[1][0]=CONTROLLER_GETMONDATA;
 gBattleBufferA[1][1]=REQUEST_ALL_BATTLE;
 memcpy(sNativeBattleRequest[1],gBattleBufferA[1],sizeof(sNativeBattleRequest[1]));
 sNativeBattleRequestPending[1]=TRUE;
 gTasks[0].tCurrentBlock_End=n+8;
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(aborted==1 && !gBattleBufferB[1][0] && !gTasks[0].tCurrentBlock_Start);
 ''')

    def test_real_solicited_owner_reply_and_duplicate_after_fifo_dispatch(self):
        for bad_species in [False, True]:
            with self.subTest(bad_species=bad_species):
                self.run_c(r'''
 struct BattlePokemon mon={0};
 mon.species=1; mon.level=10; mon.hp=mon.maxHP=30;
 mon.attack=mon.defense=mon.speed=mon.spAttack=mon.spDefense=20;
 source=0; gActiveBattler=1; gBattleTypeFlags |= BATTLE_TYPE_LINK | BATTLE_TYPE_IS_MASTER;
 BtlController_EmitGetMonData(B_COMM_TO_CONTROLLER, REQUEST_ALL_BATTLE, 0);
 receivedSize=gTasks[sLinkSendTaskId].tCurrentBlock_End;
 memcpy(gBlockRecvBuffer[source],gLinkBattleSendBuffer,receivedSize);
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && sNativeBattleRequestPending[1]);
 memset(gTasks[sLinkSendTaskId].data,0,sizeof(gTasks[sLinkSendTaskId].data));
 source=localPlayer=1; gBattleTypeFlags &= ~BATTLE_TYPE_IS_MASTER;
 ''' + ('mon.species=65535;' if bad_species else '') + r'''
 BtlController_EmitDataTransfer(B_COMM_TO_ENGINE,sizeof(mon),&mon);
 receivedSize=gTasks[sLinkSendTaskId].tCurrentBlock_End;
 memcpy(gBlockRecvBuffer[source],gLinkBattleSendBuffer,receivedSize);
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 ''' + (r'''
 assert(aborted==1 && !gBattleBufferB[1][0]);
 ''' if bad_species else r'''
 assert(!aborted && !memcmp(gBattleBufferB[1]+4,&mon,sizeof(mon)));
 /* The same source cannot answer the same request twice. */
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 assert(aborted==1);
 '''), emitters=('BtlController_EmitGetMonData','BtlController_EmitDataTransfer'))

    def test_coop_and_pvp_double_reply_owner_mapping(self):
        for coop, battler in [(True, 2), (False, 3)]:
            with self.subTest(coop=coop):
                self.run_c(f'''
 coopMode={int(coop)}; gBattleTypeFlags |= BATTLE_TYPE_IS_MASTER | BATTLE_TYPE_DOUBLE;
 u8 *p=(u8 *)gBlockRecvBuffer[source]; p[0]=B_COMM_TO_ENGINE; p[1]={battler}; p[4]=8;
 p[8]=CONTROLLER_TWORETURNVALUES;
 gBattleBufferA[{battler}][0]=CONTROLLER_CHOOSEACTION;
 memcpy(sNativeBattleRequest[{battler}],gBattleBufferA[{battler}],sizeof(sNativeBattleRequest[{battler}]));
 sNativeBattleRequestPending[{battler}]=TRUE;
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && gBattleBufferB[{battler}][0]==CONTROLLER_TWORETURNVALUES);
 ''')

    def test_unsolicited_well_formed_mon_reply_is_rejected(self):
        self.run_c(r'''
 struct BattlePokemon mon={0};
 mon.species=1; mon.level=10; mon.hp=mon.maxHP=30;
 mon.attack=mon.defense=mon.speed=mon.spAttack=mon.spDefense=20;
 u8 *p=gLinkBattleRecvBuffer; p[0]=B_COMM_TO_ENGINE; p[1]=1;
 unsigned n=4+sizeof(mon); n=n-n%4+4; p[4]=n;
 p[8]=CONTROLLER_DATATRANSFER; p[10]=sizeof(mon); memcpy(p+12,&mon,sizeof(mon));
 gTasks[0].tCurrentBlock_End=n+8;
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(aborted==1 && !gBattleBufferB[1][0] && !gTasks[0].tCurrentBlock_Start);
 ''')

    def test_coop_switch_reply_cannot_select_partners_mon(self):
        for party_slot in [0, 3]:
            with self.subTest(party_slot=party_slot):
                self.run_c(f'''
 coopMode=TRUE; gBattleTypeFlags |= BATTLE_TYPE_IS_MASTER;
 u8 *p=(u8 *)gBlockRecvBuffer[source]; p[0]=B_COMM_TO_ENGINE; p[1]=2; p[4]=8;
 p[8]=CONTROLLER_CHOSENMONRETURNVALUE; p[9]={party_slot};
 p[10]=0x10; p[11]=0x32; p[12]=0x54;
 gBattleBufferA[2][0]=CONTROLLER_CHOOSEPOKEMON;
 memcpy(sNativeBattleRequest[2],gBattleBufferA[2],sizeof(sNativeBattleRequest[2]));
 sNativeBattleRequestPending[2]=TRUE;
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 assert(aborted=={int(party_slot == 0)});
 ''')

    def test_real_chosen_mon_cancel_emitter_keeps_valid_order(self):
        self.run_c(r'''
 source=0; gBattleTypeFlags |= BATTLE_TYPE_LINK | BATTLE_TYPE_IS_MASTER;
 gBattleBufferA[0][0]=CONTROLLER_CHOOSEPOKEMON;
 memcpy(sNativeBattleRequest[0],gBattleBufferA[0],sizeof(sNativeBattleRequest[0]));
 sNativeBattleRequestPending[0]=TRUE;
 BtlController_EmitChosenMonReturnValue(B_COMM_TO_ENGINE, PARTY_SIZE, NULL);
 receivedSize=gTasks[sLinkSendTaskId].tCurrentBlock_End;
 assert(!memcmp(gLinkBattleSendBuffer+LINK_BUFF_DATA+2,gBattlePartyCurrentOrder,3));
 memcpy(gBlockRecvBuffer[source],gLinkBattleSendBuffer,receivedSize);
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && gBattleBufferB[0][1]==PARTY_SIZE);
 ''', emitters=('BtlController_EmitChosenMonReturnValue',))

    def test_party_order_nibbles_are_bounded_and_unique(self):
        for order in ['0xF0,0x32,0x54', '0x10,0x32,0x44']:
            with self.subTest(order=order):
                self.run_c(r'''
 u8 *p=gLinkBattleRecvBuffer; p[0]=B_COMM_TO_ENGINE; p[1]=1; p[4]=8;
 p[8]=CONTROLLER_CHOSENMONRETURNVALUE; p[9]=1;
 u8 order[3]={''' + order + r'''}; memcpy(p+10,order,3);
 gBattleBufferA[1][0]=CONTROLLER_CHOOSEPOKEMON;
 memcpy(sNativeBattleRequest[1],gBattleBufferA[1],sizeof(sNativeBattleRequest[1]));
 sNativeBattleRequestPending[1]=TRUE;
 gTasks[0].tCurrentBlock_End=16;
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(aborted==1 && !gBattleBufferB[1][0] && !gTasks[0].tCurrentBlock_Start);
 ''')

    def test_real_sender_done_round_trip_clears_only_acknowledged_flag(self):
        # Take the size from real completion callers, not an invented packet.
        for filename, name in [('battle_controller_player.c', 'PlayerBufferExecCompleted'),
                               ('battle_controller_link_opponent.c', 'LinkOpponentBufferExecCompleted')]:
            caller = function((ROOT / 'src' / filename).read_text(), name)
            match = re.search(r'PrepareBufferDataTransferLink\(B_COMM_CONTROLLER_IS_DONE, (\d+), &playerId\)', caller)
            assert match is not None, 'completion caller must use the production DONE sender'
            with self.subTest(caller=name):
                self.run_c(r'''
 u8 data[4]={1, 0xA5, 0xA5, 0xA5};
 gActiveBattler=1;
 memset(gLinkBattleSendBuffer,0xA5,sizeof(gLinkBattleSendBuffer));
 ''' + f'PrepareBufferDataTransferLink(B_COMM_CONTROLLER_IS_DONE, {match.group(1)}, data);' + r'''
 receivedSize=gTasks[sLinkSendTaskId].tCurrentBlock_End;
 assert(receivedSize==16 && gLinkBattleSendBuffer[LINK_BUFF_SIZE_LO]==8);
 memcpy(gBlockRecvBuffer[source],gLinkBattleSendBuffer,receivedSize);
 gBattleControllerExecFlags=0xFF;
 TryReceiveLinkBattleData();
 assert(!aborted && !gLinkErrorOccurred && resets==1);
 assert(gTasks[0].tCurrentBlock_End==16);
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && !dispatched && gTasks[0].tCurrentBlock_Start==16);
 assert(gBattleControllerExecFlags==(0xFF & ~(2 << 4)));
 ''')

    def test_real_intro_slide_emitter_round_trip(self):
        self.run_c(r'''
 gBattleTypeFlags |= BATTLE_TYPE_LINK;
 BtlController_EmitIntroSlide(B_COMM_TO_CONTROLLER, 0);
 receivedSize=gTasks[sLinkSendTaskId].tCurrentBlock_End;
 assert(receivedSize==12 && gLinkBattleSendBuffer[LINK_BUFF_SIZE_LO]==4);
 memcpy(gBlockRecvBuffer[source],gLinkBattleSendBuffer,receivedSize);
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && !gLinkErrorOccurred && dispatched==1);
 assert(gTasks[0].tCurrentBlock_Start==12 && gBattleBufferA[0][0]==CONTROLLER_INTROSLIDE);
 ''', emitters=('BtlController_EmitIntroSlide',))

    def test_other_real_two_byte_emitters_round_trip(self):
        emitters = ('BtlController_EmitReturnMonToBall', 'BtlController_EmitBallThrowAnim',
                    'BtlController_EmitStatusXor', 'BtlController_EmitResetActionMoveSelection',
                    'BtlController_EmitSetUnkVar')
        for emitter in emitters:
            with self.subTest(emitter=emitter):
                self.run_c(r'''
 gBattleTypeFlags |= BATTLE_TYPE_LINK;
 ''' + emitter + r'''(B_COMM_TO_CONTROLLER, 0);
 receivedSize=gTasks[sLinkSendTaskId].tCurrentBlock_End;
 assert(receivedSize==12 && gLinkBattleSendBuffer[LINK_BUFF_SIZE_LO]==4);
 memcpy(gBlockRecvBuffer[source],gLinkBattleSendBuffer,receivedSize);
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && !gLinkErrorOccurred && dispatched==1);
 assert(gTasks[0].tCurrentBlock_Start==12);
 ''', emitters=(emitter,))

    def test_real_command_emitters_with_other_payload_widths(self):
        emitters = ('BtlController_EmitGetMonData', 'BtlController_EmitSetMonData',
                    'BtlController_EmitSwitchInAnim', 'BtlController_EmitChooseMove',
                    'BtlController_EmitChoosePokemon', 'BtlController_EmitStatusIconUpdate',
                    'BtlController_EmitStatusAnimation', 'BtlController_EmitDataTransfer',
                    'BtlController_EmitTwoReturnValues', 'BtlController_EmitOneReturnValue')
        self.run_c(r'''
 struct BattlePokemon mon={0}, transfer[2];
 struct ChooseMoveStruct moves={0};
 u8 order[3]={0};
 mon.species=1; mon.level=10; mon.hp=mon.maxHP=30;
 mon.attack=mon.defense=mon.speed=mon.spAttack=mon.spDefense=20;
 transfer[0]=transfer[1]=mon;
 source=0;
 gBattleTypeFlags |= BATTLE_TYPE_LINK | BATTLE_TYPE_IS_MASTER;
 #define ROUND_TRIP(call, bufferId) do { \
   memset(gTasks,0,sizeof(gTasks)); \
   sNativeBattleReplyUsed[0]=FALSE; \
   memcpy(sNativeBattleRequest[0],gBattleBufferA[0],sizeof(sNativeBattleRequest[0])); \
   sNativeBattleRequestPending[0]=TRUE; \
   call; \
   receivedSize=gTasks[sLinkSendTaskId].tCurrentBlock_End; \
   memcpy(gBlockRecvBuffer[source],gLinkBattleSendBuffer,receivedSize); \
   TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0); \
   assert(!aborted && !gLinkErrorOccurred); \
   assert(gTasks[0].tCurrentBlock_Start==receivedSize); \
   assert(!memcmp(bufferId == B_COMM_TO_ENGINE ? gBattleBufferB[0] : gBattleBufferA[0], \
                  gLinkBattleSendBuffer+LINK_BUFF_DATA,receivedSize-LINK_BUFF_DATA)); \
 } while (0)
 ROUND_TRIP(BtlController_EmitGetMonData(B_COMM_TO_CONTROLLER, REQUEST_ALL_BATTLE, 0), B_COMM_TO_CONTROLLER);
 ROUND_TRIP(BtlController_EmitSetMonData(B_COMM_TO_CONTROLLER, REQUEST_ALL_BATTLE, 0, sizeof(mon), &mon), B_COMM_TO_CONTROLLER);
 ROUND_TRIP(BtlController_EmitSwitchInAnim(B_COMM_TO_CONTROLLER, 0, 0), B_COMM_TO_CONTROLLER);
 ROUND_TRIP(BtlController_EmitChooseMove(B_COMM_TO_CONTROLLER, 0, 0, &moves), B_COMM_TO_CONTROLLER);
 ROUND_TRIP(BtlController_EmitChoosePokemon(B_COMM_TO_CONTROLLER, 0, 0, 0, order), B_COMM_TO_CONTROLLER);
 ROUND_TRIP(BtlController_EmitStatusIconUpdate(B_COMM_TO_CONTROLLER, 0, 0), B_COMM_TO_CONTROLLER);
 ROUND_TRIP(BtlController_EmitStatusAnimation(B_COMM_TO_CONTROLLER, 0, 0), B_COMM_TO_CONTROLLER);
 gBattleBufferA[0][0]=CONTROLLER_GETMONDATA; gBattleBufferA[0][1]=REQUEST_ALL_BATTLE;
 ROUND_TRIP(BtlController_EmitDataTransfer(B_COMM_TO_ENGINE, sizeof(mon), &mon), B_COMM_TO_ENGINE);
 gBattleBufferA[0][2]=3;
 ROUND_TRIP(BtlController_EmitDataTransfer(B_COMM_TO_ENGINE, sizeof(transfer), transfer), B_COMM_TO_ENGINE);
 gBattleBufferA[0][0]=CONTROLLER_CHOOSEACTION;
 ROUND_TRIP(BtlController_EmitTwoReturnValues(B_COMM_TO_ENGINE, B_ACTION_USE_MOVE, 0x0100), B_COMM_TO_ENGINE);
 gBattleBufferA[0][0]=CONTROLLER_OPENBAG;
 ROUND_TRIP(BtlController_EmitOneReturnValue(B_COMM_TO_ENGINE, 0), B_COMM_TO_ENGINE);
 #undef ROUND_TRIP
 ''', emitters=emitters)

    def test_remote_size_overflow_aborts_before_copy_or_queue_progress(self):
        self.run_c(r'''
 gBlockRecvBuffer[source][2]=65535;
 TryReceiveLinkBattleData();
 assert(aborted==1 && gLinkErrorOccurred);
 assert(!resets && !gTasks[0].tCurrentBlock_End && !dispatched);
 ''')

    def test_invalid_headers_aborted_before_dispatch(self):
        for offset, value in [(0, 255), (1, 200), (2, 4), (3, 255), (6, 16), (7, 4)]:
            with self.subTest(offset=offset):
                self.run_c(r'''
 u8 *p=gLinkBattleRecvBuffer;
 p[0]=B_COMM_TO_ENGINE; p[4]=8; p[8]=CONTROLLER_TWORETURNVALUES;
 gTasks[0].tCurrentBlock_End=16;
 ''' + f'p[{offset}]={value};' + r'''
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(aborted==1 && gLinkErrorOccurred && !dispatched);
 assert(gTasks[0].tCurrentBlock_Start==0);
 ''')

    def test_truncated_or_oversized_queue_record(self):
        for end, size in [(4, 8), (12, 8), (1024, 600), (16, 65535), (8, 0)]:
            with self.subTest(end=end, size=size):
                self.run_c(f'''
 gLinkBattleRecvBuffer[0]=B_COMM_TO_ENGINE;
 gLinkBattleRecvBuffer[4]={size & 255}; gLinkBattleRecvBuffer[5]={size >> 8};
 gTasks[0].tCurrentBlock_End={end};
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(aborted==1 && gLinkErrorOccurred && !gTasks[0].tCurrentBlock_Start);
 ''')

    def test_invalid_done_player_or_wire_size(self):
        for payload_size, player in [(4, 0), (12, 0), (8, 2), (8, 255)]:
            for ingress in [True, False]:
                with self.subTest(payload_size=payload_size, player=player, ingress=ingress):
                    target = '(u8 *)gBlockRecvBuffer[source]' if ingress else 'gLinkBattleRecvBuffer'
                    self.run_c(f'''
 u8 *p={target};
 p[0]=B_COMM_CONTROLLER_IS_DONE; p[4]={payload_size}; p[8]={player};
 receivedSize={payload_size + 8};
 gBattleControllerExecFlags=0xFF;
 ''' + ('TryReceiveLinkBattleData();' if ingress else f'''
 gTasks[0].tCurrentBlock_End={payload_size + 8};
 Task_HandleCopyReceivedLinkBuffersData(0);
 ''') + r'''
 assert(aborted==1 && gLinkErrorOccurred && !gTasks[0].tCurrentBlock_Start);
 assert(gBattleControllerExecFlags==0xFF && !resets && !dispatched);
 ''')

    def test_command_shapes_and_follow_on_indices(self):
        attacks = [
            'p[8]=255;',
            'p[8]=CONTROLLER_MOVEANIMATION;',
            'p[8]=CONTROLLER_CHOOSEMOVE;',
            'p[8]=CONTROLLER_GETMONDATA; p[9]=255;',
            'p[8]=CONTROLLER_GETMONDATA; p[10]=64;',
            'p[8]=CONTROLLER_SWITCHINANIM; p[9]=6;',
            'p[8]=CONTROLLER_GETRAWMONDATA; p[9]=255; p[10]=8;',
            'p[8]=CONTROLLER_SETRAWMONDATA; p[9]=99; p[10]=8;',
            'p[8]=CONTROLLER_DATATRANSFER; p[10]=255; p[11]=255;',
            'p[8]=CONTROLLER_LINKSTANDBYMSG; p[10]=255;',
            'p[0]=B_COMM_TO_ENGINE; p[8]=CONTROLLER_CHOSENMONRETURNVALUE; p[9]=255;',
            'p[0]=B_COMM_TO_ENGINE; p[8]=CONTROLLER_TWORETURNVALUES; p[9]=0; p[10]=4;',
            'p[0]=B_COMM_TO_ENGINE; p[8]=CONTROLLER_TWORETURNVALUES; p[9]=0; p[11]=255;',
        ]
        for attack in attacks:
            with self.subTest(attack=attack):
                self.run_c(r'''
 u8 *p=gLinkBattleRecvBuffer;
 p[0]=B_COMM_TO_CONTROLLER; p[4]=8;
 gTasks[0].tCurrentBlock_End=16;
 ''' + attack + r'''
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(aborted==1 && gLinkErrorOccurred && !dispatched);
 assert(gTasks[0].tCurrentBlock_Start==0 && !gBattleBufferA[0][0]);
 ''')

    def test_bad_command_rejected_before_ingress_queue_progress(self):
        self.run_c(r'''
 u8 *p=(u8 *)gBlockRecvBuffer[source]; p[4]=8; p[8]=255;
 TryReceiveLinkBattleData();
 assert(aborted==1 && gLinkErrorOccurred && !resets);
 assert(gTasks[0].tCurrentBlock_End==0);
 ''')

    def test_short_adapter_blocks_and_padding_disagreement(self):
        for length in [0, 4, 8, 12, 15, 252, 256]:
            with self.subTest(length=length):
                self.run_c(f'''
 u8 *p=(u8 *)gBlockRecvBuffer[source]; p[0]=B_COMM_TO_ENGINE; p[4]=8; p[8]=CONTROLLER_TWORETURNVALUES;
 receivedSize={length}; TryReceiveLinkBattleData();
 assert(aborted==1 && gLinkErrorOccurred && !resets && !gTasks[0].tCurrentBlock_End);
 ''')

    def test_ring_wrap_and_busy_consumer_preserve_order(self):
        self.run_c(r'''
 u8 *p=(u8 *)gBlockRecvBuffer[source]; p[0]=B_COMM_TO_CONTROLLER; p[4]=8; p[8]=CONTROLLER_LOADMONSPRITE;
 gTasks[0].tCurrentBlock_Start=4080; gTasks[0].tCurrentBlock_End=4080;
 TryReceiveLinkBattleData();
 assert(!aborted && gTasks[0].tCurrentBlock_End==16 && gTasks[0].tCurrentBlock_WrapFrom==4080);
 gBattleControllerExecFlags=1; Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!dispatched && !aborted);
 gBattleControllerExecFlags=0; Task_HandleCopyReceivedLinkBuffersData(0);
 assert(dispatched==1 && gTasks[0].tCurrentBlock_Start==16 && !aborted);
 ''')

    def test_ring_capacity_exhaustion_aborts_without_overwrite(self):
        for start, end, wrap in [(16, 4080, 0), (32, 16, 4080)]:
            with self.subTest(start=start):
                self.run_c(f'''
 u8 *p=(u8 *)gBlockRecvBuffer[source]; p[0]=B_COMM_TO_ENGINE; p[4]=8; p[8]=CONTROLLER_TWORETURNVALUES;
 gTasks[0].tCurrentBlock_Start={start}; gTasks[0].tCurrentBlock_End={end}; gTasks[0].tCurrentBlock_WrapFrom={wrap};
 TryReceiveLinkBattleData();
 assert(aborted==1 && gLinkErrorOccurred && !resets);
 assert(gTasks[0].tCurrentBlock_End=={end});
 ''')

    def test_inactive_path_is_not_changed_by_native_error_guards(self):
        self.run_c(r'''
 active=0; gLinkErrorOccurred=1;
 u8 *p=gLinkBattleRecvBuffer; p[0]=B_COMM_TO_ENGINE; p[4]=8; p[8]=CONTROLLER_TWORETURNVALUES;
 gTasks[0].tCurrentBlock_End=16;
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && gTasks[0].tCurrentBlock_Start==16);
 ''')

    def test_mon_data_reply_cannot_overflow_transfer_staging(self):
        self.run_c(r'''
 u8 *p=gLinkBattleRecvBuffer; p[0]=B_COMM_TO_CONTROLLER; p[4]=8;
 p[8]=CONTROLLER_GETMONDATA; p[9]=REQUEST_ALL_BATTLE; p[10]=63;
 gTasks[0].tCurrentBlock_End=16;
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(aborted==1 && gLinkErrorOccurred && !dispatched);
 ''')

    def test_benign_command_shapes(self):
        self.run_c(r'''
 const struct { u8 command; u16 length; } fixtures[] = {
 {CONTROLLER_GETMONDATA, 4}, {CONTROLLER_SETMONDATA, 3 + sizeof(struct BattlePokemon)},
 {CONTROLLER_LOADMONSPRITE, 4}, {CONTROLLER_SWITCHINANIM, 4},
 {CONTROLLER_RETURNMONTOBALL, 2}, {CONTROLLER_MOVEANIMATION, 16 + sizeof(struct DisableStruct)},
 {CONTROLLER_PRINTSTRING, 4 + sizeof(struct BattleMsgData)},
 {CONTROLLER_CHOOSEMOVE, 4 + sizeof(struct ChooseMoveStruct)},
 {CONTROLLER_CHOOSEPOKEMON, 8}, {CONTROLLER_STATUSICONUPDATE, 9},
 {CONTROLLER_STATUSANIMATION, 6}, {CONTROLLER_DRAWPARTYSTATUSSUMMARY, 4 + 6 * sizeof(struct HpAndStatus)},
 {CONTROLLER_LINKSTANDBYMSG, 4}, {CONTROLLER_ENDLINKBATTLE, 6},
 {CONTROLLER_RESETACTIONMOVESELECTION, 2}, {CONTROLLER_HEALTHBARUPDATE, 4}
 };
 for (unsigned i=0; i<ARRAY_COUNT(fixtures); i++) {
   memset(gTasks,0,sizeof(gTasks)); memset(gBlockRecvBuffer,0,sizeof(gBlockRecvBuffer));
   u8 *p=(u8 *)gBlockRecvBuffer[source]; p[0]=B_COMM_TO_CONTROLLER;
   p[4]=fixtures[i].length - fixtures[i].length % 4 + 4;
   receivedSize=p[4]+8; p[8]=fixtures[i].command;
   TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
   assert(!aborted && dispatched==(int)i+1 && gTasks[0].tCurrentBlock_Start==receivedSize);
 }
 ''')

    def test_maximum_packet_and_repeated_legal_wraps(self):
        self.run_c(r'''
 u8 *p=(u8 *)gBlockRecvBuffer[source]; p[0]=B_COMM_TO_CONTROLLER; p[4]=244;
 p[8]=CONTROLLER_32; p[9]=236; receivedSize=252;
 for (unsigned i=0; i<100; i++) {
   p[11]=(u8)i;
   TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
   assert(!aborted && !gLinkErrorOccurred && gBattleBufferA[0][3]==(u8)i);
   assert(gTasks[0].tCurrentBlock_Start==gTasks[0].tCurrentBlock_End);
 }
 ''')

    def test_abort_latches_before_inactive_vanilla_fallback(self):
        self.run_c(r'''
 gLinkBattleRecvBuffer[0]=255; gLinkBattleRecvBuffer[4]=8;
 gTasks[0].tCurrentBlock_End=16;
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(aborted==1 && !active && gLinkErrorOccurred);
 gLinkBattleRecvBuffer[0]=B_COMM_TO_CONTROLLER;
 gLinkBattleRecvBuffer[8]=CONTROLLER_LOADMONSPRITE;
 Task_HandleCopyReceivedLinkBuffersData(0); TryReceiveLinkBattleData();
 assert(aborted==1 && !dispatched && !gTasks[0].tCurrentBlock_Start && !resets);
 ''')

    def test_set_raw_mon_uses_party_mon_not_smaller_battle_mon_bound(self):
        self.run_c(r'''
 u8 *p=gLinkBattleRecvBuffer; p[0]=B_COMM_TO_CONTROLLER; p[4]=8;
 p[8]=CONTROLLER_SETRAWMONDATA; p[9]=99; p[10]=1;
 sNativeBattleSources[0]=1;
 gTasks[0].tCurrentBlock_End=16;
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && dispatched==1 && gTasks[0].tCurrentBlock_Start==16);
 ''')

    def test_benign_engine_packet(self):
        self.run_c(r'''
 u8 *p=(u8 *)gBlockRecvBuffer[source];
 p[0]=B_COMM_TO_ENGINE; p[1]=1; p[4]=8;
 p[8]=CONTROLLER_TWORETURNVALUES; p[9]=0; p[10]=0; p[11]=1;
 gBattleTypeFlags |= BATTLE_TYPE_IS_MASTER;
 gBattleBufferA[1][0]=CONTROLLER_CHOOSEACTION;
 memcpy(sNativeBattleRequest[1],gBattleBufferA[1],sizeof(sNativeBattleRequest[1]));
 sNativeBattleRequestPending[1]=TRUE;
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && !gLinkErrorOccurred && resets==1);
 assert(gTasks[0].tCurrentBlock_Start==16 && gTasks[0].tCurrentBlock_End==16);
 assert(!memcmp(gBattleBufferB[1],p+8,8));
 ''')


if __name__ == '__main__':
    unittest.main()
