"""First co-op mon reply must survive the real local-controller completion.

Compiles production FIFO/validation/emitter/completion functions using the
existing payload harness. BattlePokemon is an explicit valid transport fixture,
not a claim to run a game or decode a private party. No network/game launched.
"""
import unittest
from unittest.mock import patch

import test_link_battle_payloads as payloads


class CoopControllerCompletionRepro(unittest.TestCase):
    def exercise(self, complete):
        source = (payloads.ROOT / 'src/battle_controller_player.c').read_text()
        completion = payloads.function(source, 'PlayerBufferExecCompleted')
        original = payloads.function

        def extract(text, name):
            result = original(text, name)
            if name == 'BtlController_EmitDataTransfer':
                result += r'''
static void PlayerBufferRunCommand(void) {}
static void (*gBattlerControllerFuncs[4])(void);
''' + completion
            return result

        # This is the exact emit -> complete sequence used at PlayerHandleGetMonData
        # lines 1615-1616. The control differs only by omitting completion.
        body = r'''
 coopMode=TRUE; source=localPlayer=0; gActiveBattler=0;
 gBattleTypeFlags |= BATTLE_TYPE_LINK | BATTLE_TYPE_IS_MASTER | BATTLE_TYPE_MULTI | BATTLE_TYPE_DOUBLE;
 struct BattlePokemon mon={0};
 mon.species=1; mon.level=10; mon.hp=mon.maxHP=30;
 mon.attack=mon.defense=mon.speed=mon.spAttack=mon.spDefense=20;
 assert(NativeBattleMonValid((u8 *)&mon));
 BtlController_EmitGetMonData(B_COMM_TO_CONTROLLER, REQUEST_ALL_BATTLE, 0);
 receivedSize=gTasks[sLinkSendTaskId].tCurrentBlock_End;
 memcpy(gBlockRecvBuffer[source],gLinkBattleSendBuffer,receivedSize);
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && dispatched==1 && sNativeBattleRequestPending[0]);
 assert(gBattleBufferA[0][0]==CONTROLLER_GETMONDATA);
 memset(gTasks[sLinkSendTaskId].data,0,sizeof(gTasks[sLinkSendTaskId].data));
 BtlController_EmitDataTransfer(B_COMM_TO_ENGINE,sizeof(mon),&mon);
 /* Record reply size before completion also enqueues its separate ACK. */
 receivedSize=gTasks[sLinkSendTaskId].tCurrentBlock_End;
''' + (r'''
 PlayerBufferExecCompleted();
 assert(gBattleBufferA[0][0]==CONTROLLER_TERMINATOR_NOP);
 assert(sNativeBattleRequestPending[0] && !sNativeBattleReplyUsed[0]);
''' if complete else '') + r'''
 memcpy(gBlockRecvBuffer[source],gLinkBattleSendBuffer,receivedSize);
 assert(NativeBattleHeaderValid((u8 *)gBlockRecvBuffer[source],receivedSize));
 assert(NativeBattleSourceValid((u8 *)gBlockRecvBuffer[source],source));
 TryReceiveLinkBattleData(); Task_HandleCopyReceivedLinkBuffersData(0);
 assert(!aborted && "valid solicited mon response rejected after controller completion");
 assert(!memcmp(gBattleBufferB[0]+4,&mon,sizeof(mon)));
 assert(observedMon==1 && observedBattler==0 && observedSlot==0);
 assert(observedController==1);
'''
        with patch.object(payloads, 'function', extract):
            payloads.LinkBattlePayloadTests().run_c(body, emitters=(
                'BtlController_EmitGetMonData', 'BtlController_EmitDataTransfer'))

    def test_control_without_completion_accepts_same_mon(self):
        self.exercise(False)

    def test_real_completion_preserves_solicited_response(self):
        self.exercise(True)

    def test_real_completion_does_not_read_beyond_its_one_byte_identity(self):
        self.exercise(True)


if __name__ == '__main__':
    unittest.main()
