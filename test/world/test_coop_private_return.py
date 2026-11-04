"""Exercise shared-to-private reward dispatch without starting a game."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]


class CoopPrivateReturnTests(unittest.TestCase):
    def test_level_up_message_is_consumed_after_shared_attacker_retires(self):
        main = (ROOT / 'src/battle_main.c').read_text()
        player = (ROOT / 'src/battle_controller_player.c').read_text()
        util = (ROOT / 'src/battle_util.c').read_text()
        commands = (ROOT / 'src/battle_script_commands.c').read_text()
        code = r'''
#include <assert.h>
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
#define PORTABLE
#define FALSE 0
#define TRUE 1
#define B_POSITION_PLAYER_LEFT 0
#define B_POSITION_OPPONENT_LEFT 1
#define B_OUTCOME_WON 1
#define BATTLE_TYPE_LINK 1
#define B_COMM_TO_CONTROLLER 0
#define B_COMM_CONTROLLER_IS_DONE 2
#define CONTROLLER_TERMINATOR_NOP 255
#define MSG_DISPLAY 0
#define PALETTES_ALL 0
#define RGB_BLACK 0
#define ARRAY_COUNT(a) (sizeof(a) / sizeof((a)[0]))
#define T2_READ_16(p) ((p)[0] | ((p)[1] << 8))
#define MARK_BATTLE_CONTROLLER_MESSAGE_OUTBOUND_OVER_LINK(b) (gBattleControllerExecFlags |= gBitTable[b] << 28)
#define MARK_BATTLE_CONTROLLER_ACTIVE_ON_LOCAL(b) (gBattleControllerExecFlags |= gBitTable[b])
static const unsigned gBitTable[] = {1, 2, 4, 8};
static unsigned gBattleTypeFlags, gBattleControllerExecFlags;
static u8 gActiveBattler, gBattlerAttacker, gBattlerTarget, gBattlersCount;
static u8 gBattlerSpriteIds[4], gBattlerPositions[4], gAbsentBattlerFlags;
static u8 gLeveledUpInBattle, gBattleCommunication[8];
static u8 gBattleBufferA[4][8], gDoingBattleAnim, gPlayerDpadHoldFrames;
static u8 levelUpPrint[] = {0x10, 123, 0};
static const u8 *gBattlescriptCurrInstr;
static void (*gBattleMainFunc)(void), (*gBattlerControllerFuncs[4])(void);
static struct { u8 multiplayerId; } gBattleScripting;
static struct { void (*callback1)(void); } gMain;
static struct { u8 size; } scripts, callbacks;
static struct { typeof(scripts) *battleScriptsStack, *battleCallbackStack; } resources = {&scripts, &callbacks};
static typeof(resources) *gBattleResources = &resources;
static int printed, prepared;
static u8 sCoopTrainerPrizeDone, sCoopPayoffDone;
static void BattleMainCB1(void);
static void PlayerBufferRunCommand(void);
static void BattleControllerDummy(void) {}
static int WorldCoop_IsTrainer(void) { return 0; }
static int WorldCoop_PreparePrivateRewards(void) {
    prepared++; gBattleTypeFlags = 0; gBattleControllerExecFlags = 0; return 1;
}
static void ResetTasks(void) {}
static void BattleRebuildPrivateRewardHealthbox(void) {}
static void CoopPrivateRewards(void) {}
static void BeginNormalPaletteFade(unsigned a, int b, int c, int d, int e) {
    (void)a; (void)b; (void)c; (void)d; (void)e;
}
static void BattleMainCB2(void) {}
static void SetMainCallback2(void (*cb)(void)) { assert(cb == BattleMainCB2); }
static u8 GetMultiplayerId(void) { return gBattleScripting.multiplayerId; }
static void PrepareBufferDataTransferLink(u8 a, u16 b, const void *c) {
    (void)a; (void)b; (void)c; assert(!"private command used link");
}
'''
        for source, name in ((player, 'SetControllerToPlayer'),
                             (player, 'PlayerBufferExecCompleted')):
            code += function(source, name)
        code += r'''
static void PrintMessage(void) { printed++; PlayerBufferExecCompleted(); }
static void (*sPlayerBufferCommands[])(void) = {PrintMessage};
static void BtlController_EmitPrintString(u8 id, u16 stringId) {
    assert(id == B_COMM_TO_CONTROLLER && stringId == 123);
    gBattleBufferA[gActiveBattler][0] = 0;
}
'''
        for source, name in ((player, 'PlayerBufferRunCommand'),
                             (util, 'MarkBattlerForControllerExec'),
                             (util, 'PrepareStringBattle'),
                             (commands, 'Cmd_printstring'),
                             (main, 'WorldCoop_BeginPrivateRewards'),
                             (main, 'BattleMainCB1')):
            code += function(source, name)
        code += r'''
int main(void) {
    /* Either wire role can retain any shared attacker. Even opponent 1 is
     * now a dummy controller. Private messages must use player controller 0. */
    for (u8 role = 0; role < 2; role++) {
        for (u8 attacker = 0; attacker < 4; attacker++) {
            printed = prepared = 0;
            gBattleScripting.multiplayerId = role;
            gBattlerAttacker = attacker; gBattlerTarget = 1;
            gBattlerSpriteIds[0] = 10; gBattlerSpriteIds[2] = 12;
            gBattleTypeFlags = BATTLE_TYPE_LINK;
            WorldCoop_BeginPrivateRewards();
            assert(prepared == 1 && gBattlersCount == 2);
            assert(gBattlerSpriteIds[0] == (role ? 12 : 10));
            gBattlescriptCurrInstr = levelUpPrint;
            gBattleMainFunc = Cmd_printstring;
            BattleMainCB1();
            assert(printed == 1 && "level-up message dispatched to a retired controller");
            assert(gBattleControllerExecFlags == 0);
        }
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='coop-private-return-') as tmp:
            c, exe = Path(tmp) / 'test.c', Path(tmp) / 'test'
            c.write_text(code)
            build = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                                    str(c), '-o', str(exe)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == '__main__':
    unittest.main()
