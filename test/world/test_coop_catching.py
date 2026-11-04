"""Source-boundary regressions only. These are not native gameplay acceptance."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def function(path, name):
    text = (ROOT / path).read_text()
    import re
    match = re.search(r'^.*\b' + re.escape(name) + r'\([^;]*?\)\n\{', text, re.M)
    if not match:
        raise AssertionError('Missing production function ' + name)
    start = match.start()
    end = text.index('\n}\n', start) + 3
    return text[start:end]


class CoopCatching(unittest.TestCase):
    def test_private_catch_path_is_commit_gated_and_not_mixed_party(self):
        coop = (ROOT / 'src/platform/world_coop.c').read_text()
        self.assertIn('bool8 WorldCoop_BeginCatchRewards(', coop)
        body = function('src/platform/world_coop.c', 'WorldCoop_BeginCatchRewards')
        self.assertIn('sCoop.state != COOP_REWARDS', body)
        self.assertIn('sCoop.catchOwner != sCoop.local + 1', body)
        self.assertIn('sCoop.catchDelivered', body)
        scripts = (ROOT / 'src/battle_script_commands.c').read_text()
        self.assertIn('WorldCoop_EmitCatch()', scripts)
        main = function('src/battle_main.c', 'CoopPrivateRewards')
        self.assertIn('WorldCoop_BeginCatchRewards()', main)
        self.assertIn('BattleScript_CoopPrivateCatch', main)

    def test_capture_scripts_use_assembler_portable_guard(self):
        text = (ROOT / 'data/battle_scripts_2.s').read_text()
        start = text.index('BattleScript_CoopSharedCatch::')
        self.assertIn('.ifdef PORTABLE', text[:start])
        self.assertNotIn('#ifdef PORTABLE', text)
        self.assertIn('.endif', text[start:])

    def test_capture_emits_the_end_record_before_parking_master(self):
        body = function('src/battle_main.c', 'HandleEndTurn_FinishBattle')
        coop = body[body.index('if (WorldCoop_IsBattle())'):body.index('gBattleMainFunc = BeginBattleIntroDummy;')]
        self.assertIn('gBattleOutcome == B_OUTCOME_CAUGHT', coop)
        self.assertIn('BtlController_EmitEndLinkBattle', coop)

    def test_master_ball_does_not_index_before_bonus_table(self):
        body = function('src/battle_script_commands.c', 'Cmd_handleballthrow')
        self.assertIn('gLastUsedItem == ITEM_MASTER_BALL ? 0 :', body)

    def test_production_catch_boundaries(self):
        with tempfile.TemporaryDirectory(prefix='coop-catching-core-') as tmp:
            exe = str(Path(tmp) / 'core')
            command = ['gcc', '-std=gnu99', '-g', '-fsanitize=address,undefined',
                       '-fno-sanitize-recover=all', '-fno-pie', '-no-pie',
                       '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
                       '-DPORTABLE', '-DUBFIX', '-DVER_64BIT', '-DNONMATCHING',
                       '-DMODERN=1', '-iquote', 'include',
                       'test/world/coop_catching_core.c', '-o', exe]
            compiled = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            for arguments in ([], ['malformed-completion']):
                result = subprocess.run([exe] + arguments, cwd=tmp, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_solicited_ball_reply_rejects_nonballs_and_opponent_battlers(self):
        import test_link_battle_payloads as payloads
        payloads.LinkBattlePayloadTests().run_c(r'''
 coopMode=TRUE;
 u8 reply[8]={CONTROLLER_ONERETURNVALUE, ITEM_POKE_BALL, 0, 0};
 sNativeBattleRequestPending[2]=TRUE;
 sNativeBattleRequest[2][0]=CONTROLLER_OPENBAG;
 assert(NativeBattleReplyValid(2, reply));
 reply[1]=ITEM_POTION;
 assert(!NativeBattleReplyValid(2, reply));
 reply[1]=ITEM_SAFARI_BALL;
 assert(!NativeBattleReplyValid(2, reply));
 reply[1]=ITEM_POKE_BALL; reply[3]=1;
 assert(!NativeBattleReplyValid(2, reply));
 reply[3]=0;
 sNativeBattleRequestPending[1]=TRUE;
 sNativeBattleRequest[1][0]=CONTROLLER_OPENBAG;
 assert(!NativeBattleReplyValid(1, reply));
 sNativeBattleReplyUsed[2]=TRUE;
 assert(!NativeBattleReplyValid(2, reply));
 sNativeBattleReplyUsed[2]=FALSE;
 sNativeBattleRequest[2][0]=CONTROLLER_CHOOSEMOVE;
 assert(!NativeBattleReplyValid(2, reply));
''')

    def test_ball_admission_uses_private_capacity_and_rejects_trainers(self):
        source = (ROOT / 'src/platform/world_coop.c').read_text()
        self.assertIn('bool8 WorldCoop_CanSelectBall(', source)
        production = function('src/platform/world_coop.c', 'WorldCoop_CanSelectBall')
        body = '''
#include <assert.h>
typedef unsigned char u8;
typedef unsigned short u16;
typedef int bool8;
#define COOP_BATTLE 2
#define PARTY_SIZE 6
#define ITEM_MASTER_BALL 1
#define LAST_BALL 12
#define ITEM_SAFARI_BALL 5
static struct { int state, kind, originalCount; } sCoop;
static int full;
static int IsPokemonStorageFull(void) { return full; }
''' + production + '''
int main(void) {
 sCoop.state = COOP_BATTLE;
 for (int trainer=0; trainer<3; trainer++)
 for (int count=1; count<=6; count++)
 for (full=0; full<2; full++)
 for (int ball=0; ball<15; ball++) {
  sCoop.kind=trainer; sCoop.originalCount=count;
  assert(WorldCoop_CanSelectBall(ball) == (!trainer && ball>=1 && ball<=12 && ball!=5 && (count<6 || !full)));
 }
 sCoop.state=0; assert(!WorldCoop_CanSelectBall(4));
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='coop-catching-') as tmp:
            path = Path(tmp) / 'test.c'
            path.write_text(body)
            compiled = subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(path), '-o', str(path.with_suffix(''))], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(path.with_suffix(''))], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
