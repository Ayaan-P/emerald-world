"""Compile and exercise the actual native control module, without a game build."""
import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PlayerControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / 'research').mkdir(exist_ok=True)
        cls.scratch = tempfile.TemporaryDirectory(dir=ROOT / 'research')
        out = Path(cls.scratch.name) / 'control.so'
        harness = Path(cls.scratch.name) / 'control.c'
        harness.write_text('''#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
static int probeMode;
void TestProbeMode(int mode) { probeMode = mode; }
static int TestConnect(int fd, const struct sockaddr *addr, socklen_t size) {
    if (probeMode == 1 || probeMode == 5) {
        errno = probeMode == 1 ? EACCES : EAGAIN;
        return -1;
    }
    int result = connect(fd, addr, size), error = errno;
    if (result < 0 && error == ECONNREFUSED && probeMode == 2) {
        const struct sockaddr_un *un = (const struct sockaddr_un *)addr;
        char old[128];
        snprintf(old, sizeof(old), "%s.old", un->sun_path);
        if (rename(un->sun_path, old)) return 0;
        int replacement = socket(AF_UNIX, SOCK_STREAM, 0);
        if (replacement < 0 || bind(replacement, addr, size)) return 0;
        close(replacement);
    }
    if (result < 0 && error == ECONNREFUSED && probeMode == 3)
        unlink(((const struct sockaddr_un *)addr)->sun_path);
    errno = error;
    return result;
}
static int TestStat(int dir, const char *path, struct stat *st, int flags) {
    int result = fstatat(dir, path, st, flags);
    if (!result && S_ISSOCK(st->st_mode) && probeMode == 6)
        st->st_uid = geteuid() + 1;
    return result;
}
#define connect TestConnect
#define fstatat TestStat
#include "''' + str(ROOT / 'src/platform/player_control.c') + '''"
void TestSmallSendBuffer(void) { int n = 1024;
    setsockopt(s.client, SOL_SOCKET, SO_SNDBUF, &n, sizeof(n)); }
unsigned TestPendingBytes(void) { return s.size - s.sent; }
#ifdef TEST_EXECUTABLE
static void State(FILE *f, uint32_t frame) { fprintf(f, "{\\"frame\\":%u}", frame); }
static bool Shot(FILE *f) { return fputs("P6\\n1 1\\n255\\nabc", f) >= 0; }
int main(int argc, char **argv) {
    if (argc != 3 || !PlayerControl_Init(argv[1], argv[2], State, Shot)) return 2;
    puts("ready"); fflush(stdout);
    for (uint32_t frame = 1;; frame++) {
        PlayerControl_BeforeFrame(); PlayerControl_AfterFrame(frame); usleep(1000);
    }
}
#endif
''')
        cls.fixture = Path(cls.scratch.name) / 'control-native'
        subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                        '-DPORTABLE', '-DTEST_EXECUTABLE', '-iquote' + str(ROOT / 'include'),
                        str(harness), '-o', str(cls.fixture)], check=True)
        subprocess.run(['cc', '-shared', '-fPIC', '-std=gnu99', '-Wall', '-Wextra',
                        '-Werror', '-DPORTABLE', '-iquote' + str(ROOT / 'include'),
                        str(harness), '-o', str(out)], check=True)
        cls.lib = ctypes.CDLL(str(out))
        cls.lib.PlayerControl_Init.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p]
        cls.lib.PlayerControl_Init.restype = ctypes.c_bool
        cls.lib.PlayerControl_Buttons.restype = ctypes.c_uint16
        cls.lib.PlayerControl_AfterFrame.argtypes = [ctypes.c_uint32]
        libc = ctypes.CDLL(None)
        libc.fputs.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        cls.state = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint32)(
            lambda f, frame: libc.fputs(json.dumps({'frame': frame}).encode() + b'\n', f))
        cls.shot = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p)(
            lambda f: libc.fputs(b'P6\n1 1\n255\nabc', f) >= 0)

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=self.scratch.name)
        self.path = Path(self.tmp.name) / 'control.sock'
        self.save = Path(self.tmp.name) / 'trainer.sav'
        self.assertTrue(self.lib.PlayerControl_Init(os.fsencode(self.path), os.fsencode(self.save), self.state, self.shot))
        self.client = socket.socket(socket.AF_UNIX)
        self.client.connect(str(self.path))
        self.client.settimeout(.1)
        self.lib.PlayerControl_BeforeFrame()

    def tearDown(self):
        self.client.close()
        self.lib.PlayerControl_Close()
        self.tmp.cleanup()

    def send(self, request):
        self.client.sendall(json.dumps(request).encode() + b'\n')
        self.lib.PlayerControl_BeforeFrame()

    def reply(self):
        self.lib.PlayerControl_BeforeFrame()
        data = self.client.recv(8192)
        self.assertEqual(data.count(b'\n'), 1, 'response must be one JSONL line')
        return json.loads(data)

    def test_observe_and_permissions(self):
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.send({'id': 1, 'op': 'observe'})
        self.assertEqual(self.reply(), {'id': 1, 'ok': True, 'state': {'frame': 0}})

    def test_press_completes_after_executed_frames(self):
        self.send({'id': 2, 'op': 'press', 'buttons': ['UP', 'A'], 'frames': 3})
        for frame in range(1, 4):
            self.assertEqual(self.lib.PlayerControl_Buttons(), 65)
            with self.assertRaises(socket.timeout):
                self.client.recv(8192)
            self.lib.PlayerControl_AfterFrame(frame)
        self.assertEqual(self.lib.PlayerControl_Buttons(), 0)
        self.assertEqual(self.reply()['state']['frame'], 3)

    def test_disconnect_releases(self):
        self.send({'id': 1, 'op': 'press', 'buttons': ['B'], 'frames': 120})
        self.client.close()
        self.lib.PlayerControl_BeforeFrame()
        self.assertEqual(self.lib.PlayerControl_Buttons(), 0)

    def test_partial_request_and_busy(self):
        self.client.sendall(b'{"id":7,"op":')
        self.lib.PlayerControl_BeforeFrame()
        self.client.sendall(b'"press","buttons":["LEFT"],"frames":120}\n')
        self.lib.PlayerControl_BeforeFrame()
        self.assertEqual(self.lib.PlayerControl_Buttons(), 32)
        self.send({'id': 8, 'op': 'observe'})
        self.assertEqual(self.reply()['error'], 'busy')
        self.assertEqual(self.lib.PlayerControl_Buttons(), 0)

    def test_oversized_rejected(self):
        self.client.sendall(b' ' * 8192)
        self.lib.PlayerControl_BeforeFrame()
        self.assertEqual(self.reply()['error'], 'oversized')

    def test_oversized_drops_tail_and_releases(self):
        self.send({'id': 1, 'op': 'press', 'buttons': ['UP'], 'frames': 120})
        self.client.sendall(b'x' * 8191 + b'{"id":2,"op":"press","buttons":["A"],"frames":120}\n')
        self.lib.PlayerControl_BeforeFrame()
        self.assertEqual(self.reply()['error'], 'oversized')
        self.assertEqual(self.lib.PlayerControl_Buttons(), 0)
        try:
            self.assertEqual(self.client.recv(8192), b'')
        except ConnectionResetError:
            pass  # Closing with an unread oversized tail may reset the stream.

    def test_second_client_busy(self):
        with socket.socket(socket.AF_UNIX) as other:
            other.connect(str(self.path))
            other.settimeout(.1)
            self.lib.PlayerControl_BeforeFrame()
            self.assertEqual(json.loads(other.recv(8192))['error'], 'busy')

    def test_screenshot_symlink_not_followed(self):
        target = self.path.parent / 'untouched'
        target.write_text('safe')
        (self.path.parent / 'screenshot.ppm').symlink_to(target)
        self.send({'id': 1, 'op': 'screenshot'})
        self.assertFalse(self.reply()['ok'])
        self.assertEqual(target.read_text(), 'safe')

    def test_cleanup_preserves_replacement_inode(self):
        self.path.unlink()
        self.path.write_text('replacement')
        self.lib.PlayerControl_Close()
        self.assertEqual(self.path.read_text(), 'replacement')

    def test_screenshot_fixed_path(self):
        self.send({'id': 3, 'op': 'screenshot'})
        result = self.reply()
        self.assertEqual(result['screenshot'], str(self.path.parent / 'screenshot.ppm'))
        self.assertTrue(Path(result['screenshot']).read_bytes().startswith(b'P6'))

    def use_state(self, payload):
        libc = ctypes.CDLL(None)
        libc.fputs.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        self.custom_state = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint32)(
            lambda f, frame: libc.fputs(json.dumps(dict(payload, frame=frame)).encode() + b'\n', f))
        self.lib.PlayerControl_Close()
        self.client.close()
        self.assertTrue(self.lib.PlayerControl_Init(
            os.fsencode(self.path), os.fsencode(self.save), self.custom_state, self.shot))
        self.client = socket.socket(socket.AF_UNIX)
        self.client.connect(str(self.path))
        self.client.settimeout(.1)
        self.lib.PlayerControl_BeforeFrame()

    def large_reply(self):
        data = b''
        for _ in range(100):
            self.lib.PlayerControl_BeforeFrame()
            data += self.client.recv(8192)
            if data.endswith(b'\n'):
                self.assertEqual(data.count(b'\n'), 1)
                return json.loads(data)
        self.fail('bounded response did not finish')

    def test_large_state_observe_screenshot_and_press_ack(self):
        payload = {'padding': 'x' * 60000}
        self.use_state(payload)
        for request in [{'id': 10, 'op': 'observe'}, {'id': 11, 'op': 'screenshot'},
                        {'id': 12, 'op': 'press', 'buttons': ['UP'], 'frames': 3}]:
            self.send(request)
            if request['op'] == 'press':
                for frame in range(1, 4):
                    self.assertEqual(self.lib.PlayerControl_Buttons(), 64)
                    with self.assertRaises(socket.timeout):
                        self.client.recv(8192)
                    self.lib.PlayerControl_AfterFrame(frame)
                self.assertEqual(self.lib.PlayerControl_Buttons(), 0)
            result = self.large_reply()
            self.assertTrue(result['ok'])
            self.assertEqual(result['id'], request['id'])
            self.assertEqual(result['state']['padding'], payload['padding'])
            self.assertEqual(result['state']['frame'], 3 if request['op'] == 'press' else 0)
            if request['op'] == 'screenshot':
                self.assertTrue(Path(result['screenshot']).read_bytes().startswith(b'P6'))

    def test_state_size_failure_is_clean_json_and_connection_recovers(self):
        for length in (65536, 131072):
            with self.subTest(length=length):
                payload = {'padding': 'x' * length}
                self.use_state(payload)
                for op in ('observe', 'screenshot', 'press'):
                    request = {'id': 22, 'op': op}
                    if op == 'press':
                        request.update(buttons=['A'], frames=1)
                    self.send(request)
                    if op == 'press':
                        self.lib.PlayerControl_AfterFrame(1)
                    self.assertEqual(self.reply(), {'id': 22, 'ok': False, 'error': 'state_too_large'})
                    self.assertEqual(self.lib.PlayerControl_Buttons(), 0)
                payload.clear()
                self.send({'id': 23, 'op': 'observe'})
                self.assertTrue(self.reply()['ok'])

    def test_partial_write_does_not_block_game_frames(self):
        libc = ctypes.CDLL(None)
        libc.fputs.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        state = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint32)(
            lambda f, frame: libc.fputs(json.dumps({'padding': 'x' * 48000}).encode() + b'\n', f))
        self.lib.PlayerControl_Close()
        self.client.close()
        self.assertTrue(self.lib.PlayerControl_Init(os.fsencode(self.path), os.fsencode(self.save), state, self.shot))
        self.client = socket.socket(socket.AF_UNIX)
        self.client.connect(str(self.path))
        self.client.settimeout(.1)
        self.lib.PlayerControl_BeforeFrame()
        self.lib.TestSmallSendBuffer()
        self.send({'id': 1, 'op': 'observe'})
        self.assertGreater(self.lib.TestPendingBytes(), 0)
        start = time.monotonic()
        for frame in range(1, 601):
            self.lib.PlayerControl_BeforeFrame()
            self.lib.PlayerControl_AfterFrame(frame)
        self.assertLess(time.monotonic() - start, 1)
        data = self.client.recv(8192)
        while not data.endswith(b'\n'):
            self.lib.PlayerControl_BeforeFrame()
            data += self.client.recv(8192)
        self.assertEqual(len(json.loads(data)['state']['padding']), 48000)
        self.send({'id': 2, 'op': 'observe'})
        self.assertGreater(self.lib.TestPendingBytes(), 0)
        self.client.sendall(b'\x00\n')
        self.lib.PlayerControl_BeforeFrame()
        self.assertEqual(self.lib.TestPendingBytes(), 0,
                         'pipelining cannot overwrite a partially sent JSON response')

    def test_malformed_rejected(self):
        for line in [b'{"id":1,"op":"observe","op":"press"}',
                     b'{"id":1,"op":"press","buttons":["UP"],"frames":0}',
                     b'{"id":1,"op":"press","buttons":["CHEAT"],"frames":1}',
                     b'{"id":01,"op":"observe"}', b'{"id":1,"op":"observe","path":"/tmp/x"}']:
            self.client.sendall(line + b'\n')
            self.lib.PlayerControl_BeforeFrame()
            self.assertFalse(self.reply()['ok'])

    def test_sdl_hooks_and_bad_config(self):
        source = (ROOT / 'src/platform/sdl2.c').read_text()
        self.assertIn('"--player-control"', source)
        self.assertLess(source.index('PlayerControl_Init('), source.index('ReadSaveFile(sSavePath);'))
        self.assertIn('PlayerControl_BeforeFrame();', source)
        self.assertIn('PlayerControl_AfterFrame(', source)

    def test_native_bad_config_before_save_open(self):
        binary = os.environ.get('PLAYER_CONTROL_NATIVE_BINARY')
        if not binary:
            self.skipTest('parent must supply PLAYER_CONTROL_NATIVE_BINARY after its build')
        if binary:
            bad = Path(self.tmp.name) / 'bad.sock'
            bad.write_text('untouched')
            save = Path(self.tmp.name) / 'never-open.sav'
            result = subprocess.run([str(Path(binary).resolve()), '--player-control', str(bad),
                                     '--save', str(save)], capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'player control', result.stderr.lower())
            self.assertFalse(save.exists())
            self.assertEqual(bad.read_text(), 'untouched')

    def test_partial_request_timeout(self):
        self.client.sendall(b'{')
        self.lib.PlayerControl_BeforeFrame()
        time.sleep(5.05)
        self.lib.PlayerControl_BeforeFrame()
        self.assertEqual(self.lib.PlayerControl_Buttons(), 0)
        self.assertEqual(self.client.recv(8192), b'')

    def test_idle_game_frames_are_not_gated_on_requests(self):
        for frame in range(1, 601):
            self.lib.PlayerControl_BeforeFrame()
            self.lib.PlayerControl_AfterFrame(frame)
        self.send({'id': 1, 'op': 'observe'})
        self.assertEqual(self.reply()['state']['frame'], 600)

    def test_stale_same_owner_socket_recovered(self):
        self.lib.PlayerControl_Close()
        with socket.socket(socket.AF_UNIX) as stale:
            stale.bind(str(self.path))
        self.assertTrue(self.lib.PlayerControl_Init(
            os.fsencode(self.path), os.fsencode(self.save), self.state, self.shot))
        self.client.close()
        self.client = socket.socket(socket.AF_UNIX)
        self.client.settimeout(.1)
        self.client.connect(str(self.path))
        self.send({'id': 20, 'op': 'observe'})
        self.assertTrue(self.reply()['ok'])

    def test_native_fixture_sigkill_restart_and_live_rejection(self):
        self.lib.PlayerControl_Close()
        command = [str(self.fixture), str(self.path), str(self.save)]
        def launch():
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.addCleanup(stop, process)
            assert process.stdout is not None
            import select
            self.assertTrue(select.select([process.stdout], [], [], 3)[0], 'fixture startup timed out')
            self.assertEqual(process.stdout.readline(), b'ready\n')
            return process
        def stop(process):
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=3)
        first = launch()
        inode = self.path.stat().st_ino
        rejected = subprocess.run(command, capture_output=True, timeout=3)
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(self.path.stat().st_ino, inode)
        first.terminate()
        first.wait(timeout=3)
        self.assertTrue(self.path.is_socket(), 'SIGTERM must leave the stale endpoint')
        killed = launch()
        killed.kill()
        killed.wait(timeout=3)
        self.assertTrue(self.path.is_socket(), 'SIGKILL must leave the stale endpoint')
        restarted = launch()
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2)
            client.connect(str(self.path))
            client.sendall(b'{"id":31,"op":"observe"}\n')
            self.assertTrue(json.loads(client.recv(8192))['ok'])
        restarted.kill()
        restarted.wait(timeout=3)

    def test_stale_probe_uncertain_foreign_or_changed_inode_fails_closed(self):
        self.lib.PlayerControl_Close()
        for mode in (1, 2, 3, 5, 6):
            with self.subTest(mode=mode):
                if self.path.exists():
                    self.path.unlink()
                with socket.socket(socket.AF_UNIX) as stale:
                    stale.bind(str(self.path))
                original = self.path.stat().st_ino
                self.lib.TestProbeMode(mode)
                try:
                    self.assertFalse(self.lib.PlayerControl_Init(
                        os.fsencode(self.path), os.fsencode(self.save), self.state, self.shot))
                finally:
                    self.lib.TestProbeMode(0)
                if mode == 3:
                    self.assertFalse(self.path.exists())
                else:
                    self.assertTrue(self.path.is_socket())
                    if mode == 2:
                        self.assertNotEqual(self.path.stat().st_ino, original)
                    else:
                        self.assertEqual(self.path.stat().st_ino, original)

    def test_nonregular_endpoint_and_linked_socket_not_reclaimed(self):
        self.lib.PlayerControl_Close()
        for kind in ('directory', 'fifo', 'linked_socket', 'symlink_socket'):
            with self.subTest(kind=kind):
                endpoint = self.path.parent / kind
                if kind == 'directory':
                    endpoint.mkdir()
                elif kind == 'fifo':
                    os.mkfifo(endpoint)
                else:
                    target = self.path.parent / (kind + '.target')
                    with socket.socket(socket.AF_UNIX) as stale:
                        stale.bind(str(target))
                    if kind == 'linked_socket':
                        os.link(target, endpoint)
                    else:
                        endpoint.symlink_to(target)
                original = endpoint.lstat()
                self.assertFalse(self.lib.PlayerControl_Init(
                    os.fsencode(endpoint), os.fsencode(self.save), self.state, self.shot))
                self.assertEqual(endpoint.lstat().st_ino, original.st_ino)

    def test_active_socket_and_symlink_rejected(self):
        with socket.socket(socket.AF_UNIX) as active:
            endpoint = self.path.parent / 'active.sock'
            active.bind(str(endpoint))
            active.listen(1)
            self.assertFalse(self.lib.PlayerControl_Init(os.fsencode(endpoint), os.fsencode(self.save), self.state, self.shot))
            self.assertTrue(endpoint.exists())
            endpoint.unlink()
            endpoint.symlink_to('missing')
            self.assertFalse(self.lib.PlayerControl_Init(os.fsencode(endpoint), os.fsencode(self.save), self.state, self.shot))
            self.assertTrue(endpoint.is_symlink())

    def test_existing_endpoint_and_wrong_profile_rejected(self):
        self.lib.PlayerControl_Close()
        self.path.write_text('keep')
        self.assertFalse(self.lib.PlayerControl_Init(os.fsencode(self.path), os.fsencode(self.save), self.state, self.shot))
        self.assertEqual(self.path.read_text(), 'keep')
        self.path.unlink()
        self.assertFalse(self.lib.PlayerControl_Init(os.fsencode(self.path), b'/different/profile/save', self.state, self.shot))


if __name__ == '__main__':
    unittest.main()
