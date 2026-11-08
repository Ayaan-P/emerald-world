"""Compile upstream encounters and execute the real map lookup, without a game server."""
import importlib.util
import io
import json
from pathlib import Path
from test.test_rc9_kanto_content import KantoContent, ENGINE


class KantoEncounters(KantoContent):
    def test_combined_upstream_encounters_and_actual_lookup(self):
        path = ENGINE / 'tools/wild_encounters/wild_encounters_to_header.py'
        spec = importlib.util.spec_from_file_location('wild_encounters', path)
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        data = json.loads((ENGINE / 'src/data/wild_encounters.json').read_text())
        config = generator.Config(str(ENGINE / 'include/config/overworld.h'),
                                  str(ENGINE / 'include/constants/rtc.h'), data)
        output = io.StringIO()
        assembler = generator.WildEncounterAssembler(output, data, config)
        assembler.WriteHeader()
        assembler.WriteMacros()
        assembler.WriteEncounters()
        (self.generated / 'data').mkdir(exist_ok=True)
        (self.generated / 'data/wild_encounters.h').write_text(output.getvalue())
        self.run_command([str(self.directory / 'jsonproc'), 'src/data/wild_encounters.json',
                          'src/data/wild_encounters.constants.json.txt',
                          str(self.constants / 'wild_encounter.h')])
        actual = (ENGINE / 'src/wild_encounter.c').read_text()
        start = actual.index('u16 GetCurrentMapWildMonHeaderId(void)')
        end = actual.index('\n}', start) + 2
        source = self.directory / 'encounters.c'
        source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include "global.h"
#include "event_data.h"
#include "include/wild_encounter.h"
#include "constants/map_groups.h"
#include "constants/maps.h"
#include "data/wild_encounters.h"
static struct SaveBlock1 save;
struct SaveBlock1 *gSaveBlock1Ptr = &save;
u16 VarGet(u16 id) { assert(id == VAR_ALTERING_CAVE_WILD_SET); return 0; }
''' + actual[start:end] + r'''
static void Check(unsigned map, bool8 expected)
{
    save.location.mapGroup = MAP_GROUP(map);
    save.location.mapNum = MAP_NUM(map);
    u16 id = GetCurrentMapWildMonHeaderId();
    assert((id != HEADER_NONE) == expected);
    if (expected) {
        assert(gWildMonHeaders[id].mapGroup == MAP_GROUP(map));
        assert(gWildMonHeaders[id].mapNum == MAP_NUM(map));
    }
}
int main(void)
{
    Check(MAP_ROUTE101, !IS_FRLG);
    Check(MAP_ROUTE1, IS_FRLG || EW_KANTO_CONTENT);
    Check(MAP_VIRIDIAN_FOREST, IS_FRLG || EW_KANTO_CONTENT);
    Check(MAP_UNDEFINED, FALSE);
    for (unsigned i = 0; gWildMonHeaders[i].mapGroup != MAP_GROUP(MAP_UNDEFINED); i++) {
        const struct WildPokemonHeader *h = &gWildMonHeaders[i];
        printf("%u:%u", h->mapGroup, h->mapNum);
        for (unsigned t = 0; t < TIMES_OF_DAY_COUNT; t++) {
            const struct WildPokemonInfo *info[] = {h->encounterTypes[t].landMonsInfo,
                h->encounterTypes[t].waterMonsInfo, h->encounterTypes[t].rockSmashMonsInfo,
                h->encounterTypes[t].fishingMonsInfo, h->encounterTypes[t].hiddenMonsInfo};
            const unsigned counts[] = {NUM_LAND_MONS_ENCOUNTER_SLOTS, NUM_WATER_MONS_ENCOUNTER_SLOTS, NUM_ROCK_SMASH_MONS_ENCOUNTER_SLOTS,
                NUM_FISHING_MONS_ENCOUNTER_SLOTS, NUM_HIDDEN_MONS_ENCOUNTER_SLOTS};
            for (unsigned k = 0; k < ARRAY_COUNT(info); k++) {
                printf(" %u", info[k] ? info[k]->encounterRate : 0);
                if (info[k]) for (unsigned m = 0; m < counts[k]; m++) {
                    const struct WildPokemon *mon = &info[k]->wildPokemon[m];
                    printf("/%u,%u,%u", mon->species, mon->minLevel, mon->maxLevel);
                }
            }
        }
        putchar('\n');
    }
    return 0;
}
''')
        outputs = {}
        for version, enabled in (('EMERALD', 0), ('EMERALD', 1), ('FIRERED', 0), ('LEAFGREEN', 0)):
            binary = self.directory / f'encounters-{version}-{enabled}'
            flags = [f for f in self.flags if f != '-DEMERALD']
            self.run_command(['gcc', *flags, f'-D{version}', f'-DEW_REGION_STATE={enabled}',
                              f'-DEW_KANTO_CONTENT={enabled}', *self.game_includes,
                              str(source), '-o', str(binary)])
            outputs[version, enabled] = self.run_command([str(binary)]).splitlines()
        hoenn, kanto = outputs['EMERALD', 0], outputs['FIRERED', 0]
        combined = outputs['EMERALD', 1]
        # No copied tables, altered species/levels, duplicate LeafGreen cohort,
        # or dropped Hoenn entries. Compare every generated encounter slot.
        self.assertEqual(combined, [line for line in combined if line in hoenn]
                         + [line for line in combined if line in kanto])
        self.assertEqual([line for line in combined if line in hoenn], hoenn)
        self.assertEqual([line for line in combined if line in kanto], kanto)
        self.assertEqual(len(combined), len(hoenn) + len(kanto))
        self.assertNotEqual(kanto, outputs['LEAFGREEN', 0])
    def test_actual_layout_aware_travel_safety(self):
        from world.build_catalog import build_catalog, render_layout_header
        import re
        import struct
        self.run_command([str(self.directory / 'jsonproc'), 'src/data/wild_encounters.json',
                          'src/data/wild_encounters.constants.json.txt',
                          str(self.constants / 'wild_encounter.h')])
        catalog = build_catalog(ENGINE, layout_aware=True)
        self.assertEqual((ENGINE / 'include/platform/world_catalog.h').read_text(), render_layout_header(catalog))
        layouts = {x['id']: x for x in json.loads((ENGINE / 'data/layouts/layouts.json').read_text())['layouts']}
        arrays = dict(re.findall(r'const u16 (\w+)\[\] = INCBIN_U16\("([^"]+)"\);',
                                 (ENGINE / 'src/data/tilesets/metatiles.h').read_text()))
        tilesets = dict(re.findall(r'const struct Tileset (\w+)\s*=\s*\{(.*?)\};',
                                   (ENGINE / 'src/data/tilesets/headers.h').read_text(), re.S))
        fixtures = []
        for number, name in enumerate(('PalletTown_Frlg', 'SlateportCity')):
            m = json.loads((ENGINE / f'data/maps/{name}/map.json').read_text())
            layout = layouts[m['layout']]
            frlg = layout.get('layout_version') == 'frlg'
            def array(symbol, path, kind):
                data = (ENGINE / path).read_bytes()
                fmt = '<' + ('I' if kind == 'u32' else 'H') * (len(data) // (4 if kind == 'u32' else 2))
                fixtures.append(f'static const {kind} {symbol}[] = {{' + ','.join(map(str, struct.unpack(fmt, data))) + '};')
            array(f'map{number}', layout['blockdata_filepath'], 'u16')
            for field in ('primary', 'secondary'):
                name = layout[f'{field}_tileset']
                symbol = re.search(r'\.metatileAttributes\s*=\s*(\w+)', tilesets[name])[1]
                array(f'attr{number}{field}', arrays[symbol], 'u32' if frlg else 'u16')
                fixtures.append(f'static const struct Tileset tiles{number}{field} = {{.metatileAttributes=(const u16 *)attr{number}{field}}};')
            fixtures.append(f'static const struct MapLayout layout{number} = {{.width={layout["width"]}, .height={layout["height"]}, .isFrlg={int(frlg)}, .map=map{number}, .primaryTileset=&tiles{number}primary, .secondaryTileset=&tiles{number}secondary}};')
            for kind, ctype, fields in (
                    ('warp', 'WarpEvent', ('x', 'y')),
                    ('coord', 'CoordEvent', ('x', 'y')),
                    ('object', 'ObjectEventTemplate', ('x', 'y'))):
                rows = []
                for event in m[f'{kind}_events']:
                    values = [f'.{key}={event[key]}' for key in fields]
                    if kind == 'object':
                        values += [f'.movementRangeX={event.get("movement_range_x", 0)}',
                                   f'.movementRangeY={event.get("movement_range_y", 0)}', f'.flagId={event["flag"]}']
                    rows.append('{' + ','.join(values) + '}')
                fixtures.append(f'static const struct {ctype} {kind}{number}[] = {{' + ','.join(rows) + '};')
            fixtures.append(f'static const struct MapEvents events{number} = {{.warpCount=ARRAY_COUNT(warp{number}), .warps=warp{number}, .coordEventCount=ARRAY_COUNT(coord{number}), .coordEvents=coord{number}, .objectEventCount=ARRAY_COUNT(object{number}), .objectEvents=object{number}}};')
            fixtures.append(f'static const struct MapHeader header{number} = {{.mapLayout=&layout{number}, .events=&events{number}}};')
        (self.generated / 'travel_fixtures.h').write_text('\n'.join(fixtures) + '\n')
        source = self.directory / 'travel.c'
        source.write_text(r'''
#include <assert.h>
#include "global.h"
#include "src/fieldmap.c"
#include "src/world/world_travel.c"
#include "src/event_data.c"
#include "travel_fixtures.h"
static struct SaveBlock1 save;
struct SaveBlock1 *gSaveBlock1Ptr = &save;
struct MapHeader gMapHeader;
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];

u16 *const gSpecialVars[22] = {0};
struct Main gMain;
struct PaletteFadeControl gPaletteFade;
struct PlayerAvatar gPlayerAvatar;
struct Task gTasks[NUM_TASKS];
u8 gWirelessCommType;
u8 gPartiesCount[MAX_BATTLE_TRAINERS];
struct Pokemon gParties[MAX_BATTLE_TRAINERS][PARTY_SIZE];
static bool8 connected, locked, scriptActive, anchor, healthy = TRUE, onFoot = TRUE;
static int linkActive, activityActive;
static unsigned warps, targetGroup, targetNum, targetX, targetY;
void CB1_Overworld(void) {}
void CB2_Overworld(void) {}
bool8 WorldBridge_Enabled(void) { return connected; }
int NativeLink_IsActive(void) { return linkActive; }
int WorldActivity_OwnsFieldInput(void) { return activityActive; }
bool8 ScriptContext_IsEnabled(void) { return scriptActive; }
bool8 ArePlayerFieldControlsLocked(void) { return locked; }
bool32 IsOverworldLinkActive(void) { return FALSE; }
bool8 WorldRally_HasReturn(void) { return anchor; }
bool8 WorldRally_GetSnapshot(struct WorldRallySnapshot *out) { memset(out, 0, sizeof *out); return FALSE; }
u8 TestPlayerAvatarFlags(u8 flag) { assert(flag == PLAYER_AVATAR_FLAG_ON_FOOT); return onFoot; }
u32 GetMonData2(struct Pokemon *mon, s32 field)
{ (void)mon; return field == MON_DATA_IS_EGG ? 0 : healthy; }
void SetWarpDestination(s8 group, s8 num, s8 warpId, s8 x, s8 y)
{ assert(warpId == WARP_ID_NONE); targetGroup=group; targetNum=num; targetX=x; targetY=y; }
void DoWarp(void) { warps++; locked=TRUE; }

bool8 WorldBridge_TravelTileClear(unsigned group, unsigned num, unsigned x, unsigned y)
{ (void)group; (void)num; (void)x; (void)y; return TRUE; }
struct MapHeader const *const Overworld_GetMapHeaderByGroupAndId(u16 group, u16 num)
{
    if (group == MAP_GROUP(MAP_PALLET_TOWN) && num == MAP_NUM(MAP_PALLET_TOWN)) return &header0;
    if (group == MAP_GROUP(MAP_SLATEPORT_CITY) && num == MAP_NUM(MAP_SLATEPORT_CITY)) return &header1;
    return NULL;
}
int main(void)
{
    save.location.mapGroup = 127; /* destination is not the currently loaded map */
    save.location.mapNum = 127;
    assert(WorldTravel_RallyTileSafe(MAP_GROUP(MAP_PALLET_TOWN), MAP_NUM(MAP_PALLET_TOWN), 6, 8, ELEVATION_DEFAULT, FALSE));
    assert(WorldTravel_RallyTileSafe(MAP_GROUP(MAP_SLATEPORT_CITY), MAP_NUM(MAP_SLATEPORT_CITY), 19, 20, ELEVATION_DEFAULT, FALSE));
    assert(!WorldTravel_RallyTileSafe(MAP_GROUP(MAP_PALLET_TOWN), MAP_NUM(MAP_PALLET_TOWN), 6, 7, ELEVATION_DEFAULT, FALSE)); /* door */
    assert(!WorldTravel_RallyTileSafe(MAP_GROUP(MAP_PALLET_TOWN), MAP_NUM(MAP_PALLET_TOWN), 12, 1, ELEVATION_DEFAULT, FALSE)); /* story trigger */
    assert(!WorldTravel_RallyTileSafe(MAP_GROUP(MAP_PALLET_TOWN), MAP_NUM(MAP_PALLET_TOWN), 24, 8, ELEVATION_DEFAULT, FALSE));
    assert(!WorldTravel_RallyTileSafe(127, 127, 1, 1, ELEVATION_DEFAULT, FALSE));
    assert(!WorldTravel_RallyTileSafe(MAP_GROUP(MAP_PALLET_TOWN), MAP_NUM(MAP_PALLET_TOWN), 6, 8, 0, FALSE));
    u32 behavior;
    assert(TravelMetatileBehavior(&layout0, MAP_GROUP(MAP_PALLET_TOWN), MAP_NUM(MAP_PALLET_TOWN), 639, &behavior));
    assert(TravelMetatileBehavior(&layout0, MAP_GROUP(MAP_PALLET_TOWN), MAP_NUM(MAP_PALLET_TOWN), 640, &behavior));
    assert(!TravelMetatileBehavior(&layout0, MAP_GROUP(MAP_PALLET_TOWN), MAP_NUM(MAP_PALLET_TOWN), 640 + 89, &behavior));
    assert(!TravelMetatileBehavior(&layout1, MAP_GROUP(MAP_PALLET_TOWN), MAP_NUM(MAP_PALLET_TOWN), 1, &behavior));
    assert(!SafeFloor(PACK_ELEVATION(ELEVATION_DEFAULT), 0x100)); /* 9-bit FRLG behavior must not truncate to NORMAL */

    /* Exercise the production route admission and warp handoff. Only the
     * field/UI adapters and final animation task are substituted. */
    InitEventData();
    save.location.mapGroup = MAP_GROUP(MAP_SLATEPORT_CITY);
    save.location.mapNum = MAP_NUM(MAP_SLATEPORT_CITY);
    gMain.callback1 = CB1_Overworld;
    gMain.callback2 = CB2_Overworld;
    gPartiesCount[B_TRAINER_PLAYER] = 1;
    assert(WorldTravel_RegionReason()); /* own visited flag required */
    assert(!WorldTravel_VisitRegion());
    FlagSet(FLAG_VISITED_SLATEPORT_CITY);
    VarSet(VAR_LITTLEROOT_TOWN_STATE, 9);
    VarSet(VAR_MAP_SCENE_PALLET_TOWN_OAK, 7);
    const struct SaveBlock1 before = save;
    assert(!WorldTravel_RegionReason());
    connected=TRUE; assert(!WorldTravel_VisitRegion()); connected=FALSE;
    anchor=TRUE; assert(!WorldTravel_VisitRegion()); anchor=FALSE;
    scriptActive=TRUE; assert(!WorldTravel_VisitRegion()); scriptActive=FALSE;
    linkActive=TRUE; assert(!WorldTravel_VisitRegion()); linkActive=FALSE;
    activityActive=TRUE; assert(!WorldTravel_VisitRegion()); activityActive=FALSE;
    healthy=FALSE; assert(!WorldTravel_VisitRegion()); healthy=TRUE;
    onFoot=FALSE; assert(!WorldTravel_VisitRegion()); onFoot=TRUE;
    for (unsigned i=0; i<NUM_TASKS; i++) gTasks[i].isActive=TRUE;
    assert(!WorldTravel_VisitRegion());
    memset(gTasks, 0, sizeof gTasks);
    assert(warps == 0);
    assert(WorldTravel_VisitRegion());
    assert(warps == 1 && targetGroup == MAP_GROUP(MAP_PALLET_TOWN)
        && targetNum == MAP_NUM(MAP_PALLET_TOWN) && targetX == 6 && targetY == 8);
    assert(!WorldTravel_VisitRegion()); /* the warp owns field controls */
    assert(memcmp(&before, &save, sizeof save) == 0);
    assert(VarGet(VAR_MAP_SCENE_PALLET_TOWN_OAK) == 7);
    locked=FALSE;
    save.location.mapGroup = MAP_GROUP(MAP_PALLET_TOWN);
    save.location.mapNum = MAP_NUM(MAP_PALLET_TOWN);
    assert(WorldTravel_VisitRegion());
    assert(warps == 2 && targetGroup == MAP_GROUP(MAP_SLATEPORT_CITY)
        && targetNum == MAP_NUM(MAP_SLATEPORT_CITY) && targetX == 19 && targetY == 20);
    assert(VarGet(VAR_LITTLEROOT_TOWN_STATE) == 9);
    assert(VarGet(VAR_MAP_SCENE_PALLET_TOWN_OAK) == 7);
    puts("Real Kanto and Hoenn landing assets, route admission, warp handoff and attribute bounds passed");
    return 0;
}
''')
        binary = self.directory / 'travel'
        self.run_command(['gcc', *self.flags, '-DEW_REGION_STATE=1', '-DEW_KANTO_CONTENT=1',
                          *self.game_includes, str(source), 'platform/region_state.c', 'platform/save_extension.c',
                          '-Wl,--gc-sections', '-no-pie', '-o', str(binary)])
        self.assertIn('attribute bounds passed', self.run_command([str(binary)]))


    def test_layout_catalog_keeps_default_data_and_bounds(self):
        from world.build_catalog import build_catalog, render_header, render_layout_header, ROOT
        self.assertEqual(json.loads((ROOT / 'world/map_catalog.json').read_text()), build_catalog())
        self.assertEqual((ROOT / 'include/platform/world_catalog.h').read_text(), render_header(build_catalog()))
        catalog = build_catalog(ENGINE, layout_aware=True)
        self.assertEqual(len(catalog['maps']), 937)
        self.assertEqual(sum(m['attribute_bytes'] == 2 for m in catalog['maps']), 520)
        header = self.directory / 'catalog.h'
        header.write_text(render_layout_header(catalog))
        for enabled in (0, 1):
            checks = []
            for m in catalog['maps']:
                g, n, p, s, base = (m[k] for k in ('group', 'num', 'primary_count', 'secondary_count', 'secondary_base'))
                present = enabled or m['attribute_bytes'] == 2
                checks.append(f'assert((WorldCatalog_Find({g}, {n}) != 0) == {int(bool(present))});')
                for tile in {0, p - 1, p, base - 1, base, base + s - 1, base + s, 1023, 1024}:
                    safe = present and (0 <= tile < p or base <= tile < base + s)
                    if tile >= 0:
                        checks.append(f'assert(WorldCatalog_Metatile({g}, {n}, {tile}) == {int(bool(safe))});')
            source = self.directory / 'catalog.c'
            source.write_text('#include <assert.h>\n#include "catalog.h"\nint main(void) {\n'
                              + '\n'.join(checks) + '\nreturn 0;}\n')
            binary = self.directory / f'catalog-{enabled}'
            self.run_command(['gcc', '-std=gnu17', '-O0', '-g', '-fsanitize=address,undefined',
                              f'-DEW_KANTO_CONTENT={enabled}', str(source), '-o', str(binary)])
            self.run_command([str(binary)])
