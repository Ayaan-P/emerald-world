"""Two paced state-machine instances of full production world_coop.c.

The existing engine fixture supplies Pokemon accessors and link IO scaffolding.
Only its declarations/helpers preceding PeerFixture are used, not its obsolete
completion driver. No native game, save file, SDL or SDK process is launched.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]


class CoopCompletionPeers(unittest.TestCase):
    def test_asymmetric_echo_drain_owned_merge_once_and_abort(self):
        scaffold = (ROOT / 'test/world/coop_engine_core.c').read_text().split('struct PeerFixture\n')[0]
        scaffold = scaffold.replace('../../src/platform/world_coop.c', 'src/platform/world_coop.c')
        scaffold = scaffold.replace(function(scaffold, 'SendBlock'), r'''
bool8 SendBlock(u8 mask, const void *src, u16 size)
{
    assert(mask == (3 ^ (1 << local)) && size == sizeof(struct CoopCompletion));
    lastCompletion = *(const struct CoopCompletion *)src;
    completionSends++;
    for (u8 recipient = 0; recipient < 2; recipient++)
    {
        assert(completionCount[recipient] < 8);
        completionQueue[recipient][completionCount[recipient]++] = lastCompletion;
    }
    return TRUE;
}
''')
        code = scaffold + r'''
u16 gTrainerBattleOpponent_A;
const struct Trainer gTrainers[TRAINERS_COUNT] = {0};
void WorldCoop_CreateTrainerParty(void) { assert(!"unexpected trainer entry"); }
void BattleSetup_RecordWorldTrainerBattle(void) {}
void BattleSetup_RecordWorldWildBattle(void) {}
struct Peer {
    typeof(sCoop) coop;
    struct Pokemon party[PARTY_SIZE];
    u16 indexes[MAX_BATTLERS_COUNT];
    bool8 connected;
};
static struct Peer peers[2];
static struct Pokemon original[2][PARTY_SIZE], stagedParty[PARTY_SIZE];
static unsigned merges[2], grants[2];
static void Save(void) {
    peers[local].coop = sCoop;
    memcpy(peers[local].party, gPlayerParty, sizeof(gPlayerParty));
    memcpy(peers[local].indexes, gBattlerPartyIndexes, sizeof(gBattlerPartyIndexes));
    peers[local].connected = active;
}
static void Load(u8 owner) {
    local = owner; sCoop = peers[owner].coop; active = peers[owner].connected;
    memcpy(gPlayerParty, peers[owner].party, sizeof(gPlayerParty));
    memcpy(gBattlerPartyIndexes, peers[owner].indexes, sizeof(gBattlerPartyIndexes));
}
static void DeliverOne(void) {
    struct CoopCompletion packet;
    assert(completionCount[local]); packet = completionQueue[local][0];
    memmove(completionQueue[local], completionQueue[local] + 1,
            --completionCount[local] * sizeof(packet));
    assert(WorldCoop_ReceiveCompletion((u8 *)&packet, sizeof(packet), packet.sender) == 1);
}
static void DeliverAll(void) { while (completionCount[local]) DeliverOne(); }
static void Setup(void) {
    const u8 slots[3] = {1, 3, 4};
    testGeneration = 17; gBattleOutcome = B_OUTCOME_WON;
    completionSends = 0; memset(completionCount, 0, sizeof(completionCount));
    memset(merges, 0, sizeof(merges)); memset(grants, 0, sizeof(grants));
    for (u8 owner = 0; owner < 2; owner++) {
        for (u8 i = 0; i < PARTY_SIZE; i++) original[owner][i] = FixtureMon(1 + i, 1000 + owner * 100 + i);
        for (u8 i = 0; i < 3; i++) {
            stagedParty[owner * 3 + i] = original[owner][slots[i]];
            stagedParty[owner * 3 + i].hp = 10 + owner * 3 + i;
        }
    }
    for (u8 owner = 0; owner < 2; owner++) {
        memset(&sCoop, 0, sizeof(sCoop)); local = owner; active = TRUE;
        sCoop.state = COOP_BATTLE; sCoop.local = owner; sCoop.generation = 17;
        sCoop.seed = 123; sCoop.count = 3; sCoop.originalCount = 6; sCoop.staged = TRUE;
        memcpy(sCoop.slots, slots, sizeof(slots));
        memcpy(sCoop.original, original[owner], sizeof(sCoop.original));
        sCoop.enemyCount = 2; sCoop.enemies[0] = FixtureMon(100, 3000); sCoop.enemies[1] = FixtureMon(101, 3001);
        sCoop.reward = 3; sCoop.rewardMask[0] = 1 << slots[0]; sCoop.rewardMask[1] = 1 << slots[1];
        sCoop.rewardPayday = 20 + owner; sCoop.rewardMultiplier = 1;
        memcpy(gPlayerParty, stagedParty, sizeof(gPlayerParty));
        memset(gBattlerPartyIndexes, 0, sizeof(gBattlerPartyIndexes));
        gBattlerPartyIndexes[2] = 3;
        Save();
    }
}
static void MergeOnce(void) {
    assert(WorldCoop_PreparePrivateRewards()); merges[local]++;
    assert(!WorldCoop_PreparePrivateRewards());
    assert(gPlayerPartyCount == 6 && gPaydayMoney == 20 + local);
    for (u8 i = 0; i < PARTY_SIZE; i++) {
        assert(gPlayerParty[i].box.personality == original[local][i].box.personality);
        if (i == 1 || i == 3 || i == 4) {
            u8 selected = i == 1 ? 0 : i == 3 ? 1 : 2;
            assert(gPlayerParty[i].hp == 10 + local * 3 + selected);
        } else assert(memcmp(&gPlayerParty[i], &original[local][i], sizeof(struct Pokemon)) == 0);
    }
    assert(WorldCoop_NextReward()); grants[local]++;
    assert(gBattleMons[1].species == 100 && gSentPokesToOpponent[0] == (1 << 1));
    assert(WorldCoop_NextReward()); grants[local]++;
    assert(gBattleMons[1].species == 101 && gSentPokesToOpponent[0] == (1 << 3));
    assert(!WorldCoop_NextReward() && !WorldCoop_NextReward());
    Save();
}
int main(void) {
    Setup();
    Load(0);
    for (unsigned frame = 0; frame < 50; frame++) {
        assert(!WorldCoop_ReadyForPrivateRewards());
        assert(!WorldCoop_CompletionCommitted() && sCoop.staged);
    }
    assert(completionSends == 1); Save();
    Load(1); DeliverAll();
    assert(!WorldCoop_ReadyForPrivateRewards()); /* Own READY queued. */
    DeliverAll();
    assert(!WorldCoop_ReadyForPrivateRewards()); /* Own COMMIT queued. */
    assert(!WorldCoop_ReadyForPrivateRewards()); Save();
    Load(0);
    DeliverOne(); /* own READY */
    DeliverOne(); /* peer READY, but deliberately hold peer COMMIT */
    assert(!WorldCoop_ReadyForPrivateRewards()); /* Own COMMIT queued. */
    assert(!WorldCoop_ReadyForPrivateRewards());
    DeliverOne(); /* peer COMMIT arrives before local echo */
    assert(sCoop.peerCommit && WorldCoop_CompletionCommitted());
    assert(!WorldCoop_ReadyForPrivateRewards());
    DeliverOne(); /* authenticated local COMMIT */
    assert(WorldCoop_CompletionCommitted());
    Save();
    Load(1); DeliverAll();
    assert(WorldCoop_ReadyForPrivateRewards()); MergeOnce();
    Load(0); active = FALSE; /* Normal peer close after the durable echo. */
    assert(WorldCoop_ReadyForPrivateRewards()); MergeOnce();
    assert(merges[0] == 1 && merges[1] == 1 && grants[0] == 2 && grants[1] == 2);
    /* The normal reset after private rewards must not roll the committed party
     * back or carry completion bits into the next encounter. */
    {
        struct Pokemon committed[PARTY_SIZE];
        memcpy(committed, gPlayerParty, sizeof(committed));
        WorldCoop_Abort();
        assert(!memcmp(committed, gPlayerParty, sizeof(committed)));
        active = gReceivedRemoteLinkPlayers = TRUE;
        assert(WorldCoop_StartBattle(FALSE));
        assert(!sCoop.readySent && !sCoop.commitSent && !sCoop.peerReady && !sCoop.peerCommit);
        assert(!WorldCoop_CompletionCommitted() && !WorldCoop_PreparePrivateRewards());
    }

    /* Disconnect before bilateral readiness still restores the untouched party. */
    Setup(); Load(0);
    assert(!WorldCoop_ReadyForPrivateRewards());
    assert(sCoop.readySent && !sCoop.peerReady && !WorldCoop_CompletionCommitted());
    active = FALSE; WorldCoop_Abort();
    assert(!memcmp(gPlayerParty, original[0], sizeof(gPlayerParty)));
    assert(!WorldCoop_PreparePrivateRewards() && !WorldCoop_CompletionCommitted());
    for (u8 owner = 0; owner < 2; owner++) {
        Setup(); Load(owner);
        /* A swapped-in partner identity cannot become a durable private party. */
        gPlayerParty[owner * MULTI_PARTY_SIZE] = FixtureMon(25, 9000);
        assert(!WorldCoop_ReadyForPrivateRewards() && !active);
        assert(!WorldCoop_CompletionCommitted());
        WorldCoop_Abort();
        assert(!memcmp(gPlayerParty, original[owner], sizeof(gPlayerParty)));
        assert(!WorldCoop_PreparePrivateRewards());
    }
    puts("full production completion: asymmetric two-peer echo, owned merge, two rewards once, pre-ready rollback passed");
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='coop-completion-peers-') as tmp:
            c, exe = Path(tmp) / 'peers.c', Path(tmp) / 'peers'
            c.write_text(code)
            command = ['cc', '-std=gnu99', '-g', '-fsanitize=address,undefined',
                       '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                       '-DPORTABLE', '-DUBFIX', '-DVER_64BIT', '-DNONMATCHING', '-DMODERN=1',
                       '-iquote', str(ROOT / 'include'), '-iquote', str(ROOT), str(c), '-o', str(exe)]
            built = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(exe)], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('pre-ready rollback passed', run.stdout)


if __name__ == '__main__':
    unittest.main()
