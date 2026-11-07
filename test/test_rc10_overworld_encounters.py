"""Compile the real native policy and check its Expansion integration guards.

EW_RC7_ENGINE points at a reconstructed source tree with the encounter patch.
No game executable, human saves, sockets or live server are used.
"""
from pathlib import Path
import os
import hashlib
import json
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(os.environ.get('EW_RC7_ENGINE', ROOT / 'engines/expansion-native'))


class OverworldEncounterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global ENGINE
        cls.source_dir = tempfile.TemporaryDirectory()
        handoff = ROOT / 'docs/attempt-handoffs/rc7'
        manifest = json.loads((handoff / 'overworld-encounters-source-manifest.json').read_text())
        patch = (handoff / manifest['patch']).read_bytes()
        assert hashlib.sha256(patch).hexdigest() == manifest['patch_sha256']
        sources, path = {}, None
        for line in patch.decode().splitlines():
            if line.startswith('diff --git '):
                path = None
            elif line.startswith('+++ b/'):
                path = line[6:]
                sources[path] = []
            elif path and line.startswith((' ', '+')):
                sources[path].append(line[1:])
        for entry in manifest['files']:
            content = '\n'.join(sources[entry['path']]) + '\n'
            assert hashlib.sha256(content.encode()).hexdigest() == entry['sha256']
            if 'EW_RC7_ENGINE' in os.environ:
                assert (ENGINE / entry['path']).read_text() == content
            target = Path(cls.source_dir.name) / entry['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        if 'EW_RC7_ENGINE' not in os.environ:
            ENGINE = Path(cls.source_dir.name)

    @classmethod
    def tearDownClass(cls):
        cls.source_dir.cleanup()

    def test_native_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / 'platform').mkdir()
            (p / 'constants').mkdir()
            (p / 'global.h').write_text('''
#ifndef TEST_GLOBAL
#define TEST_GLOBAL
#include <stddef.h>
typedef unsigned char bool8;
typedef unsigned u32;
#define TRUE 1
#define FALSE 0
#define PARTY_SIZE 6
#define PYRAMID_LOCATION_NONE 0
#define MAPSEC_BATTLE_FRONTIER 99
#define MON_DATA_SPECIES 0
#define MON_DATA_IS_EGG 1
#define MON_DATA_HP 2
struct Pokemon { unsigned fields[3]; };
extern struct Pokemon gPlayerParty[PARTY_SIZE];
extern void *gSaveBlock1Ptr, *gSaveBlock2Ptr;
extern struct Main { bool8 inBattle; } gMain;
extern struct Map { unsigned regionMapSectionId; } gMapHeader;
unsigned GetMonData(struct Pokemon *, unsigned);
bool8 WorldBridge_Enabled(void), GeneratedMap_IsInside(void), GeneratedMap_EntryPending(void);
bool8 GetSafariZoneFlag(void), InBattlePike(void), IsOverworldLinkActive(void), NativeLink_IsActive(void);
unsigned CurrentBattlePyramidLocation(void);
#endif
''')
            for header in ['battle_pike.h', 'battle_pyramid.h', 'event_data.h',
                           'link.h', 'main.h', 'overworld.h', 'pokemon.h', 'safari_zone.h',
                           'platform/generated_map.h', 'platform/native_link.h',
                           'platform/world_bridge.h', 'constants/region_map_sections.h']:
                (p / header).write_text('#include "global.h"\n')
            (p / 'wild_encounter_ow.h').write_text('''
#define OWE_GENERATED 1
void DespawnAllOverworldWildEncounters(unsigned, unsigned);
void SetMinimumOWESpawnTimer(void);
''')
            (p / 'test.c').write_text('''
#include <assert.h>
#include <string.h>
#include "global.h"
#include "platform/overworld_encounters.h"
struct Pokemon gPlayerParty[PARTY_SIZE];
void *gSaveBlock1Ptr = (void *)1, *gSaveBlock2Ptr = (void *)1;
struct Main gMain;
struct Map gMapHeader;
static unsigned world, inside, pending, safari, pike, pyramid, link, nativeLink;
static unsigned timers, despawns;
unsigned GetMonData(struct Pokemon *p, unsigned field) { return p->fields[field]; }
bool8 WorldBridge_Enabled(void) { return world; }
bool8 GeneratedMap_IsInside(void) { return inside; }
bool8 GeneratedMap_EntryPending(void) { return pending; }
bool8 GetSafariZoneFlag(void) { return safari; }
bool8 InBattlePike(void) { return pike; }
unsigned CurrentBattlePyramidLocation(void) { return pyramid; }
bool8 IsOverworldLinkActive(void) { return link; }
bool8 NativeLink_IsActive(void) { return nativeLink; }
void DespawnAllOverworldWildEncounters(unsigned kind, unsigned flags) {
    assert(kind == 1 && flags == 0); ++despawns;
}
void SetMinimumOWESpawnTimer(void) { ++timers; }
static void blocked(unsigned *flag) {
    *flag = 1;
    assert(!OverworldEncounters_Allowed());
    assert(OverworldEncounters_UnavailableReason());
    OverworldEncounters_Toggle(); /* Off always works, even after context changes. */
    assert(!OverworldEncounters_Enabled());
    unsigned before = timers;
    OverworldEncounters_Toggle(); /* Cannot enable in the forbidden context. */
    assert(!OverworldEncounters_Enabled() && timers == before);
    *flag = 0;
    OverworldEncounters_Toggle();
    assert(OverworldEncounters_Allowed());
}
int main(void) {
    assert(!OverworldEncounters_Enabled());
    assert(!OverworldEncounters_Allowed());
    OverworldEncounters_Toggle(); assert(!OverworldEncounters_Enabled());
    gPlayerParty[5].fields[0] = 25; gPlayerParty[5].fields[2] = 10;
    assert(!OverworldEncounters_UnavailableReason());
    OverworldEncounters_Toggle();
    assert(OverworldEncounters_Allowed() && timers == 1);
    blocked(&world); blocked(&inside); blocked(&pending); blocked(&safari);
    blocked(&pike); blocked(&pyramid); blocked(&link); blocked(&nativeLink);
    gMain.inBattle = 1; assert(!OverworldEncounters_Allowed()); gMain.inBattle = 0;
    gMapHeader.regionMapSectionId = 99; assert(!OverworldEncounters_Allowed());
    gMapHeader.regionMapSectionId = 0;
    gPlayerParty[5].fields[1] = 1; assert(!OverworldEncounters_Allowed());
    gPlayerParty[5].fields[1] = 0; gPlayerParty[5].fields[2] = 0;
    assert(!OverworldEncounters_Allowed()); gPlayerParty[5].fields[2] = 10;
    gSaveBlock1Ptr = NULL; assert(!OverworldEncounters_Allowed());
    gSaveBlock1Ptr = (void *)1; gSaveBlock2Ptr = NULL;
    assert(!OverworldEncounters_Allowed()); gSaveBlock2Ptr = (void *)1;
    assert(OverworldEncounters_Allowed());
    OverworldEncounters_Toggle();
    assert(!OverworldEncounters_Allowed() && despawns == 9);
    assert(timers == 9);
    return 0;
}
''')
            binary = p / 'policy'
            result = subprocess.run([
                'cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-DPORTABLE',
                '-I' + str(p), '-I' + str(ENGINE / 'include'),
                str(ENGINE / 'src/world/overworld_encounters.c'), str(p / 'test.c'),
                '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True)

    def test_spawn_and_battle_ownership_guards(self):
        source = (ENGINE / 'src/wild_encounter_ow.c').read_text()
        update = source.split('void UpdateOverworldWildEncounter(void)', 1)[1].split('\nbool32 IsOverworldWildEncounter', 1)[0]
        self.assertLess(update.index('!OverworldEncounters_Allowed()'), update.index('ShouldSpawnWaterOWE()'))
        self.assertIn('if (!ArePlayerFieldControlsLocked())\n            DespawnAllOverworldWildEncounters(OWE_GENERATED, 0);', update)
        start = source.split('void StartWildBattleWithOWE(', 1)[1].split('\nvoid SetOverworldObjectSpecies', 1)[0]
        self.assertLess(start.index('objEventId >= OBJECT_EVENTS_COUNT'), start.index('struct ObjectEvent *owe'))
        self.assertLess(start.index('!OverworldEncounters_Allowed()'), start.index('ZeroEnemyPartyMons()'))
        self.assertIn('StopScript(ctx);', start)
        trigger = source.split('void TryTriggerOverworldWildEncounter(', 1)[1].split('\nconst u8 *GetOverworlWildEncounterScript', 1)[0]
        self.assertLess(trigger.index('!OverworldEncounters_Allowed()'), trigger.index('gSpecialVar_LastTalked ='))
        self.assertIn('FlagGet(DN_FLAG_SEARCHING) || REPEL_STEP_COUNT', trigger)

    def test_defaults_save_and_menu(self):
        config = (ENGINE / 'include/config/wild_encounter.h').read_text()
        self.assertIn('#define WE_VANILLA_RANDOM           TRUE', config)
        self.assertIn('#else\n#define WE_OW_ENCOUNTERS                        FALSE', config)
        save = (ENGINE / 'src/load_save.c').read_text()
        self.assertIn('if (IsOverworldWildEncounter(&gObjectEvents[i], OWE_GENERATED))\n            gSaveBlock1Ptr->objectEvents[i].active = FALSE;', save)
        menu = (ENGINE / 'src/world/world_menu.c').read_text()
        self.assertIn('Visible encounters: OFF', menu)
        self.assertIn('OverworldEncounters_Enabled() ? NULL : OverworldEncounters_UnavailableReason()', menu)
        self.assertIn('Starts OFF each game launch.', menu)


if __name__ == '__main__':
    unittest.main()
