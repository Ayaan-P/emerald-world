"""Exercise RC7's generated-world startup using real production functions and stubs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]
ENGINE = Path(os.environ.get("EW_RC7_ENGINE", ROOT / "engines/expansion-native"))

class GeneratedRuntime(unittest.TestCase):
    def test_startup_rejects_invalid_and_online_areas(self):
        src = (ENGINE / 'src/world/world_runtime.c').read_text()
        code = r'''#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
typedef int bool8;
#define TRUE 1
#define FALSE 0
static const char *sGeneratedMapPath;
static int loads, inits;
static bool LoadGeneratedMapTemplate(const char *path) { loads++; return strcmp(path, "valid") == 0; }
static bool GeneratedMap_InitXLProgress(const char *path, bool8 enabled) { inits++; return path && enabled; }
''' + function(src, 'WorldRuntime_ConfigureGenerated') + r'''
int main(void) {
 unsetenv("EW_WORLD_CONFIG");
 if (!WorldRuntime_ConfigureGenerated(NULL, NULL, FALSE)) return 1;
 if (WorldRuntime_ConfigureGenerated(NULL, NULL, TRUE)) return 2;
 if (WorldRuntime_ConfigureGenerated("bad", "save", FALSE)) return 3;
 if (WorldRuntime_ConfigureGenerated("valid", NULL, TRUE)) return 4;
 if (!WorldRuntime_ConfigureGenerated("valid", "save", TRUE)) return 5;
 if (!sGeneratedMapPath || strcmp(sGeneratedMapPath, "valid") || inits != 2 || loads != 3) return 6;
 setenv("EW_WORLD_CONFIG", "world", 1);
 if (WorldRuntime_ConfigureGenerated("valid", "save", FALSE)) return 7;
 if (loads != 3) return 8;
 return 0;
}'''
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            (p / 'test.c').write_text(code)
            q = subprocess.run(['cc', '-std=gnu17', '-Wall', '-Wextra', '-Werror', str(p / 'test.c'), '-o', str(p / 'test')], capture_output=True, text=True)
            self.assertEqual(q.returncode, 0, q.stderr)
            q = subprocess.run([str(p / 'test')], capture_output=True, text=True)
            self.assertEqual(q.returncode, 0, q.stderr)
