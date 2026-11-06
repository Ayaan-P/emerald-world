"""Compile the production pre-turn phase with instrumented engine boundaries."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def body(source, name):
    start = source.index('static bool8 ' + name + '(void)\n{')
    end = source.index('\n}\n', start) + 3
    return source[start:end]


class MegaTurnTests(unittest.TestCase):
    def test_transform_and_abilities_finish_before_ordering(self):
        source = (ROOT / 'src/battle_main.c').read_text()
        self.assertIn('static bool8 TryMegaEvolutionBeforeTurn(void)\n{', source)
        function = body(source, 'TryMegaEvolutionBeforeTurn')
        fixture = r'''
#include <assert.h>
#include <stdint.h>
typedef uint8_t u8; typedef uint8_t bool8;
#define TRUE 1
#define FALSE 0
#define MEGA_FEATURE_READY 1
#define MEGA_WIRE_ACTIVATE 1
#define MAX_BATTLERS_COUNT 4
#define B_ACTION_USE_MOVE 0
#define B_WIN_MSG 0
#define ABILITYEFFECT_ON_SWITCHIN 0
#define ABILITYEFFECT_INTIMIDATE1 9
#define ABILITYEFFECT_TRACE 11
#define STATUS3_INTIMIDATE_POKES 1
#define STATUS3_TRACE 2
#define _(s) s
u8 sMegaTurnBattler, sMegaTurnPhase, sMegaTurnDelay;
struct {u8 battler;} gBattleScripting;
const u8 BattleScript_MegaEvolved[1]={0};
void BattleScriptPushCursorAndCallback(const u8 *p){assert(p==BattleScript_MegaEvolved);}
bool8 sMegaTurnAbilityChanged;
struct {u8 ability;} gBattleMons[4];
struct {bool8 noValidMoves;} gProtectStructs[4];
u8 gBattlersCount=2, gChosenActionByBattler[4], gActiveBattler;
unsigned gBattleControllerExecFlags, gBattleOutcome, gStatuses3[4];
struct {unsigned intimidatedMon,traced;} gSpecialStatuses[4];
int applied,drawn,abilities,appliedMask;
void MegaGame_CancelQueue(u8 b){(void)b;}
bool8 MegaGame_Apply(u8 b){if(appliedMask&(1<<b))return 0;appliedMask|=1<<b;applied++;gBattleMons[b].ability++;return 1;}
bool8 MegaGame_PublishForm(u8 b,u8 kind){(void)b;(void)kind;return FALSE;}
void MegaGame_RefreshSprite(u8 b){(void)b;drawn++;}
void BattlePutTextOnWindow(const u8 *s,int w){(void)s;(void)w;}
int AbilityBattleEffects(int effect,int battler,int a,int b,int c){
 (void)battler;(void)a;(void)b;(void)c;
 if(effect==ABILITYEFFECT_ON_SWITCHIN){abilities++;return 1;}return 0;
}
'''
        fixture += function
        fixture += r'''
int main(void){
 int frames=0;
 gBattleControllerExecFlags=1;
 assert(TryMegaEvolutionBeforeTurn());assert(!applied);
 gBattleControllerExecFlags=0;
 while(TryMegaEvolutionBeforeTurn()){assert(++frames<200);}
 assert(applied==2 && drawn==2 && abilities==2);
 assert(sMegaTurnBattler==2);assert(!TryMegaEvolutionBeforeTurn());
 sMegaTurnBattler=sMegaTurnPhase=sMegaTurnDelay=0;applied=drawn=abilities=appliedMask=0;
 gBattleOutcome=1;assert(!TryMegaEvolutionBeforeTurn());assert(!applied);
 return 0;
}
'''
        out = ROOT / 'build/rc4-mega'
        out.mkdir(parents=True, exist_ok=True)
        (out / 'turn_phase.c').write_text(fixture)
        result = subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(out / 'turn_phase.c'), '-o', str(out / 'turn_phase')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(out / 'turn_phase')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        order = body(source.replace('static void SetActionsAndBattlersTurnOrder(void)\n{', 'static bool8 SetActionsAndBattlersTurnOrder(void)\n{'), 'SetActionsAndBattlersTurnOrder')
        self.assertLess(order.index('TryMegaEvolutionBeforeTurn()'), order.index('GetWhoStrikesFirst('))


if __name__ == '__main__':
    unittest.main()
