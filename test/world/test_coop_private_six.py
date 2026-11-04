"""Real co-op admission/projection/merge with all six private owner slots.

Only the test IO/accessor prefix from coop_engine_core is reused. No native
engine executable, SDL or save file is opened by this component test.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PrivateSixPartyTests(unittest.TestCase):
    def test_every_alive_mask_for_both_owners(self):
        fixture = (ROOT/'test/world/coop_engine_core.c').read_text()
        fixture = fixture[:fixture.index('struct PeerFixture')]
        fixture = fixture.replace('#include "../../src/platform/world_coop.c"',
            '#include "' + str(ROOT/'src/platform/world_coop.c') + '"')
        # The shared legacy fixture's transport replies predate six NPC wire
        # slots. Bind these explicit wild replies to the current wire contract.
        fixture = fixture.replace('if (size == sizeof(struct CoopCompletion))',
            'if (size == sizeof(struct CoopCompletion) && ((const u8 *)src)[3] >= COOP_READY)')
        fixture = fixture.replace('header.owner = remoteOwner;', '''header.owner = remoteOwner;
        header.kind = header.trainer = 0;
        header.enemyCount = remoteOwner ? 1 : 0;''')
        fixture = fixture.replace('else if (remoteOwner) block.mon = remoteWild;',
            'else if (remoteOwner && block.phase == 4) block.mon = remoteWild;')
        code = fixture + r'''
u16 gTrainerBattleOpponent_A;
const struct Trainer gTrainers[TRAINERS_COUNT] = {0};
void WorldCoop_CreateTrainerParty(void) {}
void BattleSetup_RecordWorldTrainerBattle(void) {}
void BattleSetup_RecordWorldWildBattle(void) {}
int main(void) {
    for (u8 owner = 0; owner < 2; owner++)
    for (unsigned mask = 0; mask < 64; mask++) {
        struct Pokemon originals[PARTY_SIZE], merged[PARTY_SIZE];
        u8 selected[3], count = 0;
        Reset(owner, TRUE);
        WorldCoop_Abort();
        for (u8 i = 0; i < PARTY_SIZE; i++) {
            gPlayerParty[i].hp = mask & (1u << i) ? 20 : 0;
            if (gPlayerParty[i].hp && count < 3) selected[count++] = i;
        }
        memcpy(originals, gPlayerParty, sizeof(originals));
        active = gReceivedRemoteLinkPlayers = TRUE;
        WorldCoop_CaptureWild();
        if (!count) {
            assert(!WorldCoop_StartBattle(TRUE));
            assert(!memcmp(originals, gPlayerParty, sizeof(originals)));
            continue;
        }
        assert(WorldCoop_StartBattle(TRUE));
        assert(sCoop.count == count && sCoop.originalCount == 6);
        assert(!memcmp(selected, sCoop.slots, count));
        for (unsigned phase = 0; phase <= COOP_CONFIRM; phase++) {
            CB2_Exchange();
            if (sCoop.state != COOP_EXCHANGE && sCoop.state != COOP_BATTLE)
                fprintf(stderr,"owner=%u mask=%u exchange failed at input phase=%u statephase=%u sizes=%u,%u\\n",owner,mask,phase,sCoop.phase,sizes[0],sizes[1]);
        }
        assert(sCoop.state == COOP_BATTLE && sCoop.staged);
        for (u8 i = 0; i < count; i++)
            gPlayerParty[owner*3+i].hp = 1+i;
        assert(BuildPrivateParty(merged));
        for (u8 i = 0; i < PARTY_SIZE; i++) {
            struct Pokemon expected = originals[i];
            for (u8 j = 0; j < count; j++)
                if (selected[j] == i) expected.hp = 1+j;
            assert(!memcmp(&expected, &merged[i], sizeof(expected)));
            assert(!memcmp(WorldCoop_GetOwnMon(i), &merged[i], sizeof(expected)));
        }
        /* Corrupting the partner's staged party must never import it into
         * any private owner slot, including slots 3 through 5. */
        memset(gPlayerParty + (owner^1)*3, 0xFF, 3*sizeof(struct Pokemon));
        assert(BuildPrivateParty(merged));
        for (u8 i = 0; i < PARTY_SIZE; i++)
            assert(merged[i].box.personality == originals[i].box.personality);
        WorldCoop_Abort();
        assert(gPlayerPartyCount == 6);
        assert(!memcmp(originals, gPlayerParty, sizeof(originals)));
    }
    puts("both owners/all 64 availability masks: private six-slot admission, merge and rollback passed");
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='coop-private-six-') as temp:
            path = Path(temp)
            (path/'six.c').write_text(code)
            result = subprocess.run(['cc', '-std=gnu99', '-g',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                '-fno-pie', '-no-pie', '-ffunction-sections', '-fdata-sections',
                '-Wl,--gc-sections', '-DPORTABLE', '-DUBFIX', '-DVER_64BIT',
                '-DNONMATCHING', '-DMODERN=1', '-iquote', 'include', '-iquote', '.',
                str(path/'six.c'), '-o', str(path/'six')], cwd=ROOT,
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(path/'six')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('rollback passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
