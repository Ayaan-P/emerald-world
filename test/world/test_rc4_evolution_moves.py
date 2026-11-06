"""Compile the actual evolution learner seam; this is not a gameplay proof.

Only data access is a boundary double. The production GiveMoveTo(Box)Mon,
learner and wrapper execute as C against the frozen staged Torterra table.
"""
from pathlib import Path
import json
import re
import shutil
import subprocess
import unittest

from test.world.test_expanded_runtime import function

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/rc4-evolution-moves'
STAGED = ROOT / 'build/rc4-acquisition-coverage/test55/generated'


class EvolutionMovesTest(unittest.TestCase):
    def run_c(self, body, portable=True):
        OUT.mkdir(parents=True, exist_ok=True)
        production = (ROOT / 'src/pokemon.c').read_text()
        staged = (STAGED / 'src/data/pokemon/expanded/learnsets.inc').read_text()
        match = re.search(r'static const u16 sExpandedTorterraLevelUpLearnset\[\] = \{.*?\n\};', staged, re.S)
        self.assertIsNotNone(match)
        assert match is not None
        table = match.group()
        self.assertIn('LEVEL_UP_MOVE(0, MOVE_EARTHQUAKE)', table)
        source = '''#include "global.h"
#include "pokemon.h"
#include "constants/moves.h"
#include "platform/expanded_species.h"
#undef NDEBUG
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define LEVEL_UP_MOVE(l, m) (((l) << 9) | (m))
static u8 sLearningMoveTableID;
u16 gMoveToLearn;
const struct BattleMove gBattleMoves[MOVES_COUNT] = {
    [MOVE_EARTHQUAKE] = {.pp=10}, [MOVE_LEECH_SEED] = {.pp=10}, [MOVE_BITE] = {.pp=25}
};
struct Fixture { struct Pokemon mon; u16 species; u16 moves[4]; u8 pp[4]; };
static struct Fixture fixtures[2];
static struct Fixture *findMon(const void *p) {
    for (unsigned i = 0; i < 2; i++) if (p == &fixtures[i].mon) return &fixtures[i];
    assert(0); return NULL;
}
u32 GetMonData(struct Pokemon *mon, s32 field, u8 *unused) {
    if (field == MON_DATA_NICKNAME) { unused[0] = 0; return 0; }
    if (field == MON_DATA_SPECIES) return findMon(mon)->species;
    if (field == MON_DATA_LEVEL) return mon->level;
    assert(0); return 0;
}
u32 GetBoxMonData(struct BoxPokemon *mon, s32 field, u8 *unused) {
    (void)unused; assert(field >= MON_DATA_MOVE1 && field <= MON_DATA_MOVE4);
    return findMon(mon)->moves[field - MON_DATA_MOVE1];
}
void SetBoxMonData(struct BoxPokemon *mon, s32 field, const void *value) {
    struct Fixture *f = findMon(mon);
    if (field >= MON_DATA_MOVE1 && field <= MON_DATA_MOVE4)
        f->moves[field - MON_DATA_MOVE1] = *(const u16 *)value;
    else { assert(field >= MON_DATA_PP1 && field <= MON_DATA_PP4);
        f->pp[field - MON_DATA_PP1] = *(const u8 *)value; }
}
static bool8 playable = TRUE, mapped = TRUE;
bool8 ExpandedSpecies_IsPlayable(u16 species) { return playable && species == SPECIES_TORTERRA; }
u16 ExpandedSpecies_NationalDexNumber(u16 species) { return mapped && species == SPECIES_TORTERRA ? 389 : 0; }
static u16 GiveMoveToBoxMon(struct BoxPokemon *, u16);
'''
        source += table + '\n'
        source += '''#define gLevelUpLearnsets testLevelUpLearnsets
static const u16 *gLevelUpLearnsets[NUM_SPECIES + 2000];
static void setup(void) {
    memset(fixtures, 0, sizeof(fixtures));
    for (int i = 0; i < 2; i++) {
        fixtures[i].species = SPECIES_TORTERRA;
        fixtures[i].mon.level = 32;
    }
    gLevelUpLearnsets[SPECIES_TORTERRA] = sExpandedTorterraLevelUpLearnset;
}
'''
        for name in ('GiveMoveToBoxMon', 'GiveMoveToMon', 'MonTryLearningNewMove'):
            source += function(production, name) + '\n'
        if portable and re.search(r'^u16 MonTryLearningEvolutionMove\(', production, re.M):
            source += function(production, 'MonTryLearningEvolutionMove') + '\n'
        else:
            # RED executes the pre-fix production path, not a missing-symbol error.
            source += '#define MonTryLearningEvolutionMove MonTryLearningNewMove\n'
        scene = (ROOT / 'src/evolution_scene.c').read_text()
        if not portable:
            # Host headers still need PORTABLE; compile the actual nonportable
            # scene selector branches, not a GBA cross-build.
            source += '#undef PORTABLE\n'
        source += '\n'.join(re.findall(r'enum \{.*?\n\};', scene, re.S)) + '\n'
        source += '''#define IsTextPrinterActive(...) 0
#define IsSEPlaying() 0
#define IsFanfareTaskInactive() TRUE
#define StopMapMusic() ((void)0)
#define Overworld_PlaySpecialMapMusic() ((void)0)
#define StringCopy_Nickname(...) ((void)0)
#define BeginNormalPaletteFade(...) ((void)0)
#define PlayBGM(...) ((void)0)
#define DrawTextOnTradeWindow(...) ((void)0)
#define BattleStringExpandPlaceholdersToDisplayedString(...) ((void)0)
#define BattlePutTextOnWindow(...) ((void)0)
#define TASK_BIT_LEARN_MOVE (1 << 7)
struct {
    bool8 tEvoWasStopped, tLearnsFirstMove;
    u16 tState, tBits, tLearnMoveState, tLearnMoveYesState, tLearnMoveNoState;
} fixtureTasks[1];
#define gTasks fixtureTasks
'''
        for prefix, name in (('', 'normalScene'), ('T_', 'tradeScene')):
            part = scene.split('case ' + prefix + 'EVOSTATE_TRY_LEARN_MOVE:')[1]
            selection = part.split('        {', 1)[1].split('            if (var != MOVE_NONE', 1)[0]
            source += 'static u16 ' + name + '''(struct Pokemon *mon, bool8 stopped, bool8 first) {
    u16 var; u8 taskId = 0;
    gTasks[0].tEvoWasStopped = stopped;
    gTasks[0].tLearnsFirstMove = first;
''' + selection + '\nreturn var; }\n'
            # Execute the exact TRY return-code/firstMove routing, plus native
            # cancel/retry subcases. Rendering/audio are explicit no-op boundaries.
            maincase = part.split('    case ' + prefix + 'EVOSTATE_END:', 1)[0]
            source += 'static void ' + name + 'Step(struct Pokemon *mon) { u16 var; u8 taskId = 0;\nswitch(gTasks[0].tState) {\ncase ' + prefix + 'EVOSTATE_TRY_LEARN_MOVE:' + maincase + '\n} }\n'
            source += 'static void ' + name + 'Retry(void) { u8 taskId = 0; switch(gTasks[0].tLearnMoveState) {\n'
            for state in ('ASK_CANCEL', 'CANCEL', 'RETRY_AFTER_HM'):
                token = prefix + 'MVSTATE_' + state
                case = scene.split('        case ' + token + ':', 1)[1].split('            break;', 1)[0]
                source += 'case ' + token + ':' + case + '\nbreak;\n'
            source += '} }\n'
        source += 'int main(void) { setup(); (void)normalScene; (void)tradeScene; (void)normalSceneStep; (void)tradeSceneStep; (void)normalSceneRetry; (void)tradeSceneRetry;\n' + body + '\nputs("production evolution learner C assertions PASS"); return 0; }\n'
        compilers = [c for c in ('gcc', 'clang') if shutil.which(c)]
        self.assertIn('gcc', compilers)
        for compiler in compilers:
            stem = OUT / (self._testMethodName + '-' + compiler)
            cfile, exe = stem.with_suffix('.c'), stem.with_suffix('.exe')
            cfile.write_text(source)
            command = [compiler, '-std=gnu11', '-DVER_64BIT', '-DUBFIX', '-DMODERN=1',
                       '-include', str(STAGED / 'include/constants/expanded_species.h'),
                       '-include', str(ROOT / 'build/rc4-self-drop-move-catalog/generated/include/constants/moves.h'),
                       '-iquote', str(ROOT / 'include'), '-fno-builtin', '-Wall', '-Wextra', '-Werror',
                       str(cfile), '-o', str(exe)]
            command.insert(2, '-DPORTABLE')
            stem.with_suffix('.command.json').write_text(json.dumps(command, indent=2))
            result = subprocess.run(command, text=True, capture_output=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], text=True, capture_output=True, cwd=OUT)
            stem.with_suffix('.log').write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(compiler + ': ' + self._testMethodName + ': ' + result.stdout.strip())

    def test_actual_torterra_full_moveset_offers_without_injection(self):
        self.run_c('''struct Pokemon *mon = &fixtures[0].mon;
for (int i = 0; i < 4; i++) fixtures[0].moves[i] = MOVE_TACKLE + i;
struct Fixture before = fixtures[0];
memset(gTasks, 0, sizeof(gTasks));
gTasks[0].tState = EVOSTATE_TRY_LEARN_MOVE;
gTasks[0].tLearnsFirstMove = TRUE;
normalSceneStep(mon);
assert(gMoveToLearn == MOVE_EARTHQUAKE);
assert(gTasks[0].tState == EVOSTATE_REPLACE_MOVE);
assert(gTasks[0].tLearnsFirstMove == FALSE);
assert(memcmp(&before, &fixtures[0], sizeof(before)) == 0);
gTasks[0].tLearnMoveState = MVSTATE_CANCEL;
normalSceneRetry(); normalSceneStep(mon);
assert(gTasks[0].tState == EVOSTATE_END);
assert(memcmp(&before, &fixtures[0], sizeof(before)) == 0);
''')

    def test_native_return_codes_fullslot_retry_and_decline_progress(self):
        body = '''static const u16 moves[] = {
    LEVEL_UP_MOVE(0, MOVE_EARTHQUAKE), LEVEL_UP_MOVE(0, MOVE_BITE),
    LEVEL_UP_MOVE(32, MOVE_LEECH_SEED), LEVEL_UP_END
};
struct Pokemon *mon = &fixtures[0].mon;
'''
        for prefix, name in (('', 'normalScene'), ('T_', 'tradeScene')):
            body += f'''setup();
gLevelUpLearnsets[SPECIES_TORTERRA] = moves;
fixtures[0].moves[0] = MOVE_EARTHQUAKE;
for (int i = 1; i < 4; i++) fixtures[0].moves[i] = MOVE_TACKLE + i;
struct Fixture before_{name} = fixtures[0];
memset(gTasks, 0, sizeof(gTasks));
gTasks[0].tState = {prefix}EVOSTATE_TRY_LEARN_MOVE;
gTasks[0].tLearnsFirstMove = TRUE;
{name}Step(mon);
assert(gTasks[0].tState == {prefix}EVOSTATE_TRY_LEARN_MOVE);
assert(gTasks[0].tLearnsFirstMove == FALSE); // ALREADY_KNOWS progresses
{name}Step(mon);
assert(gTasks[0].tState == {prefix}EVOSTATE_REPLACE_MOVE);
assert(gMoveToLearn == MOVE_BITE);
assert(gTasks[0].tLearnsFirstMove == FALSE);
for (int retry = 0; retry < 3; retry++) {{
    // Native HM retry and declined summary/stop-learning question retain offer.
    gTasks[0].tLearnMoveState = {prefix}MVSTATE_RETRY_AFTER_HM;
    {name}Retry();
    assert(gTasks[0].tLearnMoveState == {prefix}MVSTATE_SHOW_MOVE_SELECT);
    gTasks[0].tLearnMoveState = {prefix}MVSTATE_ASK_CANCEL;
    {name}Retry();
    assert(gTasks[0].tLearnMoveYesState == {prefix}MVSTATE_CANCEL);
    assert(gTasks[0].tLearnMoveNoState == {prefix}MVSTATE_INTRO_MSG_1);
    assert(gTasks[0].tLearnMoveState == {prefix}MVSTATE_PRINT_YES_NO);
    assert(gMoveToLearn == MOVE_BITE);
    assert(memcmp(&fixtures[0], &before_{name}, sizeof(fixtures[0])) == 0);
}}
// Native confirmed stop-learning returns to TRY with firstMove still FALSE.
gTasks[0].tLearnMoveState = {prefix}MVSTATE_CANCEL;
{name}Retry();
assert(gTasks[0].tState == {prefix}EVOSTATE_TRY_LEARN_MOVE);
{name}Step(mon);
assert(gTasks[0].tState == {prefix}EVOSTATE_REPLACE_MOVE);
assert(gMoveToLearn == MOVE_LEECH_SEED);
gTasks[0].tLearnMoveState = {prefix}MVSTATE_CANCEL;
{name}Retry(); {name}Step(mon);
assert(gTasks[0].tState == {prefix}EVOSTATE_END);
assert(memcmp(&fixtures[0], &before_{name}, sizeof(fixtures[0])) == 0);
'''
        self.run_c(body)

    def test_multiple_zero_then_same_level_known_and_new_mon_reset(self):
        self.run_c('''static const u16 moves[] = {
    LEVEL_UP_MOVE(0, MOVE_EARTHQUAKE), LEVEL_UP_MOVE(1, MOVE_TACKLE),
    LEVEL_UP_MOVE(0, MOVE_BITE), LEVEL_UP_MOVE(32, MOVE_LEECH_SEED), LEVEL_UP_END
};
gLevelUpLearnsets[SPECIES_TORTERRA] = moves;
struct Pokemon *a = &fixtures[0].mon, *b = &fixtures[1].mon;
// Known zero rows return the native sentinel and progress, not terminate.
fixtures[0].moves[0] = MOVE_EARTHQUAKE;
assert(tradeScene(a, FALSE, TRUE) == MON_ALREADY_KNOWS_MOVE);
assert(tradeScene(a, FALSE, FALSE) == MOVE_BITE);
assert(tradeScene(a, FALSE, FALSE) == MOVE_LEECH_SEED);
assert(tradeScene(a, FALSE, FALSE) == MOVE_NONE);
assert(fixtures[0].moves[1] == MOVE_BITE && fixtures[0].pp[1] == 25);
// Private state must not leak between Pokemon even absent the caller reset.
assert(tradeScene(b, FALSE, FALSE) == MOVE_EARTHQUAKE);
assert(tradeScene(b, FALSE, FALSE) == MOVE_BITE);
assert(tradeScene(b, FALSE, FALSE) == MOVE_LEECH_SEED);
assert(tradeScene(b, FALSE, FALSE) == MOVE_NONE);
// Same address on a fresh scene also resets (including aborted partial phases).
assert(tradeScene(b, FALSE, TRUE) == MON_ALREADY_KNOWS_MOVE);
assert(tradeScene(b, FALSE, FALSE) == MON_ALREADY_KNOWS_MOVE);
assert(tradeScene(b, FALSE, FALSE) == MON_ALREADY_KNOWS_MOVE);
assert(tradeScene(b, FALSE, FALSE) == MOVE_NONE);
// Normal battle/level-up callers retain their original path: no level-0 offer.
setup(); fixtures[0].mon.level = 32;
gLevelUpLearnsets[SPECIES_TORTERRA] = moves;
assert(MonTryLearningNewMove(a, TRUE) == MOVE_LEECH_SEED);
assert(fixtures[0].moves[0] == MOVE_LEECH_SEED);
''')

    def test_legacy_unplayable_unmapped_delegate_unchanged(self):
        self.run_c('''static const u16 moves[] = {
    LEVEL_UP_MOVE(0, MOVE_EARTHQUAKE), LEVEL_UP_MOVE(32, MOVE_BITE),
    LEVEL_UP_MOVE(32, MOVE_LEECH_SEED), LEVEL_UP_END
};
struct Pokemon *a = &fixtures[0].mon, *b = &fixtures[1].mon;
for (int mode = 0; mode < 3; mode++) {
    setup();
    u16 species = mode == 0 ? SPECIES_IVYSAUR : SPECIES_TORTERRA;
    fixtures[0].species = fixtures[1].species = species;
    playable = mode != 1; mapped = mode != 2;
    gLevelUpLearnsets[species] = moves;
    assert(MonTryLearningEvolutionMove(a, TRUE) == MonTryLearningNewMove(b, TRUE));
    // The original has one shared cursor; reinitialize it to compare the traces.
    assert(MonTryLearningNewMove(b, TRUE) == MON_ALREADY_KNOWS_MOVE);
    assert(MonTryLearningEvolutionMove(a, FALSE) == MOVE_LEECH_SEED);
    assert(MonTryLearningEvolutionMove(a, FALSE) == MOVE_NONE);
    assert(fixtures[0].moves[0] == MOVE_BITE);
    assert(fixtures[0].moves[1] == MOVE_LEECH_SEED);
}
_Static_assert(sizeof(struct BoxPokemon) == 80, "unchanged box ABI");
_Static_assert(sizeof(struct Pokemon) == 100, "unchanged party ABI");
''')

    def test_nonportable_scene_keeps_original_path(self):
        self.run_c('''struct Pokemon *mon = &fixtures[0].mon;
assert(normalScene(mon, FALSE, TRUE) == MOVE_NONE);
assert(tradeScene(mon, FALSE, TRUE) == MOVE_NONE);
fixtures[0].mon.level = 33;
assert(normalScene(mon, FALSE, TRUE) == MOVE_LEECH_SEED);
''', portable=False)

    def test_scene_ui_and_original_learner_are_not_rewritten(self):
        scene = (ROOT / 'src/evolution_scene.c').read_text()
        baseline = subprocess.check_output(['git', 'show', 'HEAD:src/evolution_scene.c'], cwd=ROOT, text=True)
        selection = '''#ifdef PORTABLE
            if (!gTasks[taskId].tEvoWasStopped)
                var = MonTryLearningEvolutionMove(mon, gTasks[taskId].tLearnsFirstMove);
            else
#endif
                var = MonTryLearningNewMove(mon, gTasks[taskId].tLearnsFirstMove);'''
        self.assertEqual(scene.count(selection), 2)
        self.assertEqual(scene.replace(selection, '            var = MonTryLearningNewMove(mon, gTasks[taskId].tLearnsFirstMove);'), baseline)
        production = (ROOT / 'src/pokemon.c').read_text()
        baseline = subprocess.check_output(['git', 'show', 'HEAD:src/pokemon.c'], cwd=ROOT, text=True)
        for name in ('MonTryLearningNewMove', 'GiveMoveToMon', 'GiveMoveToBoxMon', 'SetMonMoveSlot', 'RemoveMonPPBonus', 'CalculateBoxMonChecksum'):
            self.assertEqual(function(production, name), function(baseline, name), name)
        self.assertIn('#ifdef PORTABLE\n// Evolution-only offers', production)
        self.assertIn('}\n#endif\n\nvoid DeleteFirstMoveAndGiveMoveToMon', production)

    def test_declined_duplicate_zero_is_not_offered_again(self):
        self.run_c('''static const u16 repeated[] = {
    LEVEL_UP_MOVE(0, MOVE_EARTHQUAKE), LEVEL_UP_MOVE(0, MOVE_EARTHQUAKE),
    LEVEL_UP_MOVE(0, MOVE_BITE), LEVEL_UP_MOVE(32, MOVE_LEECH_SEED), LEVEL_UP_END
};
struct Pokemon *mon = &fixtures[0].mon;
gLevelUpLearnsets[SPECIES_TORTERRA] = repeated;
for (int i = 0; i < 4; i++) fixtures[0].moves[i] = MOVE_TACKLE + i;
assert(normalScene(mon, FALSE, TRUE) == MON_HAS_MAX_MOVES);
assert(gMoveToLearn == MOVE_EARTHQUAKE);
// The native UI retains this pending offer during YES/NO/summary retries.
// Its final decline re-enters TRY_LEARN_MOVE with firstMove FALSE.
assert(normalScene(mon, FALSE, FALSE) == MON_HAS_MAX_MOVES);
assert(gMoveToLearn == MOVE_BITE);
assert(normalScene(mon, FALSE, FALSE) == MON_HAS_MAX_MOVES);
assert(gMoveToLearn == MOVE_LEECH_SEED);
assert(normalScene(mon, FALSE, FALSE) == MOVE_NONE);
assert(normalScene(mon, FALSE, FALSE) == MOVE_NONE);
''')

    def test_successful_normal_trade_and_cancelled_scene_selection(self):
        self.run_c('''struct Pokemon *mon = &fixtures[0].mon;
assert(normalScene(mon, FALSE, TRUE) == MOVE_EARTHQUAKE);
setup();
assert(tradeScene(mon, FALSE, TRUE) == MOVE_EARTHQUAKE);
setup();
assert(normalScene(mon, TRUE, TRUE) == MOVE_NONE);
assert(fixtures[0].moves[0] == MOVE_NONE);
assert(tradeScene(mon, TRUE, TRUE) == MOVE_NONE);
// Cancellation still runs the original current-level path (level 33).
fixtures[0].mon.level = 33;
assert(normalScene(mon, TRUE, TRUE) == MOVE_LEECH_SEED);
assert(fixtures[0].moves[0] == MOVE_LEECH_SEED);
setup(); fixtures[0].mon.level = 33;
assert(tradeScene(mon, TRUE, TRUE) == MOVE_LEECH_SEED);
assert(fixtures[0].moves[0] == MOVE_LEECH_SEED);
''')

    def test_staged_torterra_earthquake_zero_at_evolution_32(self):
        self.run_c('''struct Pokemon *mon = &fixtures[0].mon;
u16 result = MonTryLearningEvolutionMove(mon, TRUE);
printf("Torterra32 result=%u Earthquake=%u moveToLearn=%u\\n", result, MOVE_EARTHQUAKE, gMoveToLearn);
fflush(stdout);
assert(result == MOVE_EARTHQUAKE);
assert(gMoveToLearn == MOVE_EARTHQUAKE);
assert(fixtures[0].moves[0] == MOVE_EARTHQUAKE && fixtures[0].pp[0] == 10);
assert(MonTryLearningEvolutionMove(mon, FALSE) == MOVE_NONE);
''')


if __name__ == '__main__':
    unittest.main()
