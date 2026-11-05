"""Blueprint output must pass the real exporter and remain bounded data."""
import json
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
from scripts import cave_blueprint, export_generated_cave

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
    def test_cli_outputs_only_valid_proposal(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'blueprint.json'
            path.write_text(json.dumps({'rooms': [[5,5,5,5]], 'links': [], 'entrance_room': 0, 'exit_room': 0}))
            result = subprocess.run(['python3', str(ROOT/'scripts/cave_blueprint.py'), str(path)], capture_output=True, text=True, check=True)
            export_generated_cave.encode(json.loads(result.stdout))
            path.write_text('x' * 16385)
            self.assertNotEqual(subprocess.run(['python3', str(ROOT/'scripts/cave_blueprint.py'), str(path)], capture_output=True).returncode, 0)

if __name__ == '__main__': unittest.main()
