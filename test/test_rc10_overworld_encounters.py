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
            elif path and line == '':
                sources[path].append('')
        for entry in manifest['files']:
            content = '\n'.join(sources[entry['path']]) + '\n'
            if entry['path'] not in manifest.get('partial_context_files', []):
                assert hashlib.sha256(content.encode()).hexdigest() == entry['sha256']
            if 'EW_RC7_ENGINE' in os.environ:
                assert hashlib.sha256((ENGINE / entry['path']).read_bytes()).hexdigest() == entry['sha256']
            target = Path(cls.source_dir.name) / entry['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        if 'EW_RC7_ENGINE' not in os.environ:
            ENGINE = Path(cls.source_dir.name)

    @classmethod
    def tearDownClass(cls):
        cls.source_dir.cleanup()

    def test_world_actions_scroll_above_help(self):
        menu = (ENGINE / 'src/world/world_menu.c').read_text()
        start = menu.index('        unsigned first = selected >= 7')
        end = menu.index('        Wrap(&screen, 9,', start)
        loop = menu[start:end]
        source = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
struct Row {const char *label,*reason;};
struct Screen {unsigned calls, selected;};
static void Line(struct Screen *screen,unsigned row,const char *text){
 assert(row>=2 && row<9);screen->calls++;if(text[0]=='>')screen->selected++;
}
static void Draw(unsigned count,unsigned selected){
 struct Row rows[12]; struct Screen screen={0};char text[80];unsigned i;
 for(i=0;i<count;i++)rows[i]=(struct Row){"Action",NULL};
""" + loop + r"""
 assert(screen.calls<=7 && screen.selected==1);
}
int main(void){unsigned count,selected;
 for(count=1;count<=12;count++)for(selected=0;selected<count;selected++)Draw(count,selected);
 return 0;}
"""
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);(path/'scroll.c').write_text(source)
            subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(path/'scroll.c'),'-o',str(path/'scroll')],check=True)
            subprocess.run([str(path/'scroll')],check=True)

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
bool8 WorldBridge_Enabled(void), WorldBridge_ConnectionActive(void), GeneratedMap_IsInside(void), GeneratedMap_EntryPending(void);
int WorldActivity_OwnsFieldInput(void);
bool8 GetSafariZoneFlag(void), InBattlePike(void), IsOverworldLinkActive(void), NativeLink_IsActive(void);
unsigned CurrentBattlePyramidLocation(void);
#endif
''')
            for header in ['battle_pike.h', 'battle_pyramid.h', 'event_data.h',
                           'link.h', 'main.h', 'overworld.h', 'pokemon.h', 'safari_zone.h',
                           'platform/generated_map.h', 'platform/native_link.h',
                           'platform/world_bridge.h', 'platform/world_activity.h', 'constants/region_map_sections.h']:
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
static unsigned world, connected, busy, inside, pending, safari, pike, pyramid, link, nativeLink;
static unsigned timers, despawns;
unsigned GetMonData(struct Pokemon *p, unsigned field) { return p->fields[field]; }
bool8 WorldBridge_Enabled(void) { return world; }
bool8 WorldBridge_ConnectionActive(void) { return connected; }
int WorldActivity_OwnsFieldInput(void) { return busy; }
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
    blocked(&world); blocked(&busy);
    world = connected = 1;
    assert(OverworldEncounters_Allowed()); /* Authenticated personal encounters. */
    connected = 0; assert(!OverworldEncounters_Allowed()); /* Connection lost. */
    world = 0; assert(OverworldEncounters_Allowed()); /* Explicitly left world. */
    blocked(&inside); blocked(&pending); blocked(&safari);
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
    assert(!OverworldEncounters_Allowed() && despawns == 10);
    assert(timers == 10);
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

    def test_real_coop_transition_and_cleanup(self):
        # Compile the actual transition and despawn functions, not a Python model.
        from test.world.test_save_isolation import function
        activity = (ENGINE / 'src/world/world_activity.c').read_text()
        encounter = (ENGINE / 'src/wild_encounter_ow.c').read_text()
        start = function(activity, 'StartCoopBattle')
        cleanup = function(encounter, 'DespawnOWEOnBattleStart')
        token = encounter.split('static struct\n{', 1)[1].split('} sNativeOWEEncounter;', 1)[0]
        token = 'static struct\n{' + token + '} sNativeOWEEncounter;\n'
        token += function(encounter, 'ClearNativeOWEEncounter') + '\n'
        token += function(encounter, 'CaptureNativeOWEEncounter') + '\n'
        token += function(encounter, 'TakeNativeOWEEncounter') + '\n'
        preamble = r"""
#include <assert.h>
#include <stddef.h>
#include <string.h>
typedef unsigned char bool8;
typedef unsigned u32;
#define TRUE 1
#define FALSE 0
#define OBJECT_EVENTS_COUNT 4
#define LOCALID_NONE 0
#define OWE_ANY 0
#define OWE_MANUAL 1
struct ObjectEvent { unsigned active, wild, manual, localId, mapNum, mapGroup, graphicsId; };
static struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
static unsigned gSpecialVar_LastTalked, flags, cleared, timers, calls, prepared;
static unsigned owner, started, preparedOwner, sequence;
static struct { bool8 wildCaptured, encounterPending, trainerCaptured; } sActivity;
static bool8 LinkTransport_CoopOwner(void) { return owner; }
static void DexNavNative_PrepareNativeActivity(bool8 owns) {
    prepared++; preparedOwner = owns;
}
static int WorldCoop_StartBattle(bool8 owns) {
    assert(owns == owner); calls++; sequence = 1; return started;
}
static u32 __attribute__((unused)) GetObjectEventIdByLocalId(unsigned localId) {
    for (unsigned i = 0; i < OBJECT_EVENTS_COUNT; i++)
        if (gObjectEvents[i].active && gObjectEvents[i].localId == localId) return i;
    return OBJECT_EVENTS_COUNT;
}
static int IsOverworldWildEncounter(struct ObjectEvent *o, unsigned type) {
    assert(o >= gObjectEvents && o < gObjectEvents + OBJECT_EVENTS_COUNT);
    return o->active && o->wild && (type == OWE_ANY || o->manual);
}
static unsigned GetObjectEventFlagIdByLocalIdAndMap(unsigned id, unsigned n, unsigned g) {
    assert(id == 7 && n == 2 && g == 3); return 42;
}
static void FlagSet(unsigned flag) { assert(flag == 42); flags++; }
void ClearNativeOWEEncounter(struct ObjectEvent *object);
static void ClearObjectEvent(struct ObjectEvent *o) {
    ClearNativeOWEEncounter(o);
    assert(sequence == 1); cleared++; memset(o, 0, sizeof(*o));
}
static void SetNewOWESpawnCountdown(void) { timers++; }
"""
        body = r"""
int main(void) {
    // Random encounters, invalid IDs and ordinary NPCs cannot index/consume OWE.
    DespawnOWEOnBattleStart(); assert(!cleared && !flags && !timers);
    gSpecialVar_LastTalked = 65535; DespawnOWEOnBattleStart(); assert(!cleared);
    gObjectEvents[0] = (struct ObjectEvent){1,0,0,7,2,3,25};
    gSpecialVar_LastTalked = 7; DespawnOWEOnBattleStart(); assert(!cleared);
    gObjectEvents[0].wild = 1;
    // A random owner battle with stale LastTalked resolving to a REAL wild
    // object is not a visible encounter. Test generated AND authored objects.
    owner = started = 1;
    for (unsigned manual = 0; manual < 2; manual++) {
        gObjectEvents[0].manual = manual;
        sActivity.wildCaptured = sActivity.encounterPending = 1;
        assert(StartCoopBattle());
        assert(!cleared && !flags && !timers && gObjectEvents[0].active);
        assert(gSpecialVar_LastTalked == 7);
    }
    gObjectEvents[0].manual = 0;
    started = 0;
    CaptureNativeOWEEncounter(&gObjectEvents[0]);
    // Failed native start preserves the selected wild object and fallback flags.
    owner = 1; sActivity.wildCaptured = sActivity.encounterPending = 1;
    assert(!StartCoopBattle());
    assert(!cleared && gSpecialVar_LastTalked == 7 && sActivity.wildCaptured);
    assert(sActivity.encounterPending && preparedOwner);
    // Guest starts may have a locally selected object. Never consume it.
    owner = 0; started = 1;
    assert(StartCoopBattle());
    assert(!cleared && !sActivity.encounterPending && !sActivity.wildCaptured);
    assert(!preparedOwner);
    DespawnOWEOnBattleStart(); assert(!cleared); /* Guest discarded old token. */
    // Trainer owners do not consume the wild object either.
    CaptureNativeOWEEncounter(&gObjectEvents[0]);
    owner = 1; sActivity.trainerCaptured = sActivity.encounterPending = 1;
    assert(StartCoopBattle()); assert(!cleared && !sActivity.trainerCaptured);
    assert(!preparedOwner);
    DespawnOWEOnBattleStart(); assert(!cleared); /* Trainer discarded old token. */
    // Successful owner wild start consumes exactly its explicitly armed object.
    CaptureNativeOWEEncounter(&gObjectEvents[0]);
    sActivity.wildCaptured = sActivity.encounterPending = 1;
    assert(StartCoopBattle());
    assert(cleared == 1 && timers == 1 && !flags && preparedOwner);
    assert(!gObjectEvents[0].active && gSpecialVar_LastTalked == LOCALID_NONE);
    assert(!sActivity.wildCaptured && !sActivity.encounterPending);
    DespawnOWEOnBattleStart(); assert(cleared == 1 && timers == 1);
    // Authored encounters retain Expansion's flag semantics on the owner only.
    gObjectEvents[0] = (struct ObjectEvent){1,1,1,7,2,3,25};
    gSpecialVar_LastTalked = 7; sActivity.wildCaptured = 1;
    CaptureNativeOWEEncounter(&gObjectEvents[0]);
    assert(StartCoopBattle()); assert(cleared == 2 && flags == 1 && timers == 2);
    assert(calls == 7 && prepared == 7);
    // Removal/reuse with IDENTICAL identity invalidates the previous token.
    gObjectEvents[0] = (struct ObjectEvent){1,1,0,7,2,3,25};
    CaptureNativeOWEEncounter(&gObjectEvents[0]);
    ClearNativeOWEEncounter(&gObjectEvents[0]);
    gObjectEvents[0] = (struct ObjectEvent){1,1,0,7,2,3,25};
    DespawnOWEOnBattleStart(); assert(cleared == 2 && gObjectEvents[0].active);
    // Map/species/local-ID drift cannot consume a different identity.
    CaptureNativeOWEEncounter(&gObjectEvents[0]);
    gObjectEvents[0].mapGroup++;
    DespawnOWEOnBattleStart(); assert(cleared == 2);
    CaptureNativeOWEEncounter(&gObjectEvents[0]);
    gObjectEvents[0].graphicsId++;
    DespawnOWEOnBattleStart(); assert(cleared == 2);
    CaptureNativeOWEEncounter(&gObjectEvents[0]);
    gObjectEvents[0].localId++;
    DespawnOWEOnBattleStart(); assert(cleared == 2);
    // Abort/load invalidates even an otherwise exact matching token.
    CaptureNativeOWEEncounter(&gObjectEvents[0]);
    ClearNativeOWEEncounter(NULL);
    DespawnOWEOnBattleStart(); assert(cleared == 2);
    // The identity does not depend on ambient LastTalked, nor clear another ID.
    CaptureNativeOWEEncounter(&gObjectEvents[0]);
    gSpecialVar_LastTalked = 99;
    DespawnOWEOnBattleStart(); assert(cleared == 3 && gSpecialVar_LastTalked == 99);
    // Failed co-op startup still allows the normal battle transition to consume
    // the original token. Clearing a different object's slot cannot revoke it.
    gObjectEvents[0] = (struct ObjectEvent){1,1,0,7,2,3,25};
    CaptureNativeOWEEncounter(&gObjectEvents[0]);
    ClearNativeOWEEncounter(&gObjectEvents[1]);
    sActivity.wildCaptured = sActivity.encounterPending = 1; started = 0;
    assert(!StartCoopBattle());
    DespawnOWEOnBattleStart(); assert(cleared == 4 && flags == 1 && timers == 4);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            source = p / 'transition.c'
            source.write_text(preamble + token + cleanup + '\n' + start + body)
            binary = p / 'transition'
            build = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                                    '-fsanitize=undefined', '-fno-sanitize-recover=all',
                                    '-DPORTABLE', str(source), '-o', str(binary)],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            subprocess.run([str(binary)], check=True)
        self.assertIn('if (!StartCoopBattle())\n            { Stop("tagged battle unavailable"); return; }', activity)
        self.assertIn('ClearNativeOWEEncounter(objectEvent);',
                      (ENGINE / 'src/event_object_movement.c').read_text())
        self.assertIn('ClearNativeOWEEncounter(owe);', function(encounter, 'OnOverworldWildEncounterDespawn'))
        self.assertIn('ClearNativeOWEEncounter(NULL);', function(activity, 'WorldActivity_ReturnToField'))
        self.assertIn('ClearNativeOWEEncounter(NULL);',
                      function((ENGINE / 'src/load_save.c').read_text(), 'LoadObjectEvents'))
        self.assertIn('CaptureNativeOWEEncounter(owe);', function(encounter, 'StartWildBattleWithOWE'))


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
        self.assertIn('Starts OFF each launch.', menu)


if __name__ == '__main__':
    unittest.main()
