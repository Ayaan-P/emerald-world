"""Catalog safety regressions at authority, sandbox and native boundaries."""
import json
from pathlib import Path
import tempfile
import unittest

from world.mechanics import MechanicRuntime, MechanicError
from world.server import WorldServer

ROOT = Path(__file__).resolve().parents[2]


class CatalogTests(unittest.TestCase):
    def test_generator_uses_smaller_of_render_and_attribute_allocations(self):
        from world.build_catalog import build_catalog
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            files = {
                'src/data/tilesets/metatiles.h':
                    'const u16 M1[] = INCBIN_U16("p.bin");\n'
                    'const u16 A1[] = INCBIN_U16("pa.bin");\n'
                    'const u16 M2[] = INCBIN_U16("s.bin");\n'
                    'const u16 A2[] = INCBIN_U16("sa.bin");\n',
                'src/data/tilesets/headers.h':
                    'const struct Tileset P = {.metatiles = M1, .metatileAttributes = A1,};\n'
                    'const struct Tileset S = {.metatiles = M2, .metatileAttributes = A2,};\n',
                'data/maps/map_groups.json': json.dumps({'group_order': ['G'], 'G': ['Map']}),
                'data/maps/Map/map.json': json.dumps({'layout': 'L'}),
                'data/layouts/layouts.json': json.dumps({'layouts': [dict(id='L', width=2, height=3,
                    primary_tileset='P', secondary_tileset='S')]}),
            }
            for name, text in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            (root / 'p.bin').write_bytes(bytes(16 * 10))
            (root / 'pa.bin').write_bytes(bytes(2 * 3))
            (root / 's.bin').write_bytes(bytes(16 * 4))
            (root / 'sa.bin').write_bytes(bytes(2 * 11))
            m = build_catalog(root)['maps'][0]
            self.assertEqual((m['primary_count'], m['secondary_count']), (3, 4))
            (root / 'pa.bin').write_bytes(bytes(3))
            with self.assertRaisesRegex(ValueError, 'misaligned'):
                build_catalog(root)

    def test_generated_catalog_matches_source_and_all_c_boundaries(self):
        import subprocess
        from world.build_catalog import build_catalog, render_header, validate_tile
        catalog = build_catalog()
        self.assertEqual(json.loads((ROOT / 'world/map_catalog.json').read_text()), catalog)
        self.assertEqual((ROOT / 'include/platform/world_catalog.h').read_text(), render_header(catalog))
        groups = json.loads((ROOT / 'data/maps/map_groups.json').read_text())
        self.assertEqual(len(catalog['maps']), sum(len(groups[g]) for g in groups['group_order']))
        assertions = []
        with tempfile.TemporaryDirectory() as root:
            runtime = MechanicRuntime(root)
            for m in catalog['maps']:
                g, n, p, s = (m[k] for k in ('group', 'num', 'primary_count', 'secondary_count'))
                for tile_id in {0, p - 1, p, 511, 512, 512 + s - 1, 512 + s, 1023, 1024}:
                    safe = 0 <= tile_id < p or 512 <= tile_id < 512 + s
                    tile = dict(group=g, num=n, x=m['width']-1, y=m['height']-1,
                                metatile=tile_id, collision=1)
                    result = dict(state={}, tiles=[tile])
                    if safe:
                        validate_tile(list(tile.values()))
                        WorldServer._validated(result)
                        runtime._decode_result(json.dumps(result))
                    else:
                        with self.assertRaises(ValueError):
                            validate_tile(list(tile.values()))
                        with self.assertRaises(ValueError):
                            WorldServer._validated(result)
                        with self.assertRaises(MechanicError):
                            runtime._decode_result(json.dumps(result))
                    if tile_id >= 0:
                        assertions.append(f'assert(!!WorldCatalog_Metatile({g},{n},{tile_id}) == {int(safe)});')
                assertions += [f'assert(WorldCatalog_Coords({g},{n},{m["width"]-1},{m["height"]-1}));',
                               f'assert(!WorldCatalog_Coords({g},{n},{m["width"]},0));',
                               f'assert(!WorldCatalog_Coords({g},{n},0,{m["height"]}));']
            c, exe = Path(root) / 'catalog.c', Path(root) / 'catalog'
            c.write_text('#include <assert.h>\n#include "platform/world_catalog.h"\nint main(void) {\n' +
                         '\n'.join(assertions) + '\nassert(!WorldCatalog_Coords(255,255,0,0)); return 0;}\n')
            subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-iquote',
                            str(ROOT / 'include'), str(c), '-o', str(exe)], check=True, capture_output=True)
            subprocess.run([str(exe)], check=True, capture_output=True, cwd=root)

    def test_sparse_tilesets_reject_real_sandbox_output(self):
        with tempfile.TemporaryDirectory() as root:
            runtime = MechanicRuntime(root)
            for tile_id in (8, 511, 708, 1023):
                tile = dict(group=1, num=0, x=0, y=0, metatile=tile_id, collision=0)
                with self.subTest(tile_id=tile_id), self.assertRaises(MechanicError):
                    runtime.from_source('def update(context,state):\n return ' + repr(dict(state={}, tiles=[tile])))
            for tile_id in (7, 512, 707):
                tile = dict(group=1, num=0, x=10, y=8, metatile=tile_id, collision=1)
                candidate = runtime.from_source('def update(context,state):\n return ' + repr(dict(state={}, tiles=[tile])))
                self.assertEqual(runtime.run(candidate, {}, {})['tiles'], [tile])

    def test_native_parser_rejects_sparse_primary_and_secondary_ids(self):
        import subprocess
        from test_save_isolation import function
        bridge = (ROOT / 'src/platform/world_bridge.c').read_text()
        declarations = bridge[bridge.index('struct Peer {'):bridge.index('static bool8 Identifier(')]
        source = '''#include <assert.h>
#include <string.h>
#include <limits.h>
#include <stdio.h>
typedef unsigned char bool8;
typedef unsigned char u8;
typedef unsigned short u16;
#define TRUE 1
#define FALSE 0
#define WB_PEERS 8
#define WB_OBJECTS 8
#define WB_REMOTES (WB_PEERS + WB_OBJECTS)
#define WB_TILES 128
#define WB_BUFFER 65536
#define MAP_GROUPS_COUNT 34
#define ARRAY_COUNT(x) (sizeof(x)/sizeof((x)[0]))
#define MAP_OFFSET 7
#define MAPGRID_IMPASSABLE 0xc00
static int writes, draws;
static bool8 GridCoords(unsigned x, unsigned y) {(void)x;(void)y;return 1;}
static u16 Raw(unsigned x, unsigned y) {(void)x;(void)y;return 0;}
static void MapGridSetMetatileIdAt(unsigned x, unsigned y, unsigned v) {(void)x;(void)y;(void)v;writes++;}
static void CurrentMapDrawMetatileAt(unsigned x, unsigned y) {(void)x;(void)y;draws++;}
struct MapLayout { int width, height; };
struct MapHeader { const struct MapLayout *mapLayout; };
static const struct MapHeader *Overworld_GetMapHeaderByGroupAndId(unsigned g, unsigned n) {
 static struct MapLayout l = {11,9}; static struct MapHeader h = {&l};
 (void)g; (void)n; return &h;
}
#include "platform/world_catalog.h"
'''
        source += (ROOT/'include/platform/chat_command_gate.h').read_text()
        source += declarations
        source += ''.join(function(bridge, n) for n in ('Identifier', 'Decimal', 'ObjectText', 'MapCoords', 'Line'))
        source += '''static void ApplyTiles(void) {
 unsigned i;
'''
        sync = function(bridge, 'SyncEngine')
        loop = sync[sync.index('    for (i = 0; i < sWorld.live.tileCount; i++)'):]
        source += loop
        source += '''int main(void) {
 char begin[]="BEGIN 1", bad[]="TILE 1 0 0 0 511 1";
 char secondaryBad[]="TILE 1 0 0 0 708 1", primaryEdge[]="TILE 1 0 0 0 8 1";
 char good[]="TILE 1 0 0 0 707 1", peerBad[]="PEER Bob 255 255 0 0 0 65535 0";
 sWorld.connected=1;
 assert(Line(begin)); assert(!Line(bad)); assert(!Line(secondaryBad)); assert(!Line(primaryEdge));
 assert(!Line(peerBad)); assert(Line(good));
 sWorld.group=1; sWorld.num=0; sWorld.live.tileCount=1;
 sWorld.live.tiles[0]=(struct Tile){1,0,0,0,511,1};
 ApplyTiles(); assert(writes==0 && draws==0 && sWorld.appliedCount==0);
 sWorld.live.tiles[0].metatile=708;
 ApplyTiles(); assert(writes==0 && draws==0 && sWorld.appliedCount==0);
 sWorld.live.tiles[0].metatile=7;
 ApplyTiles(); assert(writes==1 && draws==1 && sWorld.appliedCount==1);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as root:
            c = Path(root) / 'parser.c'
            exe = Path(root) / 'parser'
            c.write_text(source)
            result = subprocess.run(['cc', '-std=gnu99', '-iquote', str(ROOT / 'include'), str(c), '-o', str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, cwd=root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_prepare_save_removes_owned_peers_outside_overworld(self):
        from test_save_isolation import SaveIsolation
        SaveIsolation().compile_and_run('overworld = 0; SaveObjectEvents(); RoundTrip(); assert(!gObjectEvents[2].active);')

    def test_invalid_peer_does_not_reach_other_clients(self):
        from world.client import WorldClient
        with tempfile.TemporaryDirectory() as root:
            server = WorldServer(root + '/sock', root + '/state')
            identities = [server.create_identity(n) for n in ('Alice', 'Bob')]
            server.start()
            try:
                with WorldClient(root + '/sock', 'Alice', identities[0]['token']) as alice:
                    alice.snapshot()
                    with WorldClient(root + '/sock', 'Bob', identities[1]['token']) as bob:
                        bob.snapshot()
                        alice.snapshot()  # Bob joined.
                        bob.send_state(1, 255, 255, 0, 0, 0, 65535, 0, 'a'*16, 'b'*16)
                        with self.assertRaisesRegex(ValueError, 'MALFORMED'):
                            bob.snapshot()
                        self.assertEqual(alice.snapshot()['peers'], {})
                        alice.send_state(1, 0, 0, 0, 0, 1, 7, 1, 'a'*16, 'b'*16)
                        self.assertEqual(alice.snapshot()['peers'], {})
            finally:
                server.close()

    def test_invalid_deploy_retains_last_good_durable_overlay_and_reconnects(self):
        from world.client import WorldClient, admin_request
        with tempfile.TemporaryDirectory() as root:
            state = Path(root) / 'state'
            server = WorldServer(root + '/sock', state)
            identity = server.create_identity('Alice')
            good = state / 'candidates/good.py'
            tile = dict(group=1, num=0, x=0, y=0, metatile=7, collision=1)
            good.write_text('def update(c,s): return ' + repr(dict(state={'good': True}, tiles=[tile])))
            server.start()
            try:
                self.assertTrue(admin_request(root + '/sock', dict(command='deploy', source_path=str(good)))['ok'])
                before = server.inspect()
                for bad_tile in (dict(tile, group=255, num=255), dict(tile, metatile=511), dict(tile, metatile=708)):
                    path = state / 'candidates/bad.py'
                    path.write_text('def update(c,s): return ' + repr(dict(state={'bad': True}, tiles=[bad_tile])))
                    response = admin_request(root + '/sock', dict(command='deploy', source_path=str(path)))
                    self.assertFalse(response['ok'], response)
                    after = server.inspect()
                    for key in ('module_hash', 'state', 'tiles'):
                        self.assertEqual(before[key], after[key])
                    with WorldClient(root + '/sock', 'Alice', identity['token']) as client:
                        self.assertEqual(client.snapshot()['tiles'], [[1,0,0,0,7,1]])
            finally:
                server.close()
            server = WorldServer(root + '/sock', state)
            server.start()
            try:
                self.assertEqual(server.inspect()['module_hash'], before['module_hash'])
                with WorldClient(root + '/sock', 'Alice', identity['token']) as client:
                    self.assertEqual(client.snapshot()['tiles'], [[1,0,0,0,7,1]])
            finally:
                server.close()

    def test_peer_fields_and_canonical_unready_presence(self):
        from world.client import WorldClient
        invalid = [(255,255,0,0,1,7,1), (1,255,0,0,1,7,1),
                   (1,0,11,0,1,7,1), (1,0,0,9,1,7,1),
                   (1,0,0,0,0,7,1), (1,0,0,0,1,256,1),
                   (1,0,0,0,1,7,0)]
        with tempfile.TemporaryDirectory() as root:
            server = WorldServer(root + '/sock', root + '/state')
            alice_id = server.create_identity('Alice')
            server.start()
            try:
                with WorldClient(root + '/sock', 'Alice', alice_id['token']) as alice:
                    alice.snapshot()
                    for i, fields in enumerate(invalid):
                        identity = server.create_identity('bad' + str(i))
                        with self.subTest(fields=fields), WorldClient(root + '/sock', identity['id'], identity['token']) as bad:
                            bad.snapshot()
                            alice.snapshot()
                            bad.send_state(1, *fields, 'a'*16, 'b'*16)
                            with self.assertRaisesRegex(ValueError, 'MALFORMED'):
                                bad.snapshot()
                            self.assertEqual(alice.snapshot()['peers'], {})
                    bob_id = server.create_identity('Bob')
                    with WorldClient(root + '/sock', 'Bob', bob_id['token']) as bob:
                        bob.snapshot()
                        alice.snapshot()
                        bob.send_state(1, 1, 0, 10, 8, 4, 255, 1, 'a'*16, 'b'*16)
                        self.assertEqual(alice.snapshot()['peers']['Bob']['gfx'], 255)
                        bob.send_state(2, 0, 0, 0, 0, 1, 7, 0, 'a'*16, 'b'*16)
                        self.assertEqual(alice.snapshot()['peers'], {})
                        bob.send_state(3, 1, 0, 0, 0, 1, 7, 1, 'a'*16, 'b'*16)
                        self.assertIn('Bob', alice.snapshot()['peers'])
            finally:
                server.close()

    def test_persisted_invalid_tiles_are_quarantined_on_restart(self):
        with tempfile.TemporaryDirectory() as root:
            server = WorldServer(root + '/sock', root + '/state')
            server.db.execute('INSERT INTO module(singleton,source,sha256,state,tiles) VALUES(1,?,?,?,?)',
                              ('def update(c,s): return {"state":{},"tiles":[]}', '0'*64,
                               '{}', '[[255,255,0,0,1,0]]'))
            server.db.commit()
            server.close()
            server = WorldServer(root + '/sock', root + '/state')
            try:
                self.assertEqual(server.tiles, [])
                self.assertIsNone(server.candidate)
                self.assertIn('persisted', server.module_error)
            finally:
                server.close()

    def test_field_cache_revokes_scripts_warp_fades_battles_and_resets(self):
        import subprocess
        from test_save_isolation import function
        bridge = (ROOT / 'src/platform/world_bridge.c').read_text()
        source = '''#include <assert.h>
 typedef unsigned char bool8;
 #define FALSE 0
 #define MAP_OFFSET 7
 struct Peer {unsigned group,num,x,y,facing,gfx;};
 struct ObjectEvent {struct {int x,y;} currentCoords; unsigned facingDirection,graphicsId;};
 static struct ObjectEvent gObjectEvents[1] = {{{13,12},1,7}};
 static struct {unsigned objectEventId;} gPlayerAvatar;
 static struct {int active;} gPaletteFade;
 static struct {struct Peer field; bool8 fieldKnown;} sWorld;
 static struct Save {struct {int mapGroup,mapNum;} location;} save={{1,4}}, *gSaveBlock1Ptr=&save;
 static void CB1_Overworld(void) {}
 static struct {int inBattle; void (*callback1)(void);} gMain={0,CB1_Overworld};
 static int overworld=1, script, menu;
 static bool8 Overworld(void) {return overworld;}
 static bool8 ScriptContext_IsEnabled(void) {return script;}
 static void Task_ShowStartMenu(unsigned char taskId) {(void)taskId;}
 static bool8 FuncIsActiveTask(void (*func)(unsigned char)) {(void)func;return menu;}
 static bool8 MapCoords(unsigned g,unsigned n,unsigned x,unsigned y) {return g==1 && n==4 && x<14 && y<14;}
'''
        source += function(bridge, 'UpdateFieldPresence')
        source += '''int main(void) {
 UpdateFieldPresence(); assert(sWorld.fieldKnown); assert(sWorld.field.x==6);
 script=1; UpdateFieldPresence(); assert(!sWorld.fieldKnown); script=0;
 UpdateFieldPresence(); gPaletteFade.active=1;
 UpdateFieldPresence(); assert(!sWorld.fieldKnown);
 gPaletteFade.active=0; UpdateFieldPresence(); gPaletteFade.active=1; menu=1;
 UpdateFieldPresence(); assert(sWorld.fieldKnown);
 overworld=0; menu=0; UpdateFieldPresence(); assert(sWorld.fieldKnown);
 gMain.inBattle=1; UpdateFieldPresence(); assert(!sWorld.fieldKnown);
 gMain.inBattle=0; overworld=1; gPaletteFade.active=0; UpdateFieldPresence();
 overworld=0; gMain.callback1=0; UpdateFieldPresence(); assert(!sWorld.fieldKnown);
 gMain.callback1=CB1_Overworld; overworld=1; UpdateFieldPresence();
 overworld=0; save.location.mapNum=5; UpdateFieldPresence(); assert(!sWorld.fieldKnown);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as root:
            c, exe = Path(root)/'cache.c', Path(root)/'cache'
            c.write_text(source)
            subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                            str(c), '-o', str(exe)], check=True, capture_output=True)
            subprocess.run([str(exe)], check=True, capture_output=True)

    def test_walking_presence_does_not_unlock_field_interactions(self):
        import subprocess
        from test_save_isolation import function
        bridge = (ROOT / 'src/platform/world_bridge.c').read_text()
        source = '''#include <assert.h>
 typedef unsigned char bool8;
 static struct {int active;} gPaletteFade;
 static struct {int tileTransitionState;} gPlayerAvatar;
 static int overworld=1, locked, script;
 static bool8 Overworld(void) {return overworld;}
 static bool8 ArePlayerFieldControlsLocked(void) {return locked;}
 static bool8 ScriptContext_IsEnabled(void) {return script;}
'''
        source += function(bridge, 'PresenceReady') + function(bridge, 'Ready')
        source += '''int main(void) {
 gPlayerAvatar.tileTransitionState=1;
 assert(PresenceReady()); assert(!Ready());
 gPlayerAvatar.tileTransitionState=0;
 assert(PresenceReady()); assert(Ready());
 locked=1; assert(!PresenceReady()); assert(!Ready()); locked=0;
 script=1; assert(!PresenceReady()); assert(!Ready()); script=0;
 gPaletteFade.active=1; assert(!PresenceReady()); gPaletteFade.active=0;
 overworld=0; assert(!PresenceReady()); assert(!Ready());
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as root:
            c, exe = Path(root)/'readiness.c', Path(root)/'readiness'
            c.write_text(source)
            subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                            str(c), '-o', str(exe)], check=True, capture_output=True)
            subprocess.run([str(exe)], check=True, capture_output=True)

    def test_native_unready_state_is_canonical_even_in_transition(self):
        import subprocess
        from test_save_isolation import function
        bridge = (ROOT / 'src/platform/world_bridge.c').read_text()
        source = '''#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char bool8;
#define OBJ_EVENT_GFX_BOY_1 7
#define MAP_OFFSET 7
struct ObjectEvent { struct {int x,y;} currentCoords; unsigned facingDirection,graphicsId; };
static struct ObjectEvent gObjectEvents[1] = {{{-10,-20},0,999}};
static struct {unsigned objectEventId;} gPlayerAvatar;
static struct Save { struct {int mapGroup,mapNum;} location;
 char bagPocket_Items[1],bagPocket_KeyItems[1],bagPocket_PokeBalls[1],bagPocket_TMHM[1],bagPocket_Berries[1]; } save = {{255,255},{0},{0},{0},{0},{0}}, *gSaveBlock1Ptr=&save;
static char gPlayerParty[1];
struct Peer { unsigned group,num,x,y,facing,gfx; };
static struct {int connected; unsigned seq; size_t outputSize; char output[4096]; struct Peer field; bool8 fieldKnown;} sWorld;
static bool8 Overworld(void) {return 1;}
static bool8 PresenceReady(void) {return 0;}
static void Flush(void) {}
static void Fingerprint(const void *p,size_t n,char out[17]) {(void)p;(void)n;strcpy(out,"0000000000000000");}
'''
        source += function(bridge, 'SendState')
        source += '''int main(void) {
 sWorld.connected=1; SendState();
 assert(!strncmp(sWorld.output,"STATE 1 0 0 0 0 1 7 0 ",22));
 gSaveBlock1Ptr=0; sWorld.outputSize=0; SendState();
 assert(!strncmp(sWorld.output,"STATE 2 0 0 0 0 1 7 0 ",22)); return 0;
}
'''
        with tempfile.TemporaryDirectory() as root:
            c, exe = Path(root) / 'state.c', Path(root) / 'state'
            c.write_text(source)
            result = subprocess.run(['cc', '-std=gnu99', str(c), '-o', str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, cwd=root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_nonexistent_maps_and_layout_edges_are_rejected(self):
        tiles = [dict(group=255, num=255, x=0, y=0, metatile=1, collision=0),
                 dict(group=1, num=0, x=11, y=0, metatile=1, collision=0),
                 dict(group=1, num=0, x=0, y=9, metatile=1, collision=0)]
        with tempfile.TemporaryDirectory() as root:
            runtime = MechanicRuntime(root)
            for tile in tiles:
                with self.subTest(tile=tile):
                    with self.assertRaises(ValueError):
                        WorldServer._validated(dict(state={}, tiles=[tile]))
                    with self.assertRaises(MechanicError):
                        runtime.from_source('def update(context,state):\n return ' + repr(dict(state={}, tiles=[tile])))


if __name__ == '__main__':
    unittest.main()
