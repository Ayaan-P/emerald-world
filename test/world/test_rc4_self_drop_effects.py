"""Native self-drop seam: real GAS bytecode and extracted production C commands.

Only presentation opcodes are skipped. Hit outcome flags are inputs at the
seteffectwithchance boundary, not a replacement accuracy/damage implementation.
SetMoveEffect is sliced to its unchanged entry gates and the relevant dispatch
cases, avoiding unrelated status/item machinery. Stat mutation is never mocked.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def function(source, name):
    match = re.search(r'^(?:static )?(?:void|u8|bool8) ' + name + r'\([^;]*?\)\n\{', source, re.M)
    assert match, name
    end = source.index('\n}\n', match.end()) + 3
    return source[match.start():end]


def block(source, start, end):
    text = source[source.index(start + '::'):source.index(end + '::')]
    return '\n'.join(line for line in text.splitlines()
                     if not line.startswith(('.ifdef', '.endif'))) + '\n'


class SelfDropEffects(unittest.TestCase):
    def test_portable_secondary_effect_fits_native_status_table(self):
        result = subprocess.run(['cc', '-std=gnu11', '-DPORTABLE', '-iquote', str(ROOT / 'include'), '-x', 'c', '-fsyntax-only', '-'], input='''#include "constants/battle.h"
_Static_assert(MOVE_EFFECT_DEF_SPDEF_DOWN < NUM_MOVE_EFFECTS, "paired effect indexes native status table");
_Static_assert(MOVE_EFFECT_DEF_SPDEF_DOWN < MOVE_EFFECT_AFFECTS_USER, "effect overlaps flags");
_Static_assert(MOVE_EFFECT_SELF_SPEED_DOWN < NUM_MOVE_EFFECTS, "speed effect indexes native status table");
_Static_assert(MOVE_EFFECT_SELF_SPEED_DOWN < MOVE_EFFECT_AFFECTS_USER, "speed effect overlaps flags");
''', capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_effect_pointer_table_counts_portable_and_vanilla(self):
        scripts = (ROOT / 'data/battle_scripts_1.s').read_text()
        table = scripts[scripts.index('gBattleScriptsForMoveEffects::'):scripts.index('BattleScript_EffectHit::')]
        for portable, count in ((True, 216), (False, 214)):
            with self.subTest(portable=portable), tempfile.TemporaryDirectory(prefix='rc4-self-drop-table-') as tmp:
                tmp = Path(tmp)
                cpp = subprocess.run(['cc', '-E', '-P', '-x', 'c', '-iquote', str(ROOT / 'include')] + (['-DPORTABLE=PORTABLE'] if portable else []) + ['-'], input='#include "constants/battle_move_effects.h"\n#include "constants/battle.h"\nNUM_BATTLE_MOVE_EFFECTS NUM_MOVE_EFFECTS\n', capture_output=True, text=True)
                self.assertEqual(cpp.returncode, 0, cpp.stderr)
                self.assertEqual(cpp.stdout.strip().splitlines()[-1].split(), [str(count), '62' if portable else '60'])
                asm = '.include "asm/macros/bit_width.inc"\n.set VER_64BIT, 1\n'
                if portable:
                    asm += '.set PORTABLE, 1\n'
                asm += table.replace('gBattleScriptsForMoveEffects::', '.global gBattleScriptsForMoveEffects\ngBattleScriptsForMoveEffects:')
                asm += f'\n.if (.-gBattleScriptsForMoveEffects) != {count} * 8\n.error "effect pointer table count mismatch"\n.endif\n'
                (tmp / 'table.s').write_text(asm)
                result = subprocess.run(['cc', '-c', str(tmp / 'table.s'), '-o', str(tmp / 'table.o')], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                if portable:
                    entries = re.findall(r'ptrvalue (\w+)', table)
                    self.assertEqual(entries[-2:], ['BattleScript_EffectDefSpDefDownHit', 'BattleScript_EffectSelfSpeedDownHit'])

    def test_full_script_assembles_in_both_modes(self):
        # Exercise the real script and repository preprocessor, not the small
        # execution fixture's synthetic hit-tail boundary.
        for portable in (False, True):
            with self.subTest(portable=portable), tempfile.TemporaryDirectory(prefix='rc4-self-drop-full-') as tmp:
                script = ROOT / 'data/battle_scripts_1.s'
                processed = subprocess.run([str(ROOT / 'tools/preproc/preproc'), str(script), 'charmap.txt'], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(processed.returncode, 0, processed.stderr)
                cpp = subprocess.run(['cc', '-E', '-x', 'c', '-iquote', str(ROOT / 'include')] + (['-DPORTABLE=PORTABLE'] if portable else []) + ['-'], input=processed.stdout, capture_output=True, text=True)
                self.assertEqual(cpp.returncode, 0, cpp.stderr)
                processed = subprocess.run([str(ROOT / 'tools/preproc/preproc'), '-ie', str(script), 'charmap.txt'], cwd=ROOT, input=cpp.stdout, capture_output=True, text=True)
                self.assertEqual(processed.returncode, 0, processed.stderr)
                asm = Path(tmp) / 'full.s'
                asm.write_text(processed.stdout)
                result = subprocess.run(['cc', '-c', '-Wa,--defsym,VER_64BIT=1'] + (['-Wa,--defsym,PORTABLE=1'] if portable else []) + [str(asm), '-o', str(Path(tmp) / 'full.o')], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_def_spdef_native_bytecode(self):
        scripts = (ROOT / 'data/battle_scripts_1.s').read_text()
        self.assertTrue('BattleScript_EffectDefSpDefDownHit::' in scripts,
                      'missing native DEF/SPDEF hit entry')
        self.run_native(scripts)

    def test_speed_native_bytecode(self):
        scripts = (ROOT / 'data/battle_scripts_1.s').read_text()
        self.assertTrue('BattleScript_EffectSelfSpeedDownHit::' in scripts,
                        'missing native self SPEED hit entry')
        for protection in range(6):
            with self.subTest(protection=('none', 'mist', 'clear_body', 'both',
                                          'white_smoke', 'mist_white_smoke')[protection]):
                self.run_native(scripts, speed=True, protection=protection)

    def run_native(self, scripts, speed=False, protection=3):
        source = (ROOT / 'src/battle_script_commands.c').read_text()
        # Production entry guards plus production pair dispatch, not a fake stat setter.
        entry = source[source.index('void SetMoveEffect(bool8 primary, u8 certain)'):
                       source.index('    if (gBattleCommunication[MOVE_EFFECT_BYTE] <= PRIMARY_STATUS_MOVE_EFFECT)')]
        case = re.search(r'            case MOVE_EFFECT_DEF_SPDEF_DOWN:.*?break;', source, re.S)
        self.assertIsNotNone(case, 'missing paired effect dispatch')
        assert case is not None
        cases = case[0]
        speed_case = re.search(r'            case MOVE_EFFECT_SELF_SPEED_DOWN:.*?break;', source, re.S)
        self.assertIsNotNone(speed_case, 'missing self Speed dispatch')
        assert speed_case is not None
        cases += speed_case[0]
        cases += re.search(r'            case MOVE_EFFECT_ATK_DEF_DOWN:.*?break;', source, re.S)[0]
        cases += source[source.index('            case MOVE_EFFECT_ATK_MINUS_1:'):source.index('            case MOVE_EFFECT_ATK_PLUS_2:')]
        status_table = re.search(r'static const u32 sStatusFlagsForMoveEffects\[NUM_MOVE_EFFECTS\] =\n\{.*?\n\};', source, re.S)[0]
        guard = source[source.index('        if (gBattleMons[gEffectBattler].status2 & sStatusFlagsForMoveEffects'):source.index('            u8 side;', source.index('        if (gBattleMons[gEffectBattler].status2 & sStatusFlagsForMoveEffects'))]
        dispatch = status_table + '\n' + entry + '\n' + guard + '\n switch (gBattleCommunication[MOVE_EFFECT_BYTE]) {\n' + cases + '\n default: assert(0);\n }\n }\n}\n'
        macros = source[source.index('#define INCREMENT_RESET_RETURN'):source.index('void SetMoveEffect(bool8')]
        stat_defines = source[source.index('#define STAT_CHANGE_WORKED'):source.index('static u8 ChangeStatBuffs(s8 statValue', source.index('#define STAT_CHANGE_WORKED'))]
        support = '\n'.join(line for header in ('include/battle.h', 'include/battle_message.h', 'include/gba/defines.h')
                            for line in (ROOT / header).read_text().splitlines()
                            if re.match(r'#define (GET_STAT_BUFF|SET_STAT_BUFF|STAT_BUFF_NEGATIVE|B_BUFF_(?:STRING |PLACEHOLDER_BEGIN|EOS)|TRUE |FALSE )', line)) + '\n'
        support += next(line for line in source.splitlines() if line.startswith('#define DEFENDER_IS_PROTECTED')) + '\n'
        support += function(source, 'JumpIfMoveAffectedByProtect') + '\n'
        commands = '\n'.join(function(source, n) for n in ['ChangeStatBuffs', 'Cmd_statbuffchange', 'Cmd_setbyte', 'Cmd_jumpifbyte', 'Cmd_goto', 'Cmd_return', 'Cmd_seteffectwithchance'])
        asm = '''#include "constants/global.h"
#include "constants/battle.h"
#include "constants/pokemon.h"
#include "constants/battle_script_commands.h"
#include "constants/battle_anim.h"
#include "constants/battle_string_ids.h"
.include "asm/macros/bit_width.inc"
.include "asm/macros/battle_script.inc"
.set VER_64BIT, 1
#define TRUE 1
#define FALSE 0
#undef cEFFECT_CHOOSER
#undef cMULTISTRING_CHOOSER
#undef sSTATCHANGER
#undef sSTAT_ANIM_PLAYED
.set cEFFECT_CHOOSER, gBattleCommunication + MOVE_EFFECT_BYTE
.set cMULTISTRING_CHOOSER, gBattleCommunication + MULTISTRING_CHOOSER
.set sSTATCHANGER, gBattleScripting + 0x1A
.set sSTAT_ANIM_PLAYED, gBattleScripting + 0x1B
.section .data
'''
        asm += block(scripts, 'BattleScript_EffectDefSpDefDownHit', 'BattleScript_EffectMagicCoat')
        asm += block(scripts, 'BattleScript_DefSpDefDown', 'BattleScript_AtkDefDown')
        asm += block(scripts, 'BattleScript_SelfSpeedDown', 'BattleScript_DefSpDefDown')
        asm += block(scripts, 'BattleScript_AtkDefDown', 'BattleScript_KnockedOff')
        asm += block(scripts, 'BattleScript_StatDown', 'BattleScript_EffectHaze')
        asm += 'BattleScript_EffectHit::\n seteffectwithchance\n end\n'
        with tempfile.TemporaryDirectory(prefix='rc4-self-drop-') as tmp:
            tmp = Path(tmp)
            (tmp / 'seam.raw.s').write_text(asm)
            main = MAIN.replace('TEST_SPEED', '1' if speed else '0').replace('TEST_PROTECTION', str(protection))
            (tmp / 'seam.c').write_text(PRELUDE + support + stat_defines + function(source, 'ChangeStatBuffs') + '\n' + macros + dispatch + '\n' + commands[commands.index('static void Cmd_statbuffchange'): ] + main)
            processed = subprocess.run([str(ROOT / 'tools/preproc/preproc'), str(tmp / 'seam.raw.s'), 'charmap.txt'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(processed.returncode, 0, processed.stderr)
            cpp = subprocess.run(['cc', '-E', '-x', 'c', '-DPORTABLE=PORTABLE', '-iquote', str(ROOT / 'include'), '-'], input=processed.stdout, capture_output=True, text=True)
            self.assertEqual(cpp.returncode, 0, cpp.stderr)
            processed = subprocess.run([str(ROOT / 'tools/preproc/preproc'), '-ie', str(tmp / 'seam.raw.s'), 'charmap.txt'], cwd=ROOT, input=cpp.stdout, capture_output=True, text=True)
            self.assertEqual(processed.returncode, 0, processed.stderr)
            (tmp / 'seam.s').write_text(processed.stdout + '\n.section .note.GNU-stack,"",@progbits\n')
            result = subprocess.run(['cc', '-std=gnu99', '-DPORTABLE', '-iquote', str(ROOT / 'include'), '-I', str(ROOT), '-no-pie', str(tmp / 'seam.c'), str(tmp / 'seam.s'), '-o', str(tmp / 'seam')], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(tmp / 'seam')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


PRELUDE = r'''
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef int8_t s8; typedef uint32_t u32; typedef uint16_t u16;
typedef uint8_t bool8; typedef uint32_t bool32;
#include "constants/global.h"
#include "constants/battle.h"
#include "constants/pokemon.h"
#include "constants/battle_script_commands.h"
#include "constants/battle_string_ids.h"
#include "constants/abilities.h"
#include "constants/moves.h"
#define DSIZE8BIT 1
#define DSIZE16BIT 2
#define DSIZEPTR sizeof(void *)
static u8 *ReadPtr(const u8 *p) { u8 *v; memcpy(&v,p,sizeof(v)); return v; }
#define T1_READ_PTR(p) ReadPtr(p)
#define T2_READ_PTR(p) ReadPtr(p)
#define GET_BATTLER_SIDE(b) ((b)&1)
#define PREPARE_STAT_BUFFER(b,s) do { (b)[0]=(s); } while(0);
u8 gBattleCommunication[8];
struct { u8 pad0[0x10],animArg1,animArg2,pad1[8],statChanger,statAnimPlayed,battler,multihitMoveEffect; } gBattleScripting;
struct { s8 statStages[8]; u8 ability; unsigned hp,status2; } gBattleMons[4];
struct { u8 mistTimer; } gSideTimers[2];
struct { u8 statLowered; } gSpecialStatuses[4];
struct { u8 secondaryEffectChance,flags; } gBattleMoves[65536];
struct { u8 protected; } gProtectStructs[4];
u8 gActiveBattler,gBattlerAttacker,gBattlerTarget,gEffectBattler,gLastUsedAbility,gMoveResultFlags;
u8 gBattleTextBuff1[32],gBattleTextBuff2[32];
u32 gHitMarker,gSideStatuses[2]; unsigned gCurrentMove;
const u8 *gBattlescriptCurrInstr,*stack[16]; int depth;
extern const u8 BattleScript_EffectDefSpDefDownHit[],BattleScript_DefSpDefDown[],BattleScript_AtkDefDown[],BattleScript_StatDown[],BattleScript_EffectSelfSpeedDownHit[],BattleScript_EffectSuperpower[];
extern const u8 BattleScript_SelfSpeedDown[];
const u8 BattleScript_MistProtected[1]={0},BattleScript_ButItFailed[1]={0},BattleScript_AbilityNoStatLoss[1]={0},BattleScript_AbilityNoSpecificStatLoss[1]={0};
const unsigned short gStatDownStringIds[4]={0};
static void BattleScriptPush(const u8 *p) { assert(depth<16); stack[depth++]=p; }
static void BattleScriptPop(void) { assert(depth); gBattlescriptCurrInstr=stack[--depth]; }
/* The outer hit interpreter owns this branch. Only its miss/protect flags
   are under test here; this callback does not change stats or hit results. */
static void JumpIfMoveFailed(unsigned size,u16 move) { (void)size;(void)move; }
static void RecordAbilityBattle(u8 b,u8 a) { (void)b;(void)a; }
static unsigned Random(void) { return 99; }
'''
MAIN = r'''
static void execute(void) {
 int steps=0;
 while (++steps<100) {
  switch (*gBattlescriptCurrInstr) {
   case B_SCR_OP_SETBYTE: Cmd_setbyte(); break;
   case B_SCR_OP_GOTO: Cmd_goto(); break;
   case B_SCR_OP_JUMPIFBYTE: Cmd_jumpifbyte(); break;
   case B_SCR_OP_STATBUFFCHANGE: Cmd_statbuffchange(); break;
   case B_SCR_OP_RETURN: Cmd_return(); break;
   case B_SCR_OP_SETEFFECTWITHCHANCE: Cmd_seteffectwithchance(); break;
   /* UI-only commands: no battle state mutations are replaced. */
   case B_SCR_OP_PLAYSTATCHANGEANIMATION: gBattlescriptCurrInstr+=4; break;
   case B_SCR_OP_PLAYANIMATION: gBattlescriptCurrInstr+=3+sizeof(void*); break;
   case B_SCR_OP_PRINTFROMTABLE: gBattlescriptCurrInstr+=1+sizeof(void*); break;
   case B_SCR_OP_WAITMESSAGE: gBattlescriptCurrInstr+=3; break;
   case B_SCR_OP_END: assert(depth==0); return;
   default: assert(!"unexpected opcode");
  }
 }
 assert(!"script did not terminate");
}
int main(void) {
 for(int vanilla=0;vanilla<2;vanilla++) {
 int first=vanilla?STAT_ATK:TEST_SPEED?STAT_SPEED:STAT_DEF;
 int second=vanilla?STAT_DEF:TEST_SPEED?STAT_SPEED:STAT_SPDEF;
 for (int floor=0;floor<4;floor++) for (int flags=0;flags<5;flags++)
 for(int faint=0;faint<2;faint++) for(int substitute=0;substitute<2;substitute++) {
  memset(gBattleMons,0,sizeof(gBattleMons));
  memset(gBattleCommunication,0,sizeof(gBattleCommunication));
  for(int b=0;b<2;b++) for(int s=0;s<8;s++) gBattleMons[b].statStages[s]=6;
  gBattlerAttacker=0;gBattlerTarget=1;gBattleMons[0].hp=100;gBattleMons[1].hp=faint?0:100;
  gBattleMons[0].ability=TEST_PROTECTION>=4?ABILITY_WHITE_SMOKE:TEST_PROTECTION>=2?ABILITY_CLEAR_BODY:ABILITY_NONE;gBattleMons[1].ability=ABILITY_CLEAR_BODY;
  gSideTimers[0].mistTimer=(TEST_PROTECTION&1)?5:0;gSideTimers[1].mistTimer=5;
  gBattleMons[0].status2=gBattleMons[1].status2=substitute?STATUS2_SUBSTITUTE:0;
  gBattleMons[0].statStages[first]=(floor&1)?0:6;
  if(second!=first) gBattleMons[0].statStages[second]=(floor&2)?0:6;
  gMoveResultFlags=flags==1?MOVE_RESULT_MISSED:flags==2?MOVE_RESULT_DOESNT_AFFECT_FOE:flags==3?MOVE_RESULT_FAILED:0;
  gProtectStructs[1].protected=flags==4;
  gBattleMoves[gCurrentMove].flags=FLAG_PROTECT_AFFECTED;
  if(flags==4) {
   assert(JumpIfMoveAffectedByProtect(gCurrentMove));
   assert(gBattleCommunication[MISS_TYPE]==B_MSG_PROTECTED);
  }
  depth=0;gBattlescriptCurrInstr=vanilla?BattleScript_EffectSuperpower:TEST_SPEED?BattleScript_EffectSelfSpeedDownHit:BattleScript_EffectDefSpDefDownHit;execute();
  for(int s=0;s<8;s++) {
   int before=(s==first&&(floor&1))||(second!=first&&s==second&&(floor&2))?0:6;
   int expected=before-(!flags&&before&&(s==first||s==second));
   if(gBattleMons[0].statStages[s]!=expected) fprintf(stderr,"floor=%d flags=%d faint=%d substitute=%d stat=%d actual=%d expected=%d changer=%u\\n",floor,flags,faint,substitute,s,gBattleMons[0].statStages[s],expected,gBattleScripting.statChanger);
   assert(gBattleMons[0].statStages[s]==expected);
   assert(gBattleMons[1].statStages[s]==6);
  }
 }
 }
 /* Legacy generic Speed secondaries must keep their original prevention,
    even when Cmd_seteffectwithchance receives CERTAIN. */
 for(int user=0;user<2;user++) for(int protection=0;protection<6;protection++) {
  const u8 legacy[]={B_SCR_OP_SETEFFECTWITHCHANCE,B_SCR_OP_END};
  memset(gBattleMons,0,sizeof(gBattleMons));
  memset(gBattleCommunication,0,sizeof(gBattleCommunication));
  memset(gSideTimers,0,sizeof(gSideTimers));
  memset(gProtectStructs,0,sizeof(gProtectStructs));
  for(int b=0;b<2;b++) {
   gBattleMons[b].hp=100;
   for(int s=0;s<8;s++) gBattleMons[b].statStages[s]=6;
  }
  int battler=user?0:1;
  gBattleMons[battler].ability=protection>=4?ABILITY_WHITE_SMOKE:protection>=2?ABILITY_CLEAR_BODY:ABILITY_NONE;
  gSideTimers[battler].mistTimer=(protection&1)?5:0;
  gMoveResultFlags=0;depth=0;
  gBattleCommunication[MOVE_EFFECT_BYTE]=MOVE_EFFECT_SPD_MINUS_1|MOVE_EFFECT_CERTAIN|(user?MOVE_EFFECT_AFFECTS_USER:0);
  gBattlescriptCurrInstr=legacy;execute();
  for(int b=0;b<2;b++) for(int s=0;s<8;s++)
   assert(gBattleMons[b].statStages[s]==6-(!protection&&b==battler&&s==STAT_SPEED));
 }
 return 0;
}
'''

if __name__ == '__main__':
    unittest.main()
