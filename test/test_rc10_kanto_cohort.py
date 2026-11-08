"""Check the app/engine contract against the real selected native source."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.build_expansion import PIN
from world.save_limits import EXPANSION_SAVE_MAX

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(os.environ.get('EW_RC7_ENGINE', ROOT / 'engines/expansion-native'))


class KantoCohort(unittest.TestCase):
    def test_native_pin_and_changed_source_hashes_match_manifest(self):
        manifest = json.loads((ROOT/'port/kanto-on-rc10/source-manifest.json').read_text())
        self.assertEqual(PIN, manifest['engine_commit'])
        self.assertEqual(len(manifest['files']), 44)
        for name, sha in manifest['files'].items():
            self.assertEqual(hashlib.sha256((ENGINE/name).read_bytes()).hexdigest(), sha, name)

    def test_copy_limit_matches_native_file_and_extension_headers(self):
        with tempfile.TemporaryDirectory(prefix='ew-save-bound-') as tmp:
            root = Path(tmp)
            source = root/'limit.c'
            source.write_text('''#include <stdio.h>
#include "flash.h"
#include "save_file.h"
#include "save_extension.h"
int main(void) {
 printf("%zu\\n", (size_t)(SAVE_FILE_HEADER_SIZE + FLASH_CHIP_SIZE + 8 + SAVE_EXTENSION_ENCODED_MAX));
 return 0;
}
''')
            subprocess.run(['cc', '-std=c11', '-I'+str(ENGINE/'platform'), str(source),
                            '-o', str(root/'limit')], check=True, capture_output=True)
            actual = int(subprocess.check_output([str(root/'limit')], text=True))
            self.assertEqual(EXPANSION_SAVE_MAX, actual)


if __name__ == '__main__':
    unittest.main()
