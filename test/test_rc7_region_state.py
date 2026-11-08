"""Compile real Expansion save/event hooks and native persistence, offline.

Uses the actual map/JSON generators and headers, not substitute save structs.
ASan and UBSan are enabled. No full game link, script execution, or sockets.
"""
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(os.environ.get('EW_RC7_ENGINE', ROOT / 'engines/expansion-native')).resolve()


class RegionStateIntegration(unittest.TestCase):
    @classmethod
    def run_command(cls, command):
        result = subprocess.run(command, cwd=ENGINE, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise AssertionError(f'{command[0]} exited {result.returncode}:\n{result.stdout}\n{result.stderr}')
        return result.stdout

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='ew-region-integration-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.generated = cls.directory / 'include'
        constants = cls.generated / 'constants'
        constants.mkdir(parents=True)
        asm = cls.directory / 'asm'
        asm.mkdir()
        mapjson = cls.directory / 'mapjson'
        jsonproc = cls.directory / 'jsonproc'
        cls.run_command(['g++', '-std=c++17', '-O1', 'tools/mapjson/json11.cpp',
                         'tools/mapjson/mapjson.cpp', '-o', str(mapjson)])
        cls.run_command([str(mapjson), 'groups', 'combined', 'data/maps/map_groups.json',
                         *map(str, sorted((ENGINE / 'data/maps').glob('*/map.json'))), str(asm), str(constants)])
        cls.run_command(['g++', '-std=c++17', '-O1', '-Itools/jsonproc',
                         'tools/jsonproc/jsonproc.cpp', '-o', str(jsonproc)])
        cls.run_command([str(jsonproc), 'src/data/region_map/region_map_sections.json',
                         'src/data/region_map/region_map_sections.constants.json.txt',
                         str(constants / 'region_map_sections.h')])
        cls.flags = ['-O1', '-g', '-std=gnu17', '-ffunction-sections', '-fdata-sections', '-funsigned-char',
                     '-DMODERN=1', '-DPLATFORM_NATIVE=1', '-DPORTABLE=1', '-DTESTING=0', '-DEMERALD',
                     '-D_FILE_OFFSET_BITS=64', '-D_TIME_BITS=64', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
        cls.game_includes = ['-iquote', str(cls.generated), '-iquote', str(constants),
                             '-iquote', 'include', '-iquote', '.', '-Iplatform']
        cls.link = ['-no-pie', '-Wl,--gc-sections', '-Wl,-Ttext-segment=0x40000000',
                    '-Wl,-T,platform/gba_regions.ld', '-Wl,-T,platform/gba_game.ld']
        cls.platform = ['platform/region_state.c', 'platform/save_extension.c', 'platform/save_file.c',
                        'platform/flash.c', 'platform/gba_memmap.c', 'platform/host_posix.c',
                        'platform/host_linux.c', 'platform/host_linked.c']

    def test_actual_game_save_and_event_data_hooks(self):
        obj = self.directory / 'hooks.o'
        binary = self.directory / 'hooks'
        self.run_command(['gcc', *self.flags, '-DEW_REGION_STATE=1', *self.game_includes,
                          '-c', 'tests/rc8/region_state_save.c', '-o', str(obj)])
        self.run_command(['gcc', *self.flags, '-DEW_REGION_STATE=1', '-Iplatform', '-idirafter', 'include',
                          '-iquote', '.', *self.link, str(obj), *self.platform, '-o', str(binary)])
        self.assertIn('passed', self.run_command([str(binary)]))

    def test_save_layout_and_shared_system_flags_do_not_change(self):
        source = self.directory / 'layout.c'
        source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include "global.h"
int main(void) {
#if EW_REGION_STATE
    assert(VAR_MAP_SCENE_PALLET_TOWN_OAK == 0x5050);
    assert(FLAG_HIDE_OAK_IN_PALLET_TOWN == 0x102C);
#else
    assert(VAR_MAP_SCENE_PALLET_TOWN_OAK == 0x4050);
    assert(FLAG_HIDE_OAK_IN_PALLET_TOWN == 0);
#endif
    assert(VAR_LITTLEROOT_TOWN_STATE == 0x4050);
    printf("%zu %zu %u %u %u\n", sizeof(struct SaveBlock1), sizeof(struct SaveBlock3),
           FLAG_SYS_POKEDEX_GET, FLAG_BADGE01_GET, FLAG_SYS_GAME_CLEAR);
    return 0;
}
''')
        results = []
        for enabled in (0, 1):
            binary = self.directory / f'layout-{enabled}'
            self.run_command(['gcc', *self.flags, f'-DEW_REGION_STATE={enabled}', *self.game_includes,
                              str(source), '-o', str(binary)])
            results.append(self.run_command([str(binary)]))
        self.assertEqual(results[0], results[1])
        self.assertTrue(results[0].startswith('15768 1574 '), results[0])

    def test_default_cohort_refuses_regional_saves_without_overwriting(self):
        # Independent wire-format fixture: empty even slot, Kanto odd slot.
        extension = (b'EWSX0001' + struct.pack('<III', 0, 0, 0)
                     + struct.pack('<III', 1, 0x4B4E5401, 1024) + bytes(1024))
        flash = bytes(131072)
        data = (b'PENSAV2\0' + struct.pack('<IIIII', 2, 64, 1, len(flash), zlib.crc32(flash))
                + flash + struct.pack('<II', len(extension), zlib.crc32(extension)) + extension)
        path = self.directory / 'regional.sav'
        path.write_bytes(data)
        source = self.directory / 'refuse.c'
        source.write_text(r'''
#include <assert.h>
#include "flash.h"
#include "save_file.h"
int main(int argc, char **argv) {
    assert(argc == 2);
    flash_init();
    assert(save_file_init(argv[1]) == SAVE_FILE_OK);
    assert(save_file_load() == SAVE_FILE_REFUSED);
    assert(save_file_store() == SAVE_FILE_REFUSED);
    save_file_shutdown();
    return 0;
}
''')
        binary = self.directory / 'refuse'
        self.run_command(['gcc', *self.flags, '-DEW_REGION_STATE=0', '-Iplatform', '-idirafter', 'include',
                          '-iquote', '.', *self.link, str(source), *self.platform, '-o', str(binary)])
        self.run_command([str(binary), str(path)])
        self.assertEqual(path.read_bytes(), data)

    def test_build_wrapper_requires_development_for_region_state(self):
        result = subprocess.run(['python3', str(ROOT / 'scripts/build_expansion.py'), '--regional-state'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('--regional-state requires --development', result.stderr)


if __name__ == '__main__':
    unittest.main()
