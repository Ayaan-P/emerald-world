"""Focused launcher contracts. Full two-native-client acceptance is separate."""
import pathlib
import unittest
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]

class WorldActivityContracts(unittest.TestCase):
    def test_public_boundary_and_portable_isolation(self):
        header = ROOT / 'include/platform/world_activity.h'
        self.assertTrue(header.exists(), 'public activity boundary is missing')
        text = header.read_text()
        for api in ('WorldActivity_Interact', 'WorldActivity_Update', 'WorldActivity_OwnsFieldInput', 'WorldActivity_FilterFieldKeys', 'WorldActivity_Status'):
            self.assertIn(api, text)
        source = (ROOT / 'src/platform/world_activity.c').read_text()
        self.assertTrue(source.startswith('#ifdef PORTABLE'))
        self.assertIn('NativeLink_IsActive()', source)
        self.assertIn('gReceivedRemoteLinkPlayers', source)
        self.assertNotIn('CreateTask_EnterCableClubSeat', source)
        self.assertNotIn('gReceivedRemoteLinkPlayers =', source)
        self.assertNotRegex(source, r'\bgBattleOutcome\s*=(?!=)')

    def test_real_c_name_encoding_and_input_ownership(self):
        # Compile the actual translation unit against real engine headers. GC
        # drops uncalled engine paths, not substitutes for native battle/trade.
        harness = r'''
#include <assert.h>
#include "src/platform/world_activity.c"
int main(void) {
    char name[25] = "unchanged";
    u8 text[64];
    assert(!CopyPeer(name, NULL));
    assert(!CopyPeer(name, ""));
    assert(!CopyPeer(name, "../save"));
    assert(!CopyPeer(name, "A B"));
    assert(!CopyPeer(name, "abcdefghijklmnopqrstuvwxy"));
    assert(!strcmp(name, "unchanged"));
    assert(CopyPeer(name, "abcdefghijklmnopqrstuvwx"));
    assert(strlen(name) == 24);
    assert(CopyPeer(name, "Peer_2-Name"));
    assert(!strcmp(name, "Peer_2-Name"));
    Encode(text, "Aa0-");
    assert(text[0] == CHAR_A && text[1] == CHAR_a);
    assert(text[2] == CHAR_0 && text[3] == CHAR_HYPHEN && text[4] == EOS);
    sActivity.state = IDLE;
    assert(!WorldActivity_OwnsFieldInput());
    assert(WorldActivity_FilterFieldKeys(0xffff) == 0xffff);
    for (unsigned state = MENU; state <= RETURNING; state++) {
        sActivity.state = state;
        assert(WorldActivity_OwnsFieldInput());
        assert(WorldActivity_FilterFieldKeys(0xffff) == 0);
    }
    sActivity.state = MENU;
    sActivity.mode = NATIVE_LINK_TRADE;
    assert(!strcmp(WorldActivity_Phase(), "menu"));
    assert(WorldActivity_Mode() == NATIVE_LINK_TRADE);
    sActivity.state = IDLE;
    assert(!strcmp(WorldActivity_Phase(), "idle"));
    assert(WorldActivity_Mode() == 0);
    strcpy(sActivity.talkPeer, "Peer_2-Name");
    assert(WorldActivity_TakeTalkRequest(name));
    assert(!strcmp(name, "Peer_2-Name"));
    strcpy(name, "unchanged");
    assert(!WorldActivity_TakeTalkRequest(name));
    assert(!strcmp(name, "unchanged"));
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / 'activity.c'
            binary = pathlib.Path(directory) / 'activity'
            source.write_text(harness)
            command = ['gcc', '-std=gnu99', '-DPORTABLE', '-DMODERN=1', '-DNONMATCHING',
                       '-DUBFIX', '-DVER_64BIT', '-Werror', '-Werror=implicit-function-declaration',
                       '-ffunction-sections', '-fdata-sections', '-iquote', '.', '-iquote', 'include',
                       str(source), '-Wl,--gc-sections', '-o', str(binary)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True)

    def test_committed_frame_and_field_only_integration(self):
        sdl = (ROOT / 'src/platform/sdl2.c').read_text()
        self.assertEqual(sdl.count('WorldActivity_Update();'), 3)
        for before in sdl.split('WorldBridge_AfterFrame(')[:-1]:
            self.assertTrue(before.rstrip().endswith('WorldActivity_Update();'))
        self.assertNotIn('WorldBridge_FilterInput(', sdl)
        field = (ROOT / 'src/field_control_avatar.c').read_text()
        body = field.split('void FieldGetPlayerInput(', 1)[1].split('\n}', 1)[0]
        self.assertIn('WorldActivity_FilterFieldKeys', body)
        self.assertIn('WorldBridge_FilterInput', body)
        bridge = (ROOT / 'src/platform/world_bridge.c').read_text()
        dialogue = bridge.split('static void SyncDialogue(void)', 1)[1].split('u16 WorldBridge_FilterInput', 1)[0]
        self.assertIn('WorldActivity_Interact(r->id)', dialogue)
        self.assertIn('WorldActivity_TakeTalkRequest', dialogue)
        self.assertIn('WorldActivity_OwnsFieldInput()', dialogue)
        filtering = bridge.split('u16 WorldBridge_FilterInput', 1)[1].split('void WorldBridge_WriteJSON', 1)[0]
        self.assertIn('if (WorldActivity_OwnsFieldInput()) return keys;', filtering)

    def test_admission_and_return_contracts(self):
        text = (ROOT / 'src/platform/world_activity.c').read_text()
        waiting = text.split('if (sActivity.state == WAIT_ADMIT)', 1)[1].split('if (sActivity.state == CONNECTING)', 1)[0]
        self.assertLess(waiting.index('if (!NativeLink_IsActive()) return;'), waiting.index('LockPlayerFieldControls();'))
        self.assertLess(waiting.index('LockPlayerFieldControls();'), waiting.index('OpenLink();'))
        connecting = text.split('if (sActivity.state == CONNECTING)', 1)[1].split('if (sActivity.state == NATIVE)', 1)[0]
        self.assertLess(connecting.index('if (!gReceivedRemoteLinkPlayers || !IsLinkPlayerDataExchangeComplete()) return;'), connecting.index('WorldActivity_StartNativeBattle'))
        self.assertIn('ActivityPartyReady', text)
        self.assertIn('!ActivityPartyReady(sActivity.mode)', waiting)
        self.assertIn('SetDynamicWarp(', connecting)
        cable = (ROOT / 'src/cable_club.c').read_text()
        helper = cable.split('int WorldActivity_StartNativeBattle', 1)[1].split('#endif', 1)[0]
        self.assertLess(helper.index('CreateTask(Task_WorldStartBattle'), helper.index('SavePlayerParty();'))
        self.assertIn('if (taskId == TASK_NONE)', helper)
        self.assertLess(helper.index('SavePlayerParty();'), helper.index('LoadPlayerBag();'))
        self.assertIn('CB2_ReturnFromCableClubBattle();', cable)
        self.assertIn('gMain.savedCallback = WorldActivity_ReturnToField;', cable)

if __name__ == '__main__':
    unittest.main()
