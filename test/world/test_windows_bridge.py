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
        identifier = cls.source.split('static bool8 Identifier(', 1)[1].split('/* Decode only', 1)[0]
        init = cls.source.split('bool8 WorldBridge_Init(', 1)[1].split('/* A snapshot', 1)[0]
        harness = '''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <limits.h>
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
        subprocess.run([compiler, '-std=gnu99', '-D_WIN32', str(c), '-o', str(cls.exe)], check=True, capture_output=True)
        cls.unix_exe = cls.path / 'config-unix'
        subprocess.run([compiler, '-std=gnu99', str(c), '-o', str(cls.unix_exe)], check=True, capture_output=True)

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
                         'select(', 'htonl(INADDR_LOOPBACK)', 'MoveFileExA', 'MOVEFILE_REPLACE_EXISTING'):
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
