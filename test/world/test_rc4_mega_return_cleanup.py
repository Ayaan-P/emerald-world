"""Compile the real common return and Mega reset, without running a game.

The receiving controller bypasses BattleMain's normal cleanup. Seed its observed
private form/used state directly, not a fictitious authoritative gBattleMons.
Only unrelated field/link boundaries are stubbed. Native pair acceptance remains
separate from this lifecycle regression.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include "src/platform/world_activity.c"
#include "src/platform/mega_game.c"
#include "src/platform/mega_battle.c"

struct Pokemon gPlayerParty[PARTY_SIZE], gEnemyParty[PARTY_SIZE];
static struct Pokemon playerBefore[PARTY_SIZE], enemyBefore[PARTY_SIZE];
u8 gFieldLinkPlayerCount;
void (*gFieldCallback)(void);
bool8 (*gFieldCallback2)(void);
static MainCallback callback1, callback2;
static unsigned closes, aborts, abandons, scripts, unlocks, unfreezes;

static int CheckCleanup(void)
{
    const struct MegaBattleState empty = {0};
    const u8 noChoices[MAX_BATTLERS_COUNT] = {0};
    if (memcmp(&sMega, &empty, sizeof(sMega))
        || memcmp(sQueued, noChoices, sizeof(sQueued))
        || memcmp(sSelected, noChoices, sizeof(sSelected)))
    {
        fprintf(stderr, "return retained ephemeral Mega forms/used/queued/selected state\n");
        return 1;
    }
    if (memcmp(gPlayerParty, playerBefore, sizeof(gPlayerParty))
        || memcmp(gEnemyParty, enemyBefore, sizeof(gEnemyParty)))
    {
        fprintf(stderr, "return changed persistent party bytes\n");
        return 1;
    }
    return 0;
}

void CloseLink(void) { closes++; }
void NativeLink_Abort(void) { aborts++; }
void DexNavNative_AbandonBattle(void) { abandons++; }
void CB1_Overworld(void) {}
void CB2_ReturnToField(void) {}
void FieldCB_WarpExitFadeFromBlack(void) {}
void SetMainCallback1(MainCallback callback) { callback1 = callback; }
void SetMainCallback2(MainCallback callback) { callback2 = callback; }
void ScriptContext_Init(void) { scripts++; }
void UnlockPlayerFieldControls(void) { unlocks++; }
void UnfreezeObjectEvents(void) { unfreezes++; }
static void UnexpectedTrainerResult(void) { assert(!"invented trainer result"); }

int main(int argc, char **argv)
{
    assert(argc == 2);
    /* Nonzero whole-party sentinels catch any writes, including identity,
     * held item, stats, HP, PP, status, mail, and encrypted box data. */
    for (unsigned i = 0; i < sizeof(gPlayerParty); i++)
    {
        ((u8 *)gPlayerParty)[i] = (u8)(i * 17 + 3);
        ((u8 *)gEnemyParty)[i] = (u8)(i * 29 + 7);
    }
    memcpy(playerBefore, gPlayerParty, sizeof(gPlayerParty));
    memcpy(enemyBefore, gEnemyParty, sizeof(gEnemyParty));
    sActivity.state = NATIVE;
    sActivity.mode = NATIVE_LINK_SINGLE;
    sActivity.locked = TRUE;
    gFieldLinkPlayerCount = 2;
    /* Native continuation5: receiving Bob retained these exact form/used
     * entries after normal completion, without BattleMain cleanup. */
    sMega.forms[0][0] = sMega.forms[1][0] = 1;
    sMega.used[0] = sMega.used[1] = TRUE;
    if (!strcmp(argv[1], "disconnect"))
    {
        /* Interrupted exchange can retain any slot and pending choice. */
        memset(&sMega, 1, sizeof(sMega));
        memset(sQueued, 1, sizeof(sQueued));
        memset(sSelected, 1, sizeof(sSelected));
        sActivity.mode = NATIVE_LINK_COOP;
        sActivity.trainerCallback = UnexpectedTrainerResult;
        sActivity.trainerCaptured = sActivity.encounterPending = TRUE;
        sActivity.wildCaptured = sActivity.encounterOfferDeferred = TRUE;
    }
    else if (!strcmp(argv[1], "primary"))
        MegaGame_Reset(); /* Primary BattleMain already did its cleanup. */
    else if (!strcmp(argv[1], "trade"))
    {
        MegaGame_Reset();
        sActivity.mode = NATIVE_LINK_TRADE;
    }
    else
        assert(!strcmp(argv[1], "receiving"));

    for (unsigned iteration = 1; iteration <= 2; iteration++)
    {
        WorldActivity_ReturnToField();
        if (CheckCleanup()) return 1;
        assert(callback1 == CB1_Overworld && callback2 == CB2_ReturnToField);
        assert(gFieldCallback == FieldCB_WarpExitFadeFromBlack && !gFieldCallback2);
        assert(!gFieldLinkPlayerCount && !sActivity.locked);
        assert(!sActivity.trainerCallback && !sActivity.trainerCaptured);
        assert(!sActivity.encounterPending && !sActivity.wildCaptured);
        assert(!sActivity.encounterOfferDeferred && sActivity.state == RETURNING);
        assert(!strcmp(sActivity.status, "returning to field"));
        assert(closes == iteration && aborts == iteration && abandons == iteration);
        assert(scripts == iteration && unlocks == iteration && unfreezes == iteration);
    }
    return 0;
}
'''


class MegaReturnCleanupTests(unittest.TestCase):
    def test_common_return_clears_ephemeral_state_without_party_writes(self):
        with tempfile.TemporaryDirectory(prefix='rc4-mega-return-') as directory:
            source = Path(directory) / 'return.c'
            binary = Path(directory) / 'return'
            source.write_text(HARNESS)
            command = [
                'gcc', '-std=gnu99', '-DPORTABLE', '-DMODERN=1', '-DNONMATCHING',
                '-DUBFIX', '-DVER_64BIT', '-Werror',
                '-Werror=implicit-function-declaration', '-ffunction-sections',
                '-fdata-sections', '-iquote', '.', '-iquote', 'include',
                str(source), '-Wl,--gc-sections', '-o', str(binary),
            ]
            compiled = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            for scenario in ('receiving', 'disconnect', 'primary', 'trade'):
                with self.subTest(scenario=scenario):
                    result = subprocess.run([str(binary), scenario], cwd=ROOT,
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
