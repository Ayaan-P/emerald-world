"""Executable serialization-boundary regressions; never builds the full game.

Compile the actual save/bridge function bodies against a small engine fixture.
This exercises synchronous save/reload without a frame-cleanup opportunity, but
is not a substitute for a rebuilt native client's end-to-end acceptance test.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def function(source, name):
    """Extract a definition, retaining its preprocessor branches verbatim."""
    match = re.search(r"^(?:static )?[\w *]+\b" + name + r"\([^;\n]*\)\n\{", source, re.M)
    if not match:
        raise AssertionError(f"missing function definition: {name}")
    start = source.index("{", match.start())
    depth = 1
    end = start + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end] + "\n"


PREAMBLE = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef int32_t s32;
typedef u8 bool8;
#define TRUE 1
#define FALSE 0
#define WB_PEERS 8
#define WB_TRAVEL_PEERS 63
#define WB_OBJECTS 8
#define WB_REMOTES (WB_PEERS + WB_OBJECTS)
#define WB_TILES 128
#define WB_BUFFER 65536
#define WB_LOCALID 224
#define WB_MARKER 0x5742
#define SAVED_OBJECT_EVENTS_COUNT 16
#ifdef PORTABLE
#define OBJECT_EVENTS_COUNT 64
#define MAX_SPRITES 128
#else
#define OBJECT_EVENTS_COUNT SAVED_OBJECT_EVENTS_COUNT
#define MAX_SPRITES 64
#endif
#define OBJECT_EVENT_TEMPLATES_COUNT 64
#define LOCALID_PLAYER 255
#define LOCALID_NONE 0
#define PYRAMID_LOCATION_NONE 0
#define HILL_TRAINERS_PER_FLOOR 2
#define MAP_OFFSET 7
#define MAP_OFFSET_W 15
#define MAP_OFFSET_H 14
struct ObjectEvent { u8 active, isPlayer, localId, mapGroup, mapNum, spriteId, graphicsId; int scriptState; };
struct ObjectEventTemplate { u8 localId; };
struct SpriteFrameImage { unsigned size; };
struct Sprite { u8 inUse; short data[8]; const struct SpriteFrameImage *images; };
struct Graphics { unsigned size; };
struct MapLayout { int width, height; };
struct SaveBlock {
    struct ObjectEvent objectEvents[SAVED_OBJECT_EVENTS_COUNT];
    u16 mapView[MAP_OFFSET_W * MAP_OFFSET_H];
    struct ObjectEventTemplate objectEventTemplates[OBJECT_EVENT_TEMPLATES_COUNT];
    struct { int x, y; } pos;
    struct { int mapGroup, mapNum; } location;
};
static struct SaveBlock save;
static struct SaveBlock *gSaveBlock1Ptr = &save;
static struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
static struct Sprite gSprites[MAX_SPRITES];
static u16 sBackupMapData[32 * 32];
static struct { u16 *map; int width, height; } gBackupMapLayout;
struct MapEvents { u8 objectEventCount; const struct ObjectEventTemplate *objectEvents; };
struct MapHeader { const struct MapLayout *mapLayout; const struct MapEvents *events; };
static struct MapHeader gMapHeader;
static const struct MapEvents events = {2, save.objectEventTemplates};
static const struct MapHeader *Overworld_GetMapHeaderByGroupAndId(u8 group, u8 num) {
    return group == 0 && num == 9 ? &gMapHeader : NULL;
}
static u8 CurrentBattlePyramidLocation(void) { return PYRAMID_LOCATION_NONE; }
static u8 GetNumBattlePyramidObjectEvents(void) { return 0; }
static bool8 InTrainerHill(void) { return FALSE; }
static const struct MapLayout layout = {18, 18};
static int overworld = 1;
static int draws;
static bool8 Overworld(void) { return overworld; }
static const struct Graphics *GetObjectEventGraphicsInfo(u8 id) {
    static const struct Graphics info = {32}; (void)id; return &info;
}
static void DestroySprite(struct Sprite *sprite) { sprite->inUse = FALSE; }
static void RemoveObjectEventByLocalIdAndMap(u8 id, u8 num, u8 group) {
    /* Dynamic peers have no map template; UBFIX resolves their flag to zero. */
    unsigned i;
    for (i = 0; i < OBJECT_EVENTS_COUNT; i++)
        if (gObjectEvents[i].localId == id && gObjectEvents[i].mapNum == num
            && gObjectEvents[i].mapGroup == group) {
            DestroySprite(&gSprites[gObjectEvents[i].spriteId]);
            gObjectEvents[i].active = FALSE;
        }
}
static void MapGridSetMetatileEntryAt(s32 x, s32 y, u16 value) {
    gBackupMapLayout.map[y * gBackupMapLayout.width + x] = value;
}
static void CurrentMapDrawMetatileAt(s32 x, s32 y) { (void)x; (void)y; draws++; }
'''

SETUP = r'''
static void Setup(void) {
    memset(&save, 0, sizeof(save));
    memset(gObjectEvents, 0, sizeof(gObjectEvents));
    memset(gSprites, 0, sizeof(gSprites));
    memset(&sWorld, 0, sizeof(sWorld));
    memset(sBackupMapData, 0, sizeof(sBackupMapData));
    sWorld.enabled = TRUE;
    gMapHeader.mapLayout = &layout;
    gMapHeader.events = &events;
    save.objectEventTemplates[0].localId = 1;
    save.objectEventTemplates[1].localId = 2;
    gBackupMapLayout.map = sBackupMapData;
    gBackupMapLayout.width = gBackupMapLayout.height = 32;
    save.location.mapGroup = sWorld.group = 0;
    save.location.mapNum = sWorld.num = 9;
    sWorld.layout = &layout;
    sWorld.grid = sBackupMapData;
    sWorld.tilesLive = TRUE;
    gObjectEvents[0] = (struct ObjectEvent){1, 1, 255, 0, 9, 0, 0, 91};
    gObjectEvents[1] = (struct ObjectEvent){1, 0, 1, 0, 9, 1, 0, 73};
    gObjectEvents[2] = (struct ObjectEvent){1, 0, WB_LOCALID, 0, 9, 2, 0, 0};
    strcpy(sWorld.remotes[0].id, "bob");
    sWorld.remotes[0].object = sWorld.remotes[0].sprite = 2;
    sWorld.remotes[0].num = 9;
    gSprites[2].inUse = TRUE;
    gSprites[2].data[0] = 2;
    gSprites[2].data[7] = WB_MARKER;
    sWorld.appliedCount = 1;
    sWorld.applied[0].tile.x = sWorld.applied[0].tile.y = 1;
    sWorld.applied[0].original = 0x302a;
    sWorld.applied[0].raw = 0x3c01;
    sBackupMapData[8 * 32 + 8] = 0x3c01;
}
static void RoundTrip(void) {
    struct SaveBlock disk;
    FILE *file = tmpfile();
    assert(file);
    assert(fwrite(&save, sizeof(save), 1, file) == 1);
    rewind(file);
    assert(fread(&disk, sizeof(disk), 1, file) == 1);
    fclose(file);
    memset(&save, 0, sizeof(save));
    save = disk;
    memset(gObjectEvents, 0, sizeof(gObjectEvents));
    LoadObjectEvents();
}
'''


class SaveIsolation(unittest.TestCase):
    def compile_and_run(self, body, portable=True, ubfix=True):
        bridge = (ROOT / "src/platform/world_bridge.c").read_text()
        load = (ROOT / "src/load_save.c").read_text()
        field = (ROOT / "src/fieldmap.c").read_text()
        # Use the real bridge state declarations, not a reimplementation.
        state = bridge[bridge.index("struct Peer {"):bridge.index("static bool8 Identifier(")]
        helpers = "".join(function(bridge, name) for name in
                          ("Owned", "RemoveRemote", "SameGrid", "GridCoords", "Raw",
                           "RestoreTiles", "WorldBridge_PrepareSave"))
        movement = (ROOT / "src/event_object_movement.c").read_text()
        saves = function(movement, "FindObjectEventTemplateByLocalId")
        saves += function(movement, "ObjectEventIsPersistent")
        saves += function(load, "SaveObjectEvents") + function(load, "LoadObjectEvents")
        saves += function(field, "SaveMapView")
        rally = (ROOT / "include/platform/world_rally.h").read_text()
        rally_types = rally[rally.index("#define WORLD_RALLY_ROSTER"):rally.index("/* Main/game thread only.")]
        source = PREAMBLE + rally_types + state + helpers + saves + SETUP
        source += "int main(void) { Setup();\n" + body + "\nreturn 0; }\n"
        with tempfile.TemporaryDirectory(prefix="emerald-save-isolation-") as tmp:
            cfile = Path(tmp) / "boundary.c"
            binary = Path(tmp) / "boundary"
            cfile.write_text(source)
            compiler = shutil.which("cc")
            if compiler is None:
                self.fail("C compiler required for executable boundary regression")
            flags = (["-DPORTABLE"] if portable else []) + (["-DUBFIX"] if ubfix else [])
            compiled = subprocess.run([compiler, "-std=gnu99", "-Wall", "-Wextra",
                                       "-Wno-unused-function", "-Werror", *flags,
                                       str(cfile), "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_portable_includes_are_guarded(self):
        for name in ("src/load_save.c", "src/fieldmap.c"):
            source = (ROOT / name).read_text()
            self.assertRegex(source, r'#ifdef PORTABLE\s+#include "platform/world_bridge.h"')

    def test_private_script_changes_and_reused_npc_slots_survive_cleanup(self):
        self.compile_and_run(r'''
    struct ObjectEvent npc;
    /* The engine reused the remote slot: the sprite marker no longer matches. */
    gSprites[2].data[7] = 0;
    gObjectEvents[2].localId = 2; /* Reallocated to an actual campaign identity. */
    gObjectEvents[2].scriptState = 123;
    npc = gObjectEvents[2];
    /* A script has superseded the overlay since its application. */
    sBackupMapData[8 * 32 + 8] = 0x7055;
    SaveMapView();
    SaveObjectEvents();
    RoundTrip();
    assert(save.mapView[8 * MAP_OFFSET_W + 8] == 0x7055);
    assert(memcmp(&npc, &gObjectEvents[2], sizeof(npc)) == 0);
    /* Saving twice must not restore an overlay or remove unrelated objects. */
    SaveObjectEvents();
    SaveMapView();
    assert(save.mapView[8 * MAP_OFFSET_W + 8] == 0x7055);
''')

    def test_cleanup_does_not_restore_tiles_into_a_different_map(self):
        self.compile_and_run(r'''
    save.location.mapNum = 10;
    sBackupMapData[8 * 32 + 8] = 0x6077;
    SaveMapView();
    assert(save.mapView[8 * MAP_OFFSET_W + 8] == 0x6077);
''')

    def test_disabled_world_still_filters_transients_only_on_portable(self):
        for portable in (True, False):
            with self.subTest(portable=portable):
                self.compile_and_run(r'''
    struct ObjectEvent objects[OBJECT_EVENTS_COUNT];
    memcpy(objects, gObjectEvents, sizeof(objects));
    sWorld.enabled = FALSE;
    SaveObjectEvents();
    SaveMapView();
    RoundTrip();
#ifdef PORTABLE
    assert(memcmp(objects, gObjectEvents, 2 * sizeof(objects[0])) == 0);
    assert(!gObjectEvents[2].active);
#else
    assert(memcmp(objects, gObjectEvents, sizeof(objects)) == 0);
#endif
    assert(save.mapView[8 * MAP_OFFSET_W + 8] == 0x3c01);
''', portable=portable)
        # A nonportable build must not call the bridge even if its fixture is enabled.
        self.compile_and_run(r'''
    SaveObjectEvents();
    SaveMapView();
    assert(save.objectEvents[2].active);
    assert(save.mapView[8 * MAP_OFFSET_W + 8] == 0x3c01);
''', portable=False)

    def test_map_save_strips_overlay_before_copy_and_reload(self):
        self.compile_and_run(r'''
    SaveMapView();
    RoundTrip();
    memset(sBackupMapData, 0, sizeof(sBackupMapData));
    /* Reload the saved view without any connection or overlay reapplication. */
    assert(save.mapView[8 * MAP_OFFSET_W + 8] == 0x302a);
    assert(!sWorld.tilesLive);
    assert(sWorld.appliedCount == 0);
''')

    def test_serialization_during_non_overworld_warp_excludes_owned_peer(self):
        self.compile_and_run(r'''
    overworld = 0;
    SaveObjectEvents();
    RoundTrip();
    assert(!gObjectEvents[2].active);
    assert(!save.objectEvents[2].active);
    assert(gObjectEvents[0].active && gObjectEvents[1].active);
''')

    def test_shared_npc_upper_remote_slot_is_stripped_from_save(self):
        for ubfix in (True, False):
            with self.subTest(ubfix=ubfix):
                self.compile_and_run(r'''
    /* Shared objects can occupy remote slots beyond the original eight peers. */
    sWorld.remotes[12] = sWorld.remotes[0];
    memset(&sWorld.remotes[0], 0, sizeof(sWorld.remotes[0]));
    strcpy(sWorld.remotes[12].id, "@guide");
    gObjectEvents[2].localId = WB_LOCALID + 12;
    overworld = 0;
    SaveObjectEvents();
    RoundTrip();
    assert(!gObjectEvents[2].active);
    assert(!save.objectEvents[2].active);
    assert(gObjectEvents[0].active && gObjectEvents[1].active);
''', ubfix=ubfix)

    def test_object_save_strips_peer_before_synchronous_copy_and_reload(self):
        for ubfix in (True, False):
            with self.subTest(ubfix=ubfix):
                self.compile_and_run(r'''
    struct ObjectEvent player = gObjectEvents[0], npc = gObjectEvents[1];
    /* Direct save: no BeforeFrame/AfterFrame, as in the synchronous gym warp. */
    SaveObjectEvents();
    RoundTrip();
    assert(!gObjectEvents[2].active);
    assert(memcmp(&player, &gObjectEvents[0], sizeof(player)) == 0);
    assert(memcmp(&npc, &gObjectEvents[1], sizeof(npc)) == 0);
''', ubfix=ubfix)


if __name__ == "__main__":
    unittest.main()
