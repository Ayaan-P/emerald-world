"""Blueprint output must pass the real exporter and remain bounded data."""
import json
import hashlib
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
from world import cave_blueprint
from world.shared_cave import SharedCave
from scripts import export_generated_cave
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]

class CaveBlueprintTest(unittest.TestCase):
    def test_generated_room_graphs_pass_production_validation(self):
        rng = random.Random(2026)
        maps = set()
        for _ in range(200):
            n = rng.randint(1, 20)
            rooms = [[rng.randint(1, 23), rng.randint(1, 23), rng.randint(2, 6), rng.randint(2, 6)] for _ in range(n)]
            links = [[i, rng.randrange(i)] for i in range(1, n)]
            doc = {'rooms': rooms, 'links': links, 'entrance_room': 0, 'exit_room': n - 1}
            output = cave_blueprint.proposal_from_blueprint(doc)
            encoded = export_generated_cave.encode(output)
            self.assertEqual(len(encoded), 969)
            maps.add(encoded)
        self.assertGreater(len(maps), 190)
    def test_rejects_bad_schema_bounds_disconnected_and_bool(self):
        good = {'rooms': [[1,1,3,3], [20,20,3,3]], 'links': [[0,1]], 'entrance_room': 0, 'exit_room': 1}
        bad = [dict(good, rooms=[[True,1,3,3]]), dict(good, rooms=[[29,1,2,3]]),
               dict(good, links=[]), dict(good, links=[[0,0]]), dict(good, links=[[0,True]]),
               dict(good, entrance_room=-1), dict(good, extra='anything')]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError):
                cave_blueprint.proposal_from_blueprint(item)
    def test_styles_seed_and_width_pass_both_validators(self):
        rng = random.Random(20261105)
        for style in ('rooms', 'rounded', 'organic', 'maze'):
            for _ in range(150):
                rooms = []
                for _ in range(rng.randint(1, 24)):
                    x, y = rng.randint(1, 28), rng.randint(1, 28)
                    rooms.append([x, y, rng.randint(2, 30-x), rng.randint(2, 30-y)])
                doc = {'rooms': rooms, 'links': [[i, rng.randrange(i)] for i in range(1, len(rooms))],
                       'entrance_room': 0, 'exit_room': len(rooms)-1, 'style': style,
                       'seed': rng.randrange(2**32), 'corridor_width': rng.randint(1, 3)}
                proposal = cave_blueprint.proposal_from_blueprint(doc)
                self.assertEqual(proposal, cave_blueprint.proposal_from_blueprint(doc))
                SharedCave(export_generated_cave.encode(proposal))
                for x, y, w, h in rooms:
                    self.assertEqual(proposal['rows'][y+(h-1)//2][x+(w-1)//2], '.')

    def test_legacy_blueprint_is_unchanged_and_styles_diversify(self):
        old = {'rooms': [[1,1,3,3],[20,20,5,5]], 'links': [[0,1]], 'entrance_room': 0, 'exit_room': 1}
        self.assertEqual(hashlib.sha256(export_generated_cave.encode(cave_blueprint.proposal_from_blueprint(old))).hexdigest(),
                         'bebb184517d19accfa51ffe402d6fe08d5434c62c8474380da7f853d3a69055e')
        doc = {'rooms': [[2,2,24,24]], 'links': [], 'entrance_room': 0, 'exit_room': 0}
        maps = {export_generated_cave.encode(cave_blueprint.proposal_from_blueprint(dict(doc, style=style, seed=seed)))
                for style in ('rooms','rounded','organic','maze') for seed in range(4)}
        self.assertGreaterEqual(len(maps), 8)
        for bad in (dict(doc,style='script'), dict(doc,seed=True), dict(doc,seed=-1),
                    dict(doc,seed=2**32), dict(doc,corridor_width=True), dict(doc,corridor_width=4)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                cave_blueprint.proposal_from_blueprint(bad)

    def test_styled_blueprints_pass_actual_native_staging(self):
        source = (ROOT/'src/platform/generated_map.c').read_text()
        c_source = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int16_t s16; typedef int bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 1
#define GEN_SIDE 31
#define GEN_CELLS 961
static u8 sTemplate[GEN_CELLS];static bool8 sHasTemplate;
""" + function(source,'GeneratedMap_StageTemplate') + r"""
int main(void) { u8 data[GEN_CELLS];unsigned count=0;
 while (fread(data,1,sizeof(data),stdin)==sizeof(data)) {
  if (!GeneratedMap_StageTemplate(data,sizeof(data)) || !sHasTemplate || memcmp(data,sTemplate,sizeof(data))) return 1;
  count++;
 }
 return count==200 ? 0 : 2;
}
"""
        docs = []
        for style in ('rooms','rounded','organic','maze'):
            for seed in range(50):
                docs.append({'rooms': [[2,2,12,12],[16,16,12,12]], 'links': [[0,1]],
                             'entrance_room': 0, 'exit_room': 1, 'style': style,
                             'seed': seed, 'corridor_width': seed % 3 + 1})
        data = b''.join(export_generated_cave.encode(cave_blueprint.proposal_from_blueprint(doc))[8:] for doc in docs)
        with tempfile.TemporaryDirectory() as temp:
            c, exe = Path(temp)/'validate.c', Path(temp)/'validate'
            c.write_text(c_source)
            build = subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)], capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result = subprocess.run([str(exe)],input=data,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode())

    def test_cli_outputs_only_valid_proposal(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'blueprint.json'
            path.write_text(json.dumps({'rooms': [[5,5,5,5]], 'links': [], 'entrance_room': 0, 'exit_room': 0}))
            result = subprocess.run(['python3', '-m', 'world.cave_blueprint', str(path)], capture_output=True, text=True, check=True)
            export_generated_cave.encode(json.loads(result.stdout))
            path.write_text('x' * 16385)
            self.assertNotEqual(subprocess.run(['python3', '-m', 'world.cave_blueprint', str(path)], capture_output=True).returncode, 0)

if __name__ == '__main__': unittest.main()
