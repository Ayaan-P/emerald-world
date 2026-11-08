"""Exercise the real generated region registry without claiming donor gameplay."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(os.environ.get('EW_RC7_ENGINE', ROOT / 'engines/expansion-native'))


class RegionIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ew-region-identity-')
        cls.root = Path(cls.temp.name)
        cls.binary = cls.root / 'mapjson'
        source = ENGINE / 'tools/mapjson'
        subprocess.run(['g++', '-std=c++17', '-O2', str(source / 'json11.cpp'),
                        str(source / 'mapjson.cpp'), '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def fixture(self):
        temp = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for path in ('data/maps', 'src/data', 'asm', 'include', 'tools/mapjson'):
            (root / path).mkdir(parents=True, exist_ok=True)
        (root / 'tools/mapjson/required_map_defines.json').write_text('{"required_maps": []}')
        return root

    def generate(self, root, groups, maps):
        (root / 'data/maps/map_groups.json').write_text(json.dumps(groups))
        files = []
        for row in maps:
            p = root / 'data/maps' / row['name'] / 'map.json'
            p.parent.mkdir(exist_ok=True)
            p.write_text(json.dumps(row))
            files.append(str(p))
        return subprocess.run([str(self.binary), 'groups', 'combined',
                               'data/maps/map_groups.json', *files, 'asm', 'include'],
                              cwd=root, capture_output=True, text=True)

    def test_metadata_not_graphics_selects_region_and_appended_ids_stay_stable(self):
        root = self.fixture()
        groups = {'group_order': ['Existing'], 'Existing': ['Hoenn', 'Kanto']}
        maps = [{'name': 'Hoenn', 'id': 'MAP_HOENN', 'region': 'REGION_HOENN', 'layout': 'FRLG_LAYOUT'},
                {'name': 'Kanto', 'id': 'MAP_KANTO', 'region': 'REGION_KANTO', 'layout': 'EMERALD_LAYOUT'}]
        q = self.generate(root, groups, maps)
        self.assertEqual(q.returncode, 0, q.stderr)
        old = (root / 'include/map_groups.h').read_text()
        for name in ('JOHTO', 'SINNOH', 'CUSTOM'):
            groups['group_order'].append(name)
            groups[name] = [name]
            maps.append({'name': name, 'id': 'MAP_' + name, 'region': 'REGION_' + name})
        q = self.generate(root, groups, maps)
        self.assertEqual(q.returncode, 0, q.stderr)
        new = (root / 'include/map_groups.h').read_text()
        for line in old.splitlines():
            if ' = (' in line:
                self.assertIn(line, new)
        source = root / 'check.c'
        source.write_text('''#include <assert.h>
#include "map_regions.h"
int main(void) {
 assert(WorldRegion_ForMap(0,0)==EW_MAP_REGION_HOENN);
 assert(WorldRegion_ForMap(0,1)==EW_MAP_REGION_KANTO);
 assert(WorldRegion_ForMap(1,0)==EW_MAP_REGION_JOHTO);
 assert(WorldRegion_ForMap(2,0)==EW_MAP_REGION_SINNOH);
 assert(WorldRegion_ForMap(3,0)==EW_MAP_REGION_CUSTOM);
 assert(WorldRegion_ForMap(127,127)==EW_MAP_REGION_UNKNOWN);
 assert(WorldRegion_ForMap(128,0)==EW_MAP_REGION_UNKNOWN);
 assert(WorldRegion_ForMap(0,128)==EW_MAP_REGION_UNKNOWN);
 return 0;
}
''')
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I'+str(root/'include'),
                        str(source), '-o', str(root/'check')], check=True)
        subprocess.run([str(root/'check')], check=True)

    def test_unknown_region_and_duplicate_identifier_are_rejected(self):
        for maps in ([{'name':'A','id':'MAP_A','region':'REGION_TYPO'}],
                     [{'name':'A','id':'MAP_A'}, {'name':'B','id':'MAP_A'}]):
            root = self.fixture()
            q = self.generate(root, {'group_order':['G'], 'G':[m['name'] for m in maps]}, maps)
            self.assertNotEqual(q.returncode, 0)
            self.assertRegex(q.stderr, 'Unsupported combined map region|Duplicate map identifier')

    def test_signed_save_map_coordinates_cannot_overflow(self):
        for group_count, map_count in ((129, 1), (1, 129)):
            root = self.fixture()
            groups = {'group_order': ['G'+str(i) for i in range(group_count)]}
            maps = []
            for i, group in enumerate(groups['group_order']):
                groups[group] = []
                for j in range(map_count):
                    name = 'M'+str(i)+'_'+str(j)
                    groups[group].append(name)
                    maps.append({'name':name,'id':'MAP_'+name,'region':'REGION_CUSTOM'})
            q = self.generate(root, groups, maps)
            self.assertNotEqual(q.returncode, 0)
            self.assertIn('signed 8-bit map identifier', q.stderr)


if __name__ == '__main__':
    unittest.main()
