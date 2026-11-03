"""Pure native bridge contracts; compiles isolated C, not a game or Windows runtime."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/platform/world_bridge.c'
SCRATCH = ROOT.parent / 'emerald-world-research'


class WindowsBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text()
        SCRATCH.mkdir(exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(prefix='windows-bridge-', dir=SCRATCH)
        cls.path = Path(cls.tmp.name)
        compiler = shutil.which(os.environ.get('CC', 'cc'))
        if not compiler:
            raise unittest.SkipTest('C compiler required for isolated config test')
        # Linux stand-ins for the OS primitives. These exercise the actual helper
        # and file operations, not Windows' implementation of UTF-16 conversion.
        (cls.path / 'windows.h').write_text(r'''
#include <assert.h>
#include <errno.h>
#include <locale.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#define CP_UTF8 65001
#define MB_ERR_INVALID_CHARS 8
#define MOVEFILE_REPLACE_EXISTING 1
static int MultiByteToWideChar(unsigned cp, unsigned flags, const char *text,
                              int bytes, wchar_t *out, int capacity) {
    size_t n;
    assert(cp == CP_UTF8 && flags == MB_ERR_INVALID_CHARS && bytes == -1);
    assert(setlocale(LC_CTYPE, "C.UTF-8"));
    n = mbstowcs(NULL, text, 0);
    if (n == (size_t)-1) return 0;
    if (out) {
        assert(capacity == (int)n + 1);
        if (mbstowcs(out, text, capacity) == (size_t)-1) return 0;
    }
    return (int)n + 1;
}
static char *MockUTF8(const wchar_t *wide) {
    size_t n = wcstombs(NULL, wide, 0);
    char *text;
    assert(n != (size_t)-1);
    text = malloc(n + 1);
    assert(text);
    wcstombs(text, wide, n + 1);
    return text;
}
static FILE *_wfopen(const wchar_t *path, const wchar_t *mode) {
    char *p = MockUTF8(path), *m = MockUTF8(mode);
    FILE *f = fopen(p, m);
    free(p); free(m);
    return f;
}
static int MoveFileExW(const wchar_t *from, const wchar_t *to, unsigned flags) {
    char *f = MockUTF8(from), *t = MockUTF8(to);
    int result;
    assert(flags == MOVEFILE_REPLACE_EXISTING);
    result = rename(f, t);
    free(f); free(t);
    return result == 0;
}
''')
        identifier = cls.source.split('static bool8 Identifier(', 1)[1].split('/* Decode only', 1)[0]
        init = cls.source.split('bool8 WorldBridge_Init(', 1)[1].split('/* A snapshot', 1)[0]
        harness = '''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <limits.h>
#include "platform/native_file.h"
#define bool8 int
#define TRUE 1
#define FALSE 0
#define INVALID_SOCKET (~(unsigned long long)0)
#define MAKEWORD(a,b) ((a)|((b)<<8))
typedef struct { unsigned short wVersion; } WSADATA;
static int WSAStartup(int v, WSADATA *d) { d->wVersion=v; return 0; }
static int WSACleanup(void) { return 0; }
static struct { unsigned long long fd; int enabled, winsockStarted;
unsigned loopbackPort; char loopbackToken[65], socketPath[108], trainer[25], token[65], telemetry[1024]; } sWorld;
static bool8 Identifier(''' + identifier + '\nbool8 WorldBridge_Init(' + init + '''
int main(int argc, char **argv) {
    int ok = WorldBridge_Init(argc > 1 ? argv[1] : NULL);
    if (ok && argc > 1) printf("%u|%s|%s", sWorld.loopbackPort, sWorld.trainer, sWorld.telemetry);
    return ok ? 0 : 1;
}
'''
        c = cls.path / 'config.c'
        c.write_text(harness)
        cls.exe = cls.path / 'config'
        cls.compile_flags = ['-std=gnu99', '-DPORTABLE', '-I', str(cls.path),
                             '-iquote', str(ROOT / 'include')]
        subprocess.run([compiler, *cls.compile_flags, '-D_WIN32', str(c), '-o', str(cls.exe)], check=True, capture_output=True)
        cls.unix_exe = cls.path / 'config-unix'
        subprocess.run([compiler, *cls.compile_flags, str(c), '-o', str(cls.unix_exe)], check=True, capture_output=True)
        native = cls.path / 'native.c'
        native.write_text(r'''
#include "platform/native_file.h"
int main(int argc, char **argv) {
    FILE *f;
    if (argc == 1) {
        /* Invalid UTF-8 must fail closed, never fall back to the ANSI codepage. */
        if (NativeFile_Open("\xff", "wb") || errno != EILSEQ) return 1;
        if (NativeFile_Replace("\xff", "untouched") != -1) return 2;
        if (NativeFile_Replace("untouched", "\xff") != -1) return 3;
        if (NativeFile_Wide(NULL) || errno != EINVAL) return 4;
        return 0;
    }
    f = NativeFile_Open(argv[1], "wb");
    if (!f) return 5;
    if (fputs("new unicode data", f) < 0 || fclose(f)) return 6;
    return NativeFile_Replace(argv[1], argv[2]) ? 7 : 0;
}
''')
        cls.native_exe = cls.path / 'native'
        subprocess.run([compiler, *cls.compile_flags, '-D_WIN32', str(native),
                        '-o', str(cls.native_exe)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def config(self, text):
        path = self.path / 'world.conf'
        path.write_text(text)
        return subprocess.run([str(self.exe), str(path)], capture_output=True, text=True)

    def valid(self):
        return ('loopback_port 12345\nloopback_token ' + 'ab' * 32 +
                '\ntrainer alice\ntoken ' + 'cd' * 32 +
                '\ntelemetry C:/Users/A Friend/world state.json\n')

    def test_mock_windows_unicode_config_open_and_telemetry_path(self):
        path = self.path / 'A Friend é 中文'
        path.mkdir(exist_ok=True)
        config = path / '配置.conf'
        telemetry = str(path / 'état 世界.json')
        config.write_text(self.valid().replace('C:/Users/A Friend/world state.json', telemetry),
                          encoding='utf-8')
        result = subprocess.run([str(self.exe), str(config)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '12345|alice|' + telemetry)

    def test_mock_windows_unicode_open_and_repeated_replace(self):
        directory = self.path / 'é 中文 files'
        directory.mkdir(exist_ok=True)
        temporary = directory / '遥测.json.tmp'
        target = directory / '遥测.json'
        for old in ('old contents', 'previous telemetry'):
            target.write_text(old, encoding='utf-8')
            result = subprocess.run([str(self.native_exe), str(temporary), str(target)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_text(), 'new unicode data')
            self.assertFalse(temporary.exists())
        result = subprocess.run([str(self.native_exe)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_text(), 'new unicode data')

    def test_native_utf8_file_boundaries(self):
        header = ROOT / 'include/platform/native_file.h'
        self.assertTrue(header.exists(), 'UTF-8 native file boundary is missing')
        native = header.read_text()
        for required in ('CP_UTF8', 'MB_ERR_INVALID_CHARS', 'MultiByteToWideChar',
                         '_wfopen', 'MoveFileExW', 'MOVEFILE_REPLACE_EXISTING'):
            self.assertIn(required, native)
        for relative in ('src/platform/world_bridge.c', 'src/platform/sdl2.c',
                         'src/platform/settings.c'):
            source = (ROOT / relative).read_text()
            self.assertIn('"platform/native_file.h"', source)
            self.assertNotRegex(source, r'(?<![A-Za-z_])fopen\(')
            self.assertNotIn('MoveFileExA', source)
        self.assertIn('NativeFile_Replace(path, sWorld.telemetry)', self.source)

    def test_windows_config_accepts_local_gateway_and_path_spaces(self):
        result = self.config(self.valid())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '12345|alice|C:/Users/A Friend/world state.json')

    def test_unix_config_and_disabled_mode_remain_supported(self):
        path = self.path / 'unix.conf'
        path.write_text('socket /tmp/world.sock\ntrainer alice\ntoken ' + 'cd' * 32 +
                        '\ntelemetry /tmp/world.json\n')
        result = subprocess.run([str(self.unix_exe), str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for exe in (self.exe, self.unix_exe):
            self.assertEqual(subprocess.run([str(exe)], capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run([str(self.exe), str(path)], capture_output=True).returncode, 1)

    def test_wire_preface_precedes_unchanged_hello(self):
        self.assertIn('static void QueueHello(void)', self.source)
        helper = self.source.split('static void QueueHello(void)', 1)[1].split('static void Flush', 1)[0]
        c = self.path / 'wire.c'
        c.write_text('#include <stdio.h>\n#include <string.h>\n'
                     'static struct { char output[4096], loopbackToken[65], trainer[25], token[65]; '
                     'size_t outputSize; } sWorld;\nstatic void QueueHello(void)' + helper +
                     '\nint main(void) { memset(sWorld.loopbackToken, 97, 64); '
                     'memset(sWorld.token, 98, 64); strcpy(sWorld.trainer, "alice"); '
                     'QueueHello(); fwrite(sWorld.output, 1, sWorld.outputSize, stdout); return 0; }')
        for define, prefix in [(['-D_WIN32'], 'EWLOCAL1 ' + 'a' * 64 + '\n'), ([], '')]:
            exe = self.path / 'wire'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu99', *define, str(c), '-o', str(exe)], check=True, capture_output=True)
            result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout, prefix + 'HELLO 1 alice ' + 'b' * 64 + ' SOCIAL\n')

    def test_windows_transport_and_atomic_replace_guards(self):
        for required in ('SOCKET fd;', 'INVALID_SOCKET', 'WSAStartup', 'WSACleanup',
                         'closesocket', 'ioctlsocket', 'WSAGetLastError', 'WSAEWOULDBLOCK',
                         'select(', 'htonl(INADDR_LOOPBACK)', 'NativeFile_Replace'):
            self.assertIn(required, self.source)
        self.assertNotIn('requires Unix sockets', self.source)
        self.assertIn('-lws2_32', (ROOT / 'Makefile').read_text())
        result = subprocess.run([os.environ.get('CC', 'cc'), '-E', '-P', str(SOURCE)], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), '', 'non-PORTABLE/GBA file must remain empty')

    def test_windows_config_rejects_unknown_duplicate_and_bad_values(self):
        base = self.valid()
        cases = [base + 'host 8.8.8.8\n', base + 'socket /tmp/sock\n',
                 base + 'loopback_port 55\n', base.replace('12345', '0'),
                 base.replace('12345', '65536'), base.replace('12345', '+12'),
                 base.replace('12345', '12 extra'), base.replace('ab' * 32, 'z' * 64),
                 base.replace('ab' * 32, 'ab' * 31), base.replace('cd' * 32, 'x' * 64),
                 base.replace('trainer alice', 'trainer a!'),
                 base.replace('trainer alice', 'trainer alice\x00hidden'),
                 base.rstrip('\n') + '\x00hidden',
                 base.replace('loopback_port 12345\n', ''),
                 base.replace('loopback_token ' + 'ab' * 32 + '\n', '')]
        for text in cases:
            with self.subTest(text=text[:30]):
                result = self.config(text)
                self.assertEqual(result.returncode, 1)
                self.assertNotIn('ab' * 32, result.stderr)
                self.assertNotIn('cd' * 32, result.stderr)


if __name__ == '__main__':
    unittest.main()
