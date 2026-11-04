"""Compile the real POSIX save helper and exercise descriptor ownership."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('gcc'), 'gcc required')
class NativeSaveIoTests(unittest.TestCase):
    def test_held_inode_lock_and_position_independent_flash_read(self):
        source = r'''
#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include "platform/native_save.h"
int main(int argc, char **argv)
{
    FILE *owner, *other;
    char bytes[9] = {0};
    (void)argc;
    owner = NativeSave_Open(argv[1]);
    assert(owner != NULL);
    assert(fcntl(fileno(owner), F_GETFD) & FD_CLOEXEC);
    assert(NativeSave_Open(argv[1]) == NULL);
    assert(fwrite("original", 1, 8, owner) == 8);
    assert(fflush(owner) == 0);
    assert(ftell(owner) == 8);
    assert(rename(argv[1], argv[2]) == 0);
    other = fopen(argv[1], "wb");
    assert(other != NULL);
    assert(fwrite("new data", 1, 8, other) == 8);
    assert(fclose(other) == 0);
    assert(NativeSave_Read(owner, 0, bytes, 8));
    assert(memcmp(bytes, "original", 8) == 0);
    assert(ftell(owner) == 8);
    assert(!NativeSave_Read(owner, 99, bytes, 1));
    assert(!NativeSave_Read(NULL, 0, bytes, 1));
    assert(NativeSave_Open(argv[2]) == NULL);
    assert(fclose(owner) == 0);
    owner = NativeSave_Open(argv[2]);
    assert(owner != NULL);
    assert(fclose(owner) == 0);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='ew-save-io-') as tmp:
            root = Path(tmp)
            fixture = root / 'fixture.c'
            fixture.write_text(source)
            binary = root / 'fixture'
            subprocess.run(['gcc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-DPORTABLE',
                            '-iquote', str(ROOT / 'include'), str(fixture),
                            str(ROOT / 'src/platform/native_save.c'), '-o', str(binary)],
                           check=True, capture_output=True, text=True)
            subprocess.run([str(binary), str(root / 'game.sav'), str(root / 'held.sav')],
                           check=True, timeout=10, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
