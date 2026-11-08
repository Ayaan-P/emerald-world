"""Real construction bytes, admin guards, restart and native wire framing."""
import json
import unittest
from unittest.mock import patch
from world.frontier_outposts import compile_outpost, main
from world.xl_wilds import encode
from world.shared_cave import SharedCave
import test_world_memory as fixtures


def base():
    rows = [['#'] * 127 for _ in range(127)]
    for y in range(1, 126): rows[y][1] = '.'
    for x in range(1, 126): rows[125][x] = '.'
    rows[124][125] = '.'
    return encode(dict(rows=[''.join(row) for row in rows], spawn=[1, 1], exit=[125, 125]))


def plan():
    return dict(x=15, y=20, width=9, height=7, gate='west', reservations=[])


class FrontierGeometry(unittest.TestCase):
    def test_native_courtyard_preserves_old_tiles_and_accepts_later_expansion(self):
        original = base(); blob, report = compile_outpost(original, plan())
        cave = SharedCave(blob)
        self.assertEqual(cave.version, 16)
        self.assertEqual((blob, report), compile_outpost(original, plan()))
        for index, tile in enumerate(original[8:]):
            if tile == ord('.'): self.assertEqual(blob[8 + index], tile)
        self.assertTrue(cave.walkable(18, 23)); self.assertTrue(cave.walkable(15, 23))
        self.assertFalse(cave.walkable(15, 22)); self.assertFalse(cave.walkable(23, 23))
        self.assertEqual(report['gate'], [15, 23])
        self.assertGreater(report['added_walkable_tiles'], 35)
        for a, b in zip(report['access_trail'], report['access_trail'][1:]):
            self.assertEqual(abs(a[0]-b[0])+abs(a[1]-b[1]), 1)
        next_blob, _ = compile_outpost(blob, dict(plan(), x=35, y=40))
        self.assertTrue(SharedCave(next_blob).walkable(18, 23))
        with self.assertRaisesRegex(ValueError, 'overlaps'): compile_outpost(blob, plan())

    def test_all_gates_and_reserved_detour(self):
        for gate in ('north', 'east', 'south', 'west'):
            blob, report = compile_outpost(base(), dict(plan(), gate=gate))
            self.assertTrue(SharedCave(blob).walkable(*report['gate']))
        p = dict(plan(), reservations=[[8, 15, 2, 20]])
        _, report = compile_outpost(base(), p)
        self.assertTrue(all(not (8 <= x < 10 and 15 <= y < 35) for x, y in report['access_trail']))
        p['reservations'] = [[8, 1, 2, 125], [2, 124, 124, 2]]
        with self.assertRaisesRegex(ValueError, 'separates'): compile_outpost(base(), p)

    def test_exact_engine_staging_accepts_constructed_map_and_rejects_damage(self):
        import os
        import subprocess
        import tempfile
        from pathlib import Path
        from test_save_isolation import function
        engine = Path(os.environ.get('EW_RC7_ENGINE', 'engines/expansion-native'))
        source = engine/'src/world/generated_map.c'
        if not source.exists(): self.skipTest('exact Expansion engine source not materialized')
        code = """#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;
typedef int16_t s16;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 1
#define GENERATED_WORLD_XL 1
#define XL_SIDE 127
#define XL_CELLS 16129
static u8 sXLTemplate[XL_CELLS];
static int sXLStaged,sXLShared,sXLHasPalette,sLargeStaged,sLargeShared,sHasTemplate,sLargeWilds;
static int WorldBridge_Enabled(void){return 1;}
static int GeneratedMap_IsInside(void){return 0;}
static int GeneratedMap_EntryPending(void){return 0;}
""" + function(source.read_text(), 'StageXLWilds') + """
int main(void){u8 data[XL_CELLS];if(fread(data,1,sizeof(data),stdin)!=sizeof(data))return 1;
if(!StageXLWilds(data,sizeof(data),1))return 2;
if(memcmp(data,sXLTemplate,sizeof(data)) || !sXLStaged || !sXLShared)return 3;
data[0]='.';if(StageXLWilds(data,sizeof(data),1))return 4;return 0;}
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'check.c').write_text(code)
            built = subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(root/'check.c'),'-o',str(root/'check')],capture_output=True)
            self.assertEqual(built.returncode,0,built.stderr)
            blob, _ = compile_outpost(base(),plan())
            checked = subprocess.run([str(root/'check')],input=blob[8:],capture_output=True)
            self.assertEqual(checked.returncode,0,checked.stderr)

    def test_invalid_plans(self):
        for key, value in [('x', True), ('width', 4), ('height', 16), ('gate', []),
                           ('reservations', [[1, 1, 200, 1]]), ('x', 1)]:
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError): compile_outpost(base(), dict(plan(), **{key:value}))
        with self.assertRaises(ValueError): compile_outpost(base(), {**plan(), 'script':'bad'})
        with self.assertRaises(ValueError): compile_outpost(base(), dict(plan(), reservations=[[15,20,9,7]]))


class FrontierAuthority(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.WorldMemoryTests(); self.f.setUp(); self.addCleanup(self.f.tearDown)
        self.server = self.f.server
        self.old = self.server._replace_cave(base(), label='Western Frontier')
        self.place = self.server.memory.place(self.old)

    def request(self):
        return dict(command='construct_outpost', plan=plan(), label='Western Frontier Camp',
                    previous_revision=self.old, expected_world_id=self.server.memory.world_id,
                    expected_sequence=self.server.memory.context(self.server)['through'])

    def test_persistent_place_continuity_archive_wire_and_revisit(self):
        request = self.request(); result = self.f.admin(request)
        self.assertTrue(result['ok'], result)
        new = result['revision']; self.assertNotEqual(new, self.old)
        self.assertEqual(result['place_id'], self.place)
        self.assertTrue(self.server.shared_cave.walkable(18, 23))
        self.assertTrue(self.server.memory.history()['events'][-1]['continued'])
        self.assertFalse(self.f.admin(request)['ok'])
        self.server.close(); self.f.server = self.f.open(); self.server = self.f.server
        self.assertEqual(self.server.shared_cave.identity, new)
        self.assertEqual(self.server.memory.place(new), self.place)
        self.assertTrue(self.server.shared_cave.walkable(18, 23))
        self.assertEqual(self.server.shared_cave.frames(), SharedCave(compile_outpost(base(), plan())[0]).frames())
        self.server.activate_generated_area(self.old)
        self.assertFalse(self.server.shared_cave.walkable(18, 23))
        self.server.activate_generated_area(new)
        self.assertTrue(self.server.shared_cave.walkable(18, 23))

    def test_stale_occupied_and_character_refusals_are_atomic(self):
        before = self.server.memory.history()
        for field, value in [('expected_sequence', 0), ('expected_world_id', 'wrong'),
                             ('previous_revision', '0' * 64), ('label', '\n')]:
            request = self.request(); request[field] = value
            self.assertFalse(self.f.admin(request)['ok'])
            self.assertEqual(self.server.shared_cave.identity, self.old)
            self.assertEqual(self.server.memory.history(), before)
        self.server.peers['occupied'] = dict(closing=False, in_generated_cave=True)
        try: self.assertFalse(self.f.admin(self.request())['ok'])
        finally: self.server.peers.clear()
        self.server.objects = [dict(region_revision=self.old)]
        try:
            result = self.f.admin(self.request()); self.assertFalse(result['ok']); self.assertIn('character', result['error'])
        finally: self.server.objects = []
        self.assertEqual(self.server.memory.history(), before)

    def test_failed_persistence_does_not_activate(self):
        self.server.db.execute("CREATE TRIGGER fail_build BEFORE INSERT ON generated_cave BEGIN SELECT RAISE(ABORT,'fail'); END")
        before = self.server.memory.history()
        result = self.f.admin(self.request())
        self.assertFalse(result['ok']); self.assertEqual(self.server.shared_cave.identity, self.old)
        self.assertEqual(self.server.memory.history(), before)
        self.assertEqual(len(self.server.list_generated_areas()), 1)

    def test_cli_preview_then_explicit_apply(self):
        path = self.f.root/'plan.json'; path.write_text(json.dumps(plan()))
        def transport(_socket, request, **kwargs): return self.f.admin(request)
        with patch('world.client.admin_request', side_effect=transport), patch('builtins.print'):
            self.assertEqual(main([str(path), '--admin-socket', 'admin', '--label', 'Camp']), 0)
            self.assertEqual(self.server.shared_cave.identity, self.old)
            self.assertEqual(main([str(path), '--admin-socket', 'admin', '--label', 'Camp', '--apply']), 0)
            self.assertNotEqual(self.server.shared_cave.identity, self.old)


if __name__ == '__main__': unittest.main()
