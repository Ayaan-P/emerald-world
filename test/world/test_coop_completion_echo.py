"""Production co-op completion with delayed local block echoes, no native game."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]


class CoopCompletionEcho(unittest.TestCase):
    def test_active_session_waits_for_commit_echo(self):
        source = (ROOT / 'src/platform/world_coop.c').read_text()
        fixture = r'''
#include <assert.h>
#include <string.h>
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint8_t bool8;
#define TRUE 1
#define FALSE 0
#define COOP_BATTLE 2
#define COOP_REWARDS 3
#define PARTY_SIZE 6
#define COOP_MAGIC 0x4357
#define COOP_VERSION 2
#define COOP_TIMEOUT 1800
#define COOP_READY 11
#define COOP_COMMIT 12
#define B_OUTCOME_WON 1
#define B_OUTCOME_CAUGHT 7
#define B_OUTCOME_MON_TELEPORTED 10
struct Pokemon { u8 unused; };
struct CoopCompletion {
    u16 magic; u8 version, phase; u32 generation, seed;
    u8 sender, outcome, reward, catchOwner;
};
static struct {
    u8 state, local, readySent, commitSent, commitEchoed, peerReady, peerCommit;
    u8 peerOutcome, peerReward, reward, enemyCount, catchOwner, kind;
    u16 timer;
    u32 generation, seed;
} sCoop;
static struct CoopCompletion pending;
static u8 gBattleOutcome;
static unsigned active, finished, acceptSend, valid, sends, aborts;
static u32 generation;
static int NativeLink_IsActive(void) { return active; }
static u32 NativeLink_Generation(void) { return generation; }
static void NativeLink_Abort(void) { active = 0; aborts++; }
static int IsLinkTaskFinished(void) { return finished; }
static int BuildPrivateParty(struct Pokemon *party) { (void)party; return valid; }
static u8 BitmaskAllOtherLinkPlayers(void) { return 2; }
static int SendBlock(u8 mask, const void *data, u16 size) {
    assert(mask == 2 && size == sizeof(pending));
    if (!acceptSend) return 0;
    memcpy(&pending, data, size); sends++; finished = 0; return 1;
}
'''
        for name in ('WorldCoop_ReceiveCompletion', 'WorldCoop_CompletionCommitted',
                     'WorldCoop_ReadyForPrivateRewards'):
            fixture += function(source, name)
        fixture += r'''
static void reset(void) {
    memset(&sCoop, 0, sizeof(sCoop)); memset(&pending, 0, sizeof(pending));
    sCoop.state = COOP_BATTLE; sCoop.generation = generation = 7;
    sCoop.seed = 123; sCoop.enemyCount = 1; sCoop.reward = 1; gBattleOutcome = B_OUTCOME_WON;
    active = finished = acceptSend = valid = 1; sends = aborts = 0;
}
static struct CoopCompletion peer(u8 phase) {
    struct CoopCompletion p = {COOP_MAGIC, COOP_VERSION, phase, 7, 123, 1,
                               gBattleOutcome, sCoop.reward, sCoop.catchOwner};
    return p;
}
static int receive(struct CoopCompletion *p, u8 sender) {
    return WorldCoop_ReceiveCompletion((u8 *)p, sizeof(*p), sender);
}
static void ready_and_peer_commit(void) {
    struct CoopCompletion p = peer(COOP_READY);
    assert(!WorldCoop_ReadyForPrivateRewards()); /* Queue our READY. */
    assert(sCoop.readySent && pending.phase == COOP_READY);
    assert(receive(&pending, 0) == 1); finished = 1;
    assert(receive(&p, 1) == 1);
    p.phase = COOP_COMMIT;
    assert(receive(&p, 1) == 1); /* Faster peer's commit arrives first. */
}
int main(void) {
    struct CoopCompletion p;
    reset(); ready_and_peer_commit();
    assert(!WorldCoop_ReadyForPrivateRewards()); /* Queued is NOT echoed. */
    assert(sCoop.commitSent && sends == 2 && pending.phase == COOP_COMMIT);
    assert(WorldCoop_CompletionCommitted()); /* Durable READY boundary is unchanged. */
    assert(!WorldCoop_ReadyForPrivateRewards() && sends == 2);
    /* Preserve completed results if normal peer closure overtakes our echo. */
    active = 0;
    assert(WorldCoop_CompletionCommitted());
    assert(WorldCoop_ReadyForPrivateRewards() && aborts == 0);

    reset();
    assert(!WorldCoop_ReadyForPrivateRewards()); /* No partner READY yet. */
    active = 0;
    assert(!WorldCoop_CompletionCommitted());
    assert(!WorldCoop_ReadyForPrivateRewards() && aborts == 1);

    reset(); ready_and_peer_commit();
    assert(!WorldCoop_ReadyForPrivateRewards());
    p = pending; p.generation--;
    assert(receive(&p, 0) == -1 && !WorldCoop_ReadyForPrivateRewards());
    p = pending; p.seed++;
    assert(receive(&p, 0) == -1 && !WorldCoop_ReadyForPrivateRewards());
    p = pending; p.sender = 1;
    assert(receive(&p, 0) == -1 && !WorldCoop_ReadyForPrivateRewards());
    /* Both READY retransmissions remain legal before and after the echo. */
    p = peer(COOP_READY);
    assert(receive(&p, 1) == 1 && !WorldCoop_ReadyForPrivateRewards());
    p = pending; p.phase = COOP_READY;
    assert(receive(&p, 0) == 1 && !WorldCoop_ReadyForPrivateRewards());
    p = pending; p.reward = 0;
    assert(receive(&p, 0) == -1 && !WorldCoop_ReadyForPrivateRewards());
    p = pending; p.outcome = 2;
    assert(receive(&p, 0) == -1 && !WorldCoop_ReadyForPrivateRewards());
    assert(receive(&pending, 0) == 1); finished = 1;
    assert(WorldCoop_CompletionCommitted());
    assert(WorldCoop_ReadyForPrivateRewards());
    p = peer(COOP_READY);
    assert(receive(&p, 1) == 1 && WorldCoop_ReadyForPrivateRewards());
    p.phase = COOP_COMMIT;
    assert(receive(&p, 1) == 1 && WorldCoop_ReadyForPrivateRewards());
    assert(receive(&pending, 0) == 1); /* Duplicate authenticated echo is idempotent. */
    assert(sends == 2 && WorldCoop_ReadyForPrivateRewards());
    sCoop.state = COOP_REWARDS;
    assert(!WorldCoop_CompletionCommitted() && !WorldCoop_ReadyForPrivateRewards());
    assert(receive(&pending, 0) == -1); /* No second private reward phase. */

    reset(); acceptSend = 0;
    assert(!WorldCoop_ReadyForPrivateRewards() && !sCoop.readySent && sends == 0);
    acceptSend = 1; assert(!WorldCoop_ReadyForPrivateRewards());
    finished = 1; p = peer(COOP_READY); p.outcome = 2;
    assert(receive(&p, 1) == 1);
    assert(!WorldCoop_ReadyForPrivateRewards() && aborts == 1);

    /* Combined catch-v3/echo integration: a catch needs peer COMMIT even
     * across normal closure, while an active session also needs its echo. */
    for (u8 owner = 1; owner <= 2; owner++) {
        reset(); sCoop.catchOwner = owner; sCoop.reward = 0;
        gBattleOutcome = B_OUTCOME_CAUGHT;
        assert(!WorldCoop_ReadyForPrivateRewards());
        assert(receive(&pending, 0) == 1); finished = 1;
        p = peer(COOP_READY); assert(receive(&p, 1) == 1);
        assert(!WorldCoop_ReadyForPrivateRewards());
        assert(!WorldCoop_CompletionCommitted());
        active = 0;
        assert(!WorldCoop_ReadyForPrivateRewards() && aborts == 1);

        reset(); sCoop.catchOwner = owner; sCoop.reward = 0;
        gBattleOutcome = B_OUTCOME_CAUGHT;
        ready_and_peer_commit();
        assert(!WorldCoop_ReadyForPrivateRewards());
        assert(WorldCoop_CompletionCommitted());
        p = pending; p.catchOwner = owner == 1 ? 2 : 1;
        assert(receive(&p, 0) == -1 && !sCoop.commitEchoed);
        assert(!WorldCoop_ReadyForPrivateRewards());
        assert(receive(&pending, 0) == 1);
        assert(WorldCoop_ReadyForPrivateRewards());
        active = 0;
        assert(WorldCoop_ReadyForPrivateRewards());
        generation++;
        assert(!WorldCoop_CompletionCommitted());
        assert(!WorldCoop_ReadyForPrivateRewards());
    }

    /* A replacement active link cannot inherit a completed battle's echo. */
    reset(); ready_and_peer_commit();
    assert(!WorldCoop_ReadyForPrivateRewards());
    assert(receive(&pending, 0) == 1);
    assert(WorldCoop_ReadyForPrivateRewards());
    generation++;
    assert(!WorldCoop_ReadyForPrivateRewards() && aborts == 1);
    assert(!WorldCoop_CompletionCommitted());
    assert(!WorldCoop_ReadyForPrivateRewards());
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='coop-completion-echo-') as tmp:
            c, exe = Path(tmp) / 'test.c', Path(tmp) / 'test'
            c.write_text(fixture)
            build = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                                    str(c), '-o', str(exe)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == '__main__':
    unittest.main()
