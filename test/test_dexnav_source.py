"""Source-only DexNav acceptance gates. Parent runs these at RC3, not this worker."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DexNavSourceTests(unittest.TestCase):
    def test_pinned_inputs(self):
        manifest = json.loads((ROOT / 'vendor/expansion-dexnav/provenance.json').read_text())
        self.assertEqual(manifest['commit'], 'c460a8661dfa0598ae25d42a968c690ecbf489c6')
        for item in manifest['files']:
            data = (ROOT / item['imported_as']).read_bytes()
            self.assertEqual(hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest(), item['blob'])

    def test_whole_state_machine_not_replaced_by_menu(self):
        source = (ROOT / 'src/dexnav.c').read_text()
        for name in ('struct DexNavSearch', 'struct DexNavGUI', 'Task_DexNavMain',
                     'DexNavPickTile', 'DexNavGeneratePotential', 'DexNavGenerateMoveset',
                     'OnStep_DexNavSearch', 'TryFindHiddenPokemon'):
            self.assertIn(name, source)
        self.assertGreater(len(source.splitlines()), 2500)
        self.assertNotIn('gSaveBlock3Ptr', source)
        self.assertNotIn('gParties[', source)
        self.assertNotIn('gObjectEvents[gPlayerAvatar.spriteId]', source)

    def test_final_generation_precedes_real_admission(self):
        source = (ROOT / 'src/dexnav.c').read_text()
        handoff = source[source.index('if (sDexNavSearchDataPtr->proximity < 1)'):]
        self.assertLess(handoff.index('CreateDexNavWildMon('), handoff.index('BattleSetup_StartWildBattle();'))
        temporary = source[source.index('static void DexNavGenerateMoveset(', source.index('//// DEXNAV MON GENERATOR')):]
        temporary = temporary[:temporary.index('static u16 DexNavGenerateHeldItem')]
        self.assertNotIn('WorldActivity_', temporary)
        self.assertNotIn('CreateWildMon(', temporary)
        self.assertIn('DexNavNative_GenerateMoves', temporary)

    def test_no_shared_search_state_or_remote_object_ids(self):
        adapter = (ROOT / 'src/platform/dexnav_native.c').read_text()
        self.assertNotIn('WorldBridge_', adapter)
        self.assertNotIn('SpawnSpecialObjectEvent', adapter)
        self.assertIn('NativeSave_Open', adapter)
        self.assertIn('NativeSave_Write', adapter)
        self.assertIn('abilityNum < 2', adapter)
        self.assertIn('DexNavNative_BattleFinished', (ROOT / 'src/battle_setup.c').read_text())


if __name__ == '__main__':
    unittest.main()
