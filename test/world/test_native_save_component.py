"""Compile production save I/O only. Never launch SDL, AgbMain or a game.

Disposable ordinary byte fixtures establish file ownership, not native gameplay
acceptance or host-exit autosaving.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def function(source, name):
    import re
    match = re.search(r'^(?:static[ \t]+)?(?:bool|void)[ \t]+' + re.escape(name) + r'\([^;{}]*\)\s*\{', source, re.M)
    if not match:
        raise AssertionError('missing production definition ' + name)
    depth = 1
    end = source.index('{', match.start()) + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


@unittest.skipUnless(os.name == 'posix' and shutil.which('gcc'), 'POSIX gcc required')
class NativeSaveComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='save-component-build-')
        root = Path(cls.build.name)
        code = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "platform/native_file.h"
#if __has_include("platform/native_save.h")
#include "platform/native_save.h"
#endif
#define DBGPRINTF(...) ((void)0)
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
static unsigned char FLASH_BASE[131072];
static FILE *sSaveFile;
static const char *sSavePath;
static const struct {struct {unsigned shift;} sector;} flash = {{12}}, *gFlash=&flash;
'''
        source = (ROOT / 'src/platform/sdl2.c').read_text()
        for name in ('ReadSaveFile', 'StoreSaveFile', 'Platform_ReadFlash', 'CloseSaveFile'):
            code += function(source, name) + '\n'
        code += r'''
int main(int argc, char **argv)
{
    char bytes[9] = {0};
    (void)argc;
    (void)StoreSaveFile;
    sSavePath = argv[2];
    ReadSaveFile(sSavePath);
    if (!sSaveFile) return 23;
    if (strcmp(argv[1], "hold") == 0)
    {
        puts("ready"); fflush(stdout);
        for (int c; (c=getchar()) != EOF && c != 'q'; )
        {
            if (c == 'w')
            {
                memcpy(FLASH_BASE, "changed!", 8);
                puts(StoreSaveFile() ? "stored" : "refused"); fflush(stdout);
                continue;
            }
            if (c != 'r') continue;
            Platform_ReadFlash(0, 0, (u8 *)bytes, 8);
            puts(bytes); fflush(stdout);
        }
    }
    CloseSaveFile();
    return 0;
}
'''
        (root / 'probe.c').write_text(code)
        cls.binary = root / 'probe'
        command = ['gcc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
                   '-DPORTABLE', '-iquote', str(ROOT / 'include'), str(root / 'probe.c')]
        helper = ROOT / 'src/platform/native_save.c'
        if helper.exists():
            command.append(str(helper))
        if os.environ.get('NATIVE_SAVE_SANITIZE') == '1':
            command += ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-pie', '-no-pie']
        command += ['-o', str(cls.binary)]
        built = subprocess.run(command, capture_output=True, text=True)
        if built.returncode:
            raise AssertionError(built.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='save-component-files-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'alice.sav'
        self.path.write_bytes(b'original')
        self.other = self.root / 'bob.sav'
        self.other.write_bytes(b'partner!')

    def attempt(self, path):
        return subprocess.run([str(self.binary), 'open', str(path)], capture_output=True,
                              text=True, timeout=3)

    def hold(self):
        proc = subprocess.Popen([str(self.binary), 'hold', str(self.path)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def close():
            if proc.poll() is None:
                proc.communicate('q\n', timeout=3)
            else:
                proc.communicate()
        self.addCleanup(close)
        assert proc.stdout is not None
        self.assertEqual(proc.stdout.readline().strip(), 'ready')
        return proc

    def test_second_native_save_owner_refused_without_touching_peer(self):
        owner = self.hold()
        second = self.attempt(self.path)
        self.assertNotEqual(second.returncode, 0, 'second production save owner was admitted')
        self.assertEqual(self.attempt(self.other).returncode, 0, 'independent trainer blocked')
        self.assertEqual(self.path.read_bytes(), b'original')
        self.assertEqual(self.other.read_bytes(), b'partner!')
        owner.communicate('q\n', timeout=3)
        self.assertEqual(self.attempt(self.path).returncode, 0, 'ownership not released')

    def test_flash_read_stays_with_held_inode_after_path_replacement(self):
        owner = self.hold()
        held = self.root / 'held.sav'
        self.path.rename(held)
        self.path.write_bytes(b'replaced')
        assert owner.stdin is not None and owner.stdout is not None
        owner.stdin.write('r\n'); owner.stdin.flush()
        self.assertEqual(owner.stdout.readline().strip(), 'original', 'read a different save by pathname')
        self.assertNotEqual(self.attempt(held).returncode, 0)
        self.assertEqual(self.path.read_bytes(), b'replaced')
        self.assertEqual(self.other.read_bytes(), b'partner!')

    def test_symlink_and_hardlink_save_aliases_refused(self):
        sym = self.root / 'symbolic.sav'
        sym.symlink_to(self.path)
        self.assertNotEqual(self.attempt(sym).returncode, 0, 'save symlink admitted')
        alias = self.root / 'alias.sav'
        os.link(self.path, alias)
        self.assertNotEqual(self.attempt(alias).returncode, 0, 'hardlinked save admitted')
        self.assertEqual(self.path.read_bytes(), b'original')

    def test_fifo_refused_without_blocking(self):
        fifo = self.root / 'pipe.sav'
        os.mkfifo(fifo)
        try:
            result = self.attempt(fifo)
        except subprocess.TimeoutExpired:
            self.fail('production save open blocked on FIFO')
        self.assertNotEqual(result.returncode, 0)

    def test_ordinary_store_retains_lock_and_peer_save(self):
        owner = self.hold()
        assert owner.stdin is not None and owner.stdout is not None
        owner.stdin.write('w\n'); owner.stdin.flush()
        self.assertEqual(owner.stdout.readline().strip(), 'stored')
        self.assertEqual(self.path.read_bytes()[:8], b'changed!')
        self.assertNotEqual(self.attempt(self.path).returncode, 0)
        self.assertEqual(self.other.read_bytes(), b'partner!')

    def test_alias_added_after_open_prevents_write_and_removal_allows_retry(self):
        owner = self.hold()
        alias = self.root / 'late-alias.sav'
        os.link(self.path, alias)
        assert owner.stdin is not None and owner.stdout is not None
        owner.stdin.write('w\n'); owner.stdin.flush()
        self.assertEqual(owner.stdout.readline().strip(), 'refused')
        self.assertEqual(alias.read_bytes(), b'original')
        self.assertEqual(self.path.read_bytes(), b'original')
        self.assertEqual(self.other.read_bytes(), b'partner!')
        alias.unlink()
        self.assertNotEqual(self.attempt(self.path).returncode, 0)
        owner.stdin.write('w\n'); owner.stdin.flush()
        self.assertEqual(owner.stdout.readline().strip(), 'stored')
        self.assertEqual(self.path.read_bytes()[:8], b'changed!')
        self.assertEqual(self.other.read_bytes(), b'partner!')

    def test_unlinked_owned_file_cannot_claim_persistent_save(self):
        owner = self.hold()
        self.path.unlink()
        assert owner.stdin is not None and owner.stdout is not None
        owner.stdin.write('w\n'); owner.stdin.flush()
        self.assertEqual(owner.stdout.readline().strip(), 'refused')
        self.assertFalse(self.path.exists())
        self.assertEqual(self.other.read_bytes(), b'partner!')

    def test_new_save_is_private_and_invalid_path_is_safe(self):
        path = self.root / 'new.sav'
        self.assertEqual(self.attempt(path).returncode, 0)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.attempt(self.root / 'absent' / 'save').returncode, 23)
        self.assertEqual(self.attempt(self.root).returncode, 23)

    def test_crashed_owner_releases_exclusive_save(self):
        owner = self.hold()
        self.assertNotEqual(self.attempt(self.path).returncode, 0)
        owner.kill()
        owner.communicate(timeout=3)
        self.assertEqual(self.attempt(self.path).returncode, 0)
        self.assertEqual(self.path.read_bytes(), b'original')


if __name__ == '__main__':
    unittest.main()
