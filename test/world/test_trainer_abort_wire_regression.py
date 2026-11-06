"""Focused C regressions; no SDL sessions, SDK clients, or gameplay.

Compile the actual production statement/function under small boundary stubs.
The wire fixture reproduces the observed unused-mon mail byte at offset 85.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class TrainerRegression(unittest.TestCase):
    def run_c(self, body):
        with tempfile.TemporaryDirectory(prefix='emerald-trainer-unit-') as directory:
            source = Path(directory) / 'case.c'
            binary = Path(directory) / 'case'
            source.write_text('#include <stdint.h>\n#include <stdio.h>\n#include <string.h>\n' + body)
            compiled = subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_unused_npc_slots_are_zero_on_wire(self):
        text = (ROOT / 'src/platform/world_coop.c').read_text()
        start = text.index('memset(&sCoop.outgoing, 0, sizeof(sCoop.outgoing));')
        end = text.index('if (!SendBlock(', start)
        production = text[start:end]
        self.run_c('''
#define COOP_MAGIC 0x4357
#define COOP_VERSION 2
struct Pokemon { unsigned char bytes[100]; };
struct CoopMonBlock { uint16_t magic; unsigned char version, phase; struct Pokemon mon; };
static struct {
    int owner, capturedCount;
    struct Pokemon selected[3], capturedEnemies[6];
    struct CoopMonBlock outgoing;
} sCoop;
static void prepare(unsigned char phase) {
''' + production + '''
}
int main(void) {
    struct Pokemon zero = {0};
    for (int owner = 0; owner <= 1; owner++) {
        for (int count = 1; count <= 6; count++) {
            memset(&sCoop, 0, sizeof(sCoop));
            sCoop.owner = owner;
            sCoop.capturedCount = count;
            for (int slot = 0; slot < 6; slot++) {
                if (slot < count) memset(&sCoop.capturedEnemies[slot], slot + 1, sizeof(zero));
                else sCoop.capturedEnemies[slot].bytes[85] = 255;
            }
            for (unsigned phase = 4; phase <= 9; phase++) {
                prepare(phase);
                const struct Pokemon *expected = owner && phase - 4 < (unsigned)count
                    ? &sCoop.capturedEnemies[phase - 4] : &zero;
                if (memcmp(&sCoop.outgoing.mon, expected, sizeof(zero))) {
                    fprintf(stderr, "noncanonical NPC wire slot: owner=%d count=%d phase=%u mail=%u\\n", owner, count, phase, sCoop.outgoing.mon.bytes[85]);
                    return 1;
                }
            }
        }
    }
    return 0;
}
''')

    def test_trainer_exchange_abort_does_not_invent_a_defeat(self):
        text = (ROOT / 'src/platform/world_activity.c').read_text()
        start = text.index('void WorldActivity_ReturnToField(void)\n{')
        end = text.index('\n}\n', start) + 3
        production = text[start:end]
        self.run_c('''
#define FALSE 0
#define B_OUTCOME_LOST 2
#define RETURNING 6
 typedef void (*MainCallback)(void);
struct { MainCallback trainerCallback; int locked, trainerCaptured, encounterPending,
    wildCaptured, encounterOfferDeferred, state; const char *status; } sActivity;
int gFieldLinkPlayerCount, gBattleOutcome;
MainCallback gFieldCallback, gFieldCallback2;
int resultCallbacks, scriptResets, unlocks, unfreezes;
void CloseLink(void) {}
void NativeLink_Abort(void) {}
void DexNavNative_AbandonBattle(void) {}
/* Mega state is exercised by test_rc4_mega_return_cleanup, not this abort fixture. */
void MegaGame_Reset(void) {}
void CB1_Overworld(void) {}
void CB2_ReturnToField(void) {}
void FieldCB_WarpExitFadeFromBlack(void) {}
void SetMainCallback1(MainCallback callback) { (void)callback; }
void SetMainCallback2(MainCallback callback) { (void)callback; }
void ScriptContext_Init(void) { scriptResets++; }
void UnlockPlayerFieldControls(void) { unlocks++; }
void UnfreezeObjectEvents(void) { unfreezes++; }
void TrainerResult(void) { resultCallbacks++; }
''' + production + '''
int main(void) {
    sActivity.trainerCallback = TrainerResult;
    sActivity.locked = sActivity.trainerCaptured = sActivity.encounterPending = 1;
    sActivity.wildCaptured = sActivity.encounterOfferDeferred = 1;
    gFieldLinkPlayerCount = 2;
    WorldActivity_ReturnToField();
    if (resultCallbacks || gBattleOutcome || scriptResets != 1 || unlocks != 1
        || unfreezes != 1 || gFieldLinkPlayerCount || sActivity.trainerCallback
        || sActivity.locked || sActivity.trainerCaptured || sActivity.encounterPending
        || sActivity.wildCaptured || sActivity.encounterOfferDeferred
        || sActivity.state != RETURNING) {
        fprintf(stderr, "unsafe trainer abort: resultCallbacks=%d outcome=%d scriptResets=%d unlocks=%d unfreezes=%d\\n",
                resultCallbacks, gBattleOutcome, scriptResets, unlocks, unfreezes);
        return 1;
    }
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main(verbosity=2)
