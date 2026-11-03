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
#include "constants/global.h"
#include "constants/moves.h"
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
static u16 gBlockRecvBuffer[5][128];
static u8 gBattleBufferA[4][512], gBattleBufferB[4][512];
/* Party mons have the fixed 100-byte save layout. */
static u8 gPlayerParty[6][100];
static u8 *gLinkBattleRecvBuffer;
static u32 gBattleTypeFlags = BATTLE_TYPE_LINK_IN_BATTLE;
static u32 gBattleControllerExecFlags;
static u8 gReceivedRemoteLinkPlayers = 1, gLinkErrorOccurred;
static u8 gBattlerAttacker, gBattlerTarget, gAbsentBattlerFlags, gEffectBattler;
static const u32 gBitTable[4] = {1,2,4,8};
static int active = 1, aborted, dispatched, resets;
static u16 receivedSize = 16;
static int NativeLink_IsActive(void) { return active; }
static void NativeLink_Abort(void) { active=0; aborted++; }
static u16 GetBlockReceivedSize(u8 i) { (void)i; return receivedSize; }
static u8 GetLinkPlayerCount(void) { return 2; }
static u8 GetBlockReceivedStatus(void) { return 2; }
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
        code = PREAMBLE + 'static bool8 sNativeBattlePayloadFailed;\n' + actions + structs + enums + flags + macros + offsets + helpers
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
            result = subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu99', '-iquote' + str(ROOT / 'include'), '-DPORTABLE', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie', str(path / 'test.c'), '-o', str(path / 'test')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(path / 'test')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

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
 memcpy(gBlockRecvBuffer[1],gLinkBattleSendBuffer,receivedSize);
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
 memcpy(gBlockRecvBuffer[1],gLinkBattleSendBuffer,receivedSize);
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
 memcpy(gBlockRecvBuffer[1],gLinkBattleSendBuffer,receivedSize);
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
 struct BattlePokemon mon={0};
 struct ChooseMoveStruct moves={0};
 u8 order[3]={0}, transfer[236]={0};
 gBattleTypeFlags |= BATTLE_TYPE_LINK;
 #define ROUND_TRIP(call, bufferId) do { \
   memset(gTasks,0,sizeof(gTasks)); \
   call; \
   receivedSize=gTasks[sLinkSendTaskId].tCurrentBlock_End; \
   memcpy(gBlockRecvBuffer[1],gLinkBattleSendBuffer,receivedSize); \
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
 ROUND_TRIP(BtlController_EmitDataTransfer(B_COMM_TO_ENGINE, sizeof(mon), &mon), B_COMM_TO_ENGINE);
 ROUND_TRIP(BtlController_EmitDataTransfer(B_COMM_TO_ENGINE, sizeof(transfer), transfer), B_COMM_TO_ENGINE);
 ROUND_TRIP(BtlController_EmitTwoReturnValues(B_COMM_TO_ENGINE, B_ACTION_USE_MOVE, 0x0100), B_COMM_TO_ENGINE);
 ROUND_TRIP(BtlController_EmitOneReturnValue(B_COMM_TO_ENGINE, 0), B_COMM_TO_ENGINE);
 #undef ROUND_TRIP
 ''', emitters=emitters)

    def test_remote_size_overflow_aborts_before_copy_or_queue_progress(self):
        self.run_c(r'''
 gBlockRecvBuffer[1][2]=65535;
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
                    target = '(u8 *)gBlockRecvBuffer[1]' if ingress else 'gLinkBattleRecvBuffer'
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
 u8 *p=(u8 *)gBlockRecvBuffer[1]; p[4]=8; p[8]=255;
 TryReceiveLinkBattleData();
 assert(aborted==1 && gLinkErrorOccurred && !resets);
 assert(gTasks[0].tCurrentBlock_End==0);
 ''')

    def test_short_adapter_blocks_and_padding_disagreement(self):
        for length in [0, 4, 8, 12, 15, 252, 256]:
            with self.subTest(length=length):
                self.run_c(f'''
 u8 *p=(u8 *)gBlockRecvBuffer[1]; p[0]=B_COMM_TO_ENGINE; p[4]=8; p[8]=CONTROLLER_TWORETURNVALUES;
 receivedSize={length}; TryReceiveLinkBattleData();
 assert(aborted==1 && gLinkErrorOccurred && !resets && !gTasks[0].tCurrentBlock_End);
 ''')

    def test_ring_wrap_and_busy_consumer_preserve_order(self):
        self.run_c(r'''
 u8 *p=(u8 *)gBlockRecvBuffer[1]; p[0]=B_COMM_TO_CONTROLLER; p[4]=8; p[8]=CONTROLLER_LOADMONSPRITE;
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
 u8 *p=(u8 *)gBlockRecvBuffer[1]; p[0]=B_COMM_TO_ENGINE; p[4]=8; p[8]=CONTROLLER_TWORETURNVALUES;
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
   u8 *p=(u8 *)gBlockRecvBuffer[1]; p[0]=B_COMM_TO_CONTROLLER;
   p[4]=fixtures[i].length - fixtures[i].length % 4 + 4;
   receivedSize=p[4]+8; p[8]=fixtures[i].command;
   TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
   assert(!aborted && dispatched==(int)i+1 && gTasks[0].tCurrentBlock_Start==receivedSize);
 }
 ''')

    def test_maximum_packet_and_repeated_legal_wraps(self):
        self.run_c(r'''
 u8 *p=(u8 *)gBlockRecvBuffer[1]; p[0]=B_COMM_TO_ENGINE; p[4]=244;
 p[8]=CONTROLLER_DATATRANSFER; p[10]=236; receivedSize=252;
 for (unsigned i=0; i<100; i++) {
   p[12]=(u8)i;
   TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
   assert(!aborted && !gLinkErrorOccurred && gBattleBufferB[0][4]==(u8)i);
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
 gTasks[0].tCurrentBlock_End=16;
 Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && dispatched==1 && gTasks[0].tCurrentBlock_Start==16);
 ''')

    def test_benign_engine_packet(self):
        self.run_c(r'''
 u8 *p=(u8 *)gBlockRecvBuffer[1];
 p[0]=B_COMM_TO_ENGINE; p[1]=1; p[4]=8;
 p[8]=CONTROLLER_TWORETURNVALUES; p[9]=0; p[10]=0; p[11]=1;
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && !gLinkErrorOccurred && resets==1);
 assert(gTasks[0].tCurrentBlock_Start==16 && gTasks[0].tCurrentBlock_End==16);
 assert(!memcmp(gBattleBufferB[1],p+8,8));
 ''')


if __name__ == '__main__':
    unittest.main()
