"""Roadmap 22 production-C seams, deferred to the integrated RC test pass.

Run with: python3 -m unittest discover -s test/world -p test_private_boss_credit.py
No game, save fixture, SDL session, or network is needed.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def function(path, signature):
    text = (ROOT / path).read_text()
    start = text.index(signature + '\n{')
    return text[start:text.index('\n}\n', start) + 3]


class PrivateBossCredit(unittest.TestCase):
    def run_c(self, source):
        with tempfile.TemporaryDirectory(prefix='emerald-private-boss-') as directory:
            path = Path(directory) / 'case.c'
            binary = Path(directory) / 'case'
            path.write_text(source)
            compiled = subprocess.run(
                ['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(path), '-o', str(binary)],
                capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_boss_classes_cover_every_gym_team_and_league_member(self):
        # Resolve the real data rather than inventing boss IDs for the seam.
        data = (ROOT / 'src/data/trainers.h').read_text()
        entries = dict(re.findall(
            r'\[(TRAINER_\w+)\]\s*=\s*\{\s*\.trainerClass\s*=\s*(TRAINER_CLASS_\w+)', data))
        gyms = ('ROXANNE', 'BRAWLY', 'WATTSON', 'FLANNERY', 'NORMAN',
                'WINONA', 'TATE_AND_LIZA', 'JUAN')
        for gym in gyms:
            for team in range(1, 6):
                self.assertEqual(entries[f'TRAINER_{gym}_{team}'], 'TRAINER_CLASS_LEADER')
        for member in ('SIDNEY', 'PHOEBE', 'GLACIA', 'DRAKE'):
            self.assertEqual(entries[f'TRAINER_{member}'], 'TRAINER_CLASS_ELITE_FOUR')
        self.assertEqual(entries['TRAINER_WALLACE'], 'TRAINER_CLASS_CHAMPION')

        # Include every real trainer class, so ordinary trainers/rematch teams
        # cannot accidentally be blanket-denied by a future classifier edit.
        setup = function('src/battle_setup.c',
                         'bool8 BattleSetup_CanShareWorldTrainerCredit(u16 trainerId)')
        constants = (ROOT / 'include/constants/trainers.h').read_text()
        classes = dict(re.findall(r'^#define (TRAINER_CLASS_\w+)\s+(0x[0-9a-fA-F]+|\d+)',
                                  constants, re.M))
        rows = list(entries.items())
        expected = [0 if cls in ('TRAINER_CLASS_LEADER', 'TRAINER_CLASS_ELITE_FOUR',
                                'TRAINER_CLASS_CHAMPION') else 1 for _, cls in rows]
        self.run_c('''
#include <assert.h>
#include <stdint.h>
typedef uint8_t bool8;
typedef uint16_t u16;
#define TRUE 1
#define FALSE 0
#define TRAINER_NONE 0
''' + '\n'.join(f'#define {name} {value}' for name, value in classes.items()) +
                   f'\n#define TRAINERS_COUNT {len(rows) + 1}\n' + '''
struct Trainer { unsigned trainerClass; };
static const struct Trainer gTrainers[TRAINERS_COUNT] = {
''' + ',\n'.join('{ ' + cls + ' }' for cls in ['0'] + [cls for _, cls in rows]) + '''
};
''' + setup + '''
int main(void) {
    const int expected[] = {0, ''' + ', '.join(map(str, expected)) + '''};
    for (u16 id = 0; id < TRAINERS_COUNT; id++)
        assert(BattleSetup_CanShareWorldTrainerCredit(id) == expected[id]);
    assert(!BattleSetup_CanShareWorldTrainerCredit(TRAINERS_COUNT));
    assert(!BattleSetup_CanShareWorldTrainerCredit(65535));
    return 0;
}
''')

    def test_guest_boundary_preserves_owner_and_ordinary_encounter_credit(self):
        classifier = function('src/battle_setup.c',
                              'bool8 BattleSetup_CanShareWorldTrainerCredit(u16 trainerId)')
        production = function('src/platform/world_activity.c',
                              'void WorldActivity_ReturnFromCoopWildBattle(void)')
        self.run_c('''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t bool8;
typedef uint16_t u16;
typedef void (*MainCallback)(void);
#define TRUE 1
#define FALSE 0
#define B_OUTCOME_WON 1
#define RETURNING 6
#define TRAINER_NONE 0
#define TRAINERS_COUNT 7
#define TRAINER_CLASS_LEADER 1
#define TRAINER_CLASS_ELITE_FOUR 2
#define TRAINER_CLASS_CHAMPION 3
static const struct { unsigned trainerClass; } gTrainers[] = {
    {0}, {TRAINER_CLASS_LEADER}, {TRAINER_CLASS_ELITE_FOUR},
    {TRAINER_CLASS_CHAMPION}, {0}, {0}, {TRAINER_CLASS_LEADER}
};
static struct { MainCallback trainerCallback; int locked, encounterPending,
    wildCaptured, trainerCaptured, state; const char *status; } sActivity;
static int trainer, trainerId, continuation, resumed, registered, flagged;
static int ownerCalled, ended, resets, unlocks, unfreezes;
static u16 creditedId;
static int gBattleOutcome, gFieldLinkPlayerCount;
static int WorldCoop_IsTrainer(void) { return trainer; }
static u16 WorldCoop_TrainerId(void) { return trainerId; }
static void WorldCoop_Abort(void) { trainer = 0; trainerId = 0; }
static void CloseMenu(void) {}
static void CloseLink(void) {}
static void NativeLink_Abort(void) {}
static void CB1_Overworld(void) {}
static void SetMainCallback1(MainCallback callback) { (void)callback; }
static int BattleSetup_ResumeWorldTrainerScript(u16 id) {
    assert(id == creditedId); resumed++; return continuation;
}
static void BattleSetup_RegisterWorldTrainerInMatchCall(u16 id) {
    assert(id == creditedId); registered++;
}
static void SetTrainerFlag(u16 id) { assert(id == creditedId); flagged++; }
static void ScriptContext_Init(void) { resets++; }
static void UnlockPlayerFieldControls(void) { unlocks++; }
static void UnfreezeObjectEvents(void) { unfreezes++; }
static void BattleSetup_EndWorldWildBattle(void) { ended++; }
static void OwnerResult(void) { ownerCalled++; }
''' + classifier + production + '''
int main(void) {
    for (int owner = 0; owner <= 1; owner++)
    for (int isTrainer = 0; isTrainer <= 1; isTrainer++)
    for (int id = 0; id <= TRAINERS_COUNT; id++)
    for (int won = 0; won <= 1; won++)
    for (int script = 0; script <= 1; script++) {
        memset(&sActivity, 0, sizeof(sActivity));
        trainer = isTrainer; trainerId = id; creditedId = id;
        continuation = script; gBattleOutcome = won;
        resumed = registered = flagged = ownerCalled = ended = 0;
        resets = unlocks = unfreezes = 0;
        sActivity.trainerCallback = owner ? OwnerResult : 0;
        sActivity.locked = sActivity.encounterPending = 1;
        sActivity.wildCaptured = sActivity.trainerCaptured = 1;
        int share = !owner && isTrainer && won
            && BattleSetup_CanShareWorldTrainerCredit(id);
        WorldActivity_ReturnFromCoopWildBattle();
        assert(ownerCalled == owner);
        assert(resumed == share);
        assert(registered == (share && !script));
        assert(flagged == (share && !script));
        assert(ended == (!owner && !(share && script)));
        assert(resets == ended && unlocks == ended && unfreezes == ended);
        assert(!sActivity.trainerCallback && !sActivity.locked);
        assert(!sActivity.encounterPending && !sActivity.wildCaptured);
        assert(!sActivity.trainerCaptured && sActivity.state == RETURNING);
    }
    return 0;
}
''')

    def test_direct_guest_entry_points_reject_before_any_progression(self):
        # Defense in depth for direct callers, not only the activity wrapper.
        resume = function('src/battle_setup.c',
                          'bool8 BattleSetup_ResumeWorldTrainerScript(u16 trainerId)')
        register = function('src/battle_setup.c',
                            'void BattleSetup_RegisterWorldTrainerInMatchCall(u16 trainerId)')
        self.assertLess(resume.index('!BattleSetup_CanShareWorldTrainerCredit(trainerId)'),
                        resume.index('HasTrainerBeenFought(trainerId)'))
        self.assertLess(register.index('BattleSetup_CanShareWorldTrainerCredit(trainerId)'),
                        register.index('FlagGet('))


if __name__ == '__main__':
    unittest.main(verbosity=2)
