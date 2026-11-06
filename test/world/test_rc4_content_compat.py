"""Content identity is build input, not a world-rule or trainer-save claim."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ContentManifestTest(unittest.TestCase):
    def generator(self):
        spec = importlib.util.spec_from_file_location('content_generator', ROOT/'tools/content_compat.py')
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_native_getter_embeds_generated_tag_and_hello_announces_it(self):
        self.assertTrue((ROOT/'src/platform/content_compat.c').exists(), 'native getter missing')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'platform').mkdir()
            (root/'platform/content_compat.h').write_bytes((ROOT/'include/platform/content_compat.h').read_bytes())
            (root/'main.c').write_text('#include <stdio.h>\n#include "platform/content_compat.h"\n'
                                      'int main(void) { puts(ContentCompat_Id()); return 0; }\n')
            for tag in ('a'*64, 'b'*64):
                (root/'platform/content_compat_generated.h').write_text(f'#define WORLD_CONTENT_ID "{tag}"\n')
                subprocess.run(['cc', '-DPORTABLE', '-Wall', '-Wextra', '-Werror', '-I', str(root),
                                str(ROOT/'src/platform/content_compat.c'), str(root/'main.c'),
                                '-o', str(root/'getter')], check=True, capture_output=True)
                self.assertEqual(subprocess.check_output([str(root/'getter')]).decode().strip(), tag)
        bridge = (ROOT/'src/platform/world_bridge.c').read_text()
        self.assertIn('" DATA %s\\n", ContentCompat_Id()', bridge)

    def test_native_prebuild_regenerates_before_tag_object_without_full_build(self):
        makefile = (ROOT/'Makefile').read_text()
        self.assertIn('# BEGIN native content compatibility', makefile)
        block = makefile.split('# BEGIN native content compatibility\n', 1)[1].split(
            '# END native content compatibility', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'tools').mkdir()
            (root/'tools/content_compat.py').write_bytes((ROOT/'tools/content_compat.py').read_bytes())
            (root/'src').mkdir()
            (root/'src/mon.h').write_text('catalog 3')
            # Exercise the actual narrow Makefile rule, with no project build/toolchain.
            (root/'seam.mk').write_text('PORTABLE=1\nC_BUILDDIR=objects\n' + block +
                '\nobjects/platform/content_compat.o:\n\t@mkdir -p $(@D)\n'
                '\t@cp include/platform/content_compat_generated.h $@\n'
                '\nobjects/platform/content_compat.d:\n\t@test -f include/platform/content_compat_generated.h\n')
            subprocess.run(['make', '-f', 'seam.mk', 'objects/platform/content_compat.d'],
                           cwd=root, check=True, capture_output=True)
            command = ['make', '-f', 'seam.mk', 'objects/platform/content_compat.o']
            subprocess.run(command, cwd=root, check=True, capture_output=True)
            first = (root/'objects/platform/content_compat.o').read_bytes()
            self.assertIn(json.loads((root/'world/content_compat.json').read_text())['content_id'].encode(), first)
            (root/'src/mon.h').write_text('catalog 8')
            subprocess.run(command, cwd=root, check=True, capture_output=True)
            second = (root/'objects/platform/content_compat.o').read_bytes()
            self.assertNotEqual(first, second)
            self.assertIn(json.loads((root/'world/content_compat.json').read_text())['content_id'].encode(), second)

    def test_asset_generator_source_changes_identity_but_executables_do_not(self):
        generator = self.generator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'tools/mapjson').mkdir(parents=True)
            (root/'tools/content_compat.py').write_bytes((ROOT/'tools/content_compat.py').read_bytes())
            path = root/'tools/mapjson/mapjson.cpp'
            path.write_text('generator version one')
            first = generator.generate(root)
            path.write_text('generator version two')
            second = generator.generate(root)
            self.assertNotEqual(first, second)
            (root/'tools/mapjson/mapjson').write_bytes(b'platform executable')
            self.assertEqual(second, generator.generate(root))

    def test_real_move_data_mutation_in_private_copy_changes_identity(self):
        generator = self.generator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'src/data').mkdir(parents=True)
            (root/'tools').mkdir()
            (root/'tools/content_compat.py').write_bytes((ROOT/'tools/content_compat.py').read_bytes())
            path = root/'src/data/battle_moves.h'
            original = (ROOT/'src/data/battle_moves.h').read_bytes()
            path.write_bytes(original)
            before = generator.generate(root)
            self.assertIn(b'.power', original)
            path.write_bytes(original.replace(b'.power', b'.changed_power', 1))
            self.assertNotEqual(before, generator.generate(root))
            path.write_bytes(original)
            self.assertEqual(before, generator.generate(root))
            for name in ('build/native.o', 'test/ignored.c', '.git/HEAD',
                         'profiles/private.json', 'world/content_compat.json'):
                target = root/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('excluded')
            self.assertEqual(before, generator.generate(root))

    def test_text_checkout_line_endings_are_neutral_but_binary_bytes_are_exact(self):
        generator = self.generator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'tools').mkdir()
            (root/'tools/content_compat.py').write_bytes((ROOT/'tools/content_compat.py').read_bytes())
            (root/'src').mkdir()
            for extension in ('.c', '.h', '.inc', '.s', '.json', '.txt', '.pal'):
                path = root/('src/example'+extension)
                text = b'JASC-PAL\n0100\n1\n0 0 0\n' if extension == '.pal' else b'semantic source\n'
                path.write_bytes(text)
                before = generator.generate(root)
                path.write_bytes(text.replace(b'\n', b'\r\n'))
                self.assertEqual(before, generator.generate(root), extension)
                path.write_bytes(text+b'changed\n')
                self.assertNotEqual(before, generator.generate(root), extension)
            for extension in ('.png', '.bin', '.pal'):
                path = root/('src/binary'+extension)
                path.write_bytes(b'\x00binary\r\n')
                before = generator.generate(root)
                path.write_bytes(b'\x00binary\n')
                self.assertNotEqual(before, generator.generate(root), extension)

    def test_fingerprint_tracks_sources_not_generated_outputs(self):
        self.assertTrue((ROOT/'tools/content_compat.py').exists(), 'content generator missing')
        generator = self.generator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path, data in [('src/data/moves.h', b'power=40;\n'),
                               ('graphics/mon.png', b'png source'),
                               ('tools/content_compat.py', (ROOT/'tools/content_compat.py').read_bytes())]:
                target = root/path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            first = generator.generate(root)
            self.assertRegex(first, r'^[0-9a-f]{64}$')
            header = root/'include/platform/content_compat_generated.h'
            manifest = root/'world/content_compat.json'
            times = (header.stat().st_mtime_ns, manifest.stat().st_mtime_ns)
            self.assertEqual(generator.generate(root), first)
            self.assertEqual(times, (header.stat().st_mtime_ns, manifest.stat().st_mtime_ns))
            (root/'graphics/mon.4bpp').write_bytes(b'generated gfx')
            for name in ('include/constants/map_groups.h', 'src/data/wild_encounters.h',
                         'data/maps/Town/events.inc', 'data/layouts/layouts_table.inc'):
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('generated by mapjson/jsonproc')
            (root/'src/data/moves.h').write_bytes(b'power=40;\r\n')
            self.assertEqual(generator.generate(root), first)
            (root/'src/data/moves.h').write_bytes(b'power=41;\n')
            second = generator.generate(root)
            self.assertNotEqual(second, first)
            self.assertEqual(json.loads(manifest.read_text())['content_id'], second)
            self.assertIn(second, header.read_text())
            (root/'tools/content_compat.py').write_text('changed algorithm')
            self.assertNotEqual(generator.generate(root), second)


class NativeContentRejectionTest(unittest.TestCase):
    def test_native_content_rejection_survives_disconnect_and_stops_retry(self):
        source = (ROOT/'src/platform/world_bridge.c').read_text()

        def function(signature):
            start = source.index(signature)
            return source[start:source.index('\n}\n', start)+3]

        # Compile the production state, HELLO half of Line, Disconnect, Poll,
        # Init, and telemetry prefix. Engine/rendering and transport are stubs.
        state = source[source.index('#define WB_PEERS'):source.index('static bool8 Identifier')]
        hello = function('static bool8 Line(').split('    if (!strcmp(tokens[0], "BEGIN"))', 1)[0]
        hello += '    (void)i; return FALSE;\n}\n'
        status = function('void WorldBridge_WriteJSON(').split('    for (i = 0; i < WB_REMOTES;', 1)[0]
        status += '    (void)i; (void)count;\n}\n'
        rally = (ROOT/'include/platform/world_rally.h').read_text()
        rally = rally[rally.index('struct WorldRallyMember {'):rally.index('/* Main/game thread')]
        prelude = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <limits.h>
#include <unistd.h>
typedef unsigned char bool8;
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned u32;
#define TRUE 1
#define FALSE 0
#define WORLD_RALLY_ROSTER 4
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define MAP_OFFSET 7
struct ObjectEvent {struct {int x,y;} currentCoords;};
static struct ObjectEvent gObjectEvents[1];
static struct {unsigned objectEventId;} gPlayerAvatar;
static struct {bool8 inBattle;} gMain;
static struct {struct {int mapGroup,mapNum;} location;} *gSaveBlock1Ptr;
static bool8 Overworld(void) {return FALSE;}
static bool8 Ready(void) {return FALSE;}
static void WorldRally_Disconnected(void) {}
static void WorldRally_Init(const char *path) {(void)path;}
#define NativeFile_Open fopen
'''
        transport = r'''
static unsigned connects, receives;
static bool8 SocketOpen(void) {return sWorld.fd >= 0;}
static void Connect(bool8 headless) {(void)headless; connects++;}
static void Receive(bool8 headless) {(void)headless; receives++;}
static bool8 deliver(const char *message) {
    char line[256]; strcpy(line,message);
    bool8 accepted=Line(line);
    if (!accepted) Disconnect();
    return accepted;
}
static void status(char out[2048]) {
    FILE *file=tmpfile(); assert(file);
    WorldBridge_WriteJSON(file,0); rewind(file);
    size_t n=fread(out,1,2047,file); out[n]=0; fclose(file);
}
'''
        main = r'''
int main(void) {
    char out[2048];
    assert(WorldBridge_Init(NULL));
    sWorld.enabled=TRUE; strcpy(sWorld.trainer,"alice");
    sWorld.rallyProbe=sWorld.travelProbe=sWorld.chatProbe=TRUE;
    assert(!deliver("ERROR CONTENT"));
    assert(!sWorld.connected && !SocketOpen());
    status(out);
    assert(strstr(out,"game content differs from host; update game"));
    assert(!sWorld.rallyLegacy && !sWorld.travelLegacy && !sWorld.chatLegacy);
    Disconnect();
    for (unsigned i=0;i<1000;i++) WorldBridge_Poll(FALSE);
    assert(connects==0 && receives==0);
    status(out);
    assert(strstr(out,"game content differs from host; update game"));
    assert(WorldBridge_Init(NULL));
    status(out); assert(!strstr(out,"game content differs"));
    sWorld.enabled=TRUE; strcpy(sWorld.trainer,"alice");
    WorldBridge_Poll(FALSE); assert(connects==1);
    /* Optional-role AUTH fallback order and ordinary WELCOME are unchanged. */
    sWorld.rallyProbe=sWorld.travelProbe=sWorld.chatProbe=TRUE;
    assert(!deliver("ERROR AUTH")); assert(sWorld.rallyLegacy);
    assert(!sWorld.travelLegacy && !sWorld.chatLegacy);
    sWorld.rallyProbe=FALSE; /* Next QueueHello omits the rejected role. */
    sWorld.travelProbe=sWorld.chatProbe=TRUE;
    assert(!deliver("ERROR AUTH")); assert(sWorld.travelLegacy);
    assert(!sWorld.chatLegacy);
    sWorld.chatProbe=TRUE;
    assert(!deliver("ERROR AUTH")); assert(sWorld.chatLegacy);
    assert(!deliver("ERROR AUTH"));
    assert(!deliver("ERROR CONTENT extra"));
    assert(!deliver("ERROR RULES"));
    assert(!deliver("WELCOME 1 bob 7"));
    assert(!deliver("WELCOME 1 alice nope"));
    status(out); assert(!strstr(out,"game content differs"));
    sWorld.rallyProbe=sWorld.travelProbe=sWorld.chatProbe=TRUE;
    assert(deliver("WELCOME 1 alice 7"));
    assert(sWorld.connected && sWorld.live.revision==7);
    assert(sWorld.rallyAvailable && sWorld.travelAvailable && sWorld.chatAvailable);
    Disconnect(); status(out); assert(!strstr(out,"game content differs"));
    puts("native HELLO rejection/status, retry, reset, WELCOME and AUTH passed");
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='native-content-rejection-') as directory:
            path = Path(directory)
            code = (prelude + rally + state + function('static bool8 Identifier(')
                    + function('static bool8 Decimal(') + function('static void Disconnect(')
                    + function('bool8 WorldBridge_Init(') + hello + status + transport
                    + function('void WorldBridge_Poll(') + main)
            (path/'probe.c').write_text(code)
            built = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                                    str(path/'probe.c'), '-o', str(path/'probe')],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(path/'probe')], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stderr.count('game content differs from host; update game'), 1)


class ContentProtocolTest(unittest.TestCase):
    def test_protocol_rejects_different_or_missing_ids_for_every_offer(self):
        from world.link_protocol import LinkProtocol
        positions = {'alice': [1, 4, 5, 5, 4, 7, 1], 'bob': [1, 4, 6, 5, 3, 7, 1]}
        for tags in ({'alice': 'a'*64, 'bob': 'b'*64}, {'alice': 'a'*64},
                     {'bob': 'a'*64}, {'alice': 'A'*64, 'bob': 'A'*64}):
            for request in (b'L OFFER 1 bob', b'L OFFER 2 bob', b'L OFFER 3 bob',
                            b'L OFFER 4 bob', b'T OFFER bob'):
                with self.subTest(tags=tags, request=request):
                    protocol = LinkProtocol(clock=lambda: 0, id_factory=lambda: 123)
                    self.assertEqual(protocol.process('alice', request, positions, content_ids=tags),
                        [('alice', request[:1].decode()+' ERROR INCOMPATIBLE_GAME_CONTENT\n')])
                    self.assertFalse(protocol.reserved(('alice', 'bob')))
                    self.assertEqual(protocol._tags, {})

    def test_protocol_matching_data_allows_all_activity_admissions(self):
        from world.link_protocol import LinkProtocol
        positions = {'alice': [1, 4, 5, 5, 4, 7, 1], 'bob': [1, 4, 6, 5, 3, 7, 1]}
        for tags in ({}, {'alice': 'a'*64, 'bob': 'a'*64}):
            for mode in (1, 2, 3, 4):
                protocol = LinkProtocol(clock=lambda: 0, id_factory=lambda: 123)
                if mode == 4:
                    self.assertEqual(protocol.process('alice', b'T OFFER bob', positions, content_ids=tags),
                                     [('bob', 'T OFFER 123 alice\n')])
                    active = protocol.process('bob', b'T ACCEPT 123', positions, content_ids=tags)
                    self.assertTrue(all('T ACTIVE' in line for _, line in active))
                offered = protocol.process('alice', f'L OFFER {mode} bob'.encode(), positions, content_ids=tags)
                if mode != 4:
                    self.assertIn(('bob', f'L OFFER 123 {mode} alice\n'), offered)
                    admitted = protocol.process('bob', b'L ACCEPT 123', positions, content_ids=tags)
                else:
                    admitted = offered
                self.assertEqual(sum(' ADMIT ' in line for _, line in admitted), 2)

    def test_accept_rechecks_data_before_admit(self):
        from world.link_protocol import LinkProtocol
        positions = {'alice': [1, 4, 5, 5, 4, 7, 1], 'bob': [1, 4, 6, 5, 3, 7, 1]}
        for channel in ('L', 'T'):
            protocol = LinkProtocol(clock=lambda: 0, id_factory=lambda: 123)
            offer = b'L OFFER 3 bob' if channel == 'L' else b'T OFFER bob'
            protocol.process('alice', offer, positions, content_ids={'alice': 'a'*64, 'bob': 'a'*64})
            refused = protocol.process('bob', f'{channel} ACCEPT 123'.encode(), positions,
                                       content_ids={'alice': 'a'*64, 'bob': 'b'*64})
            self.assertIn(('bob', f'{channel} ERROR INCOMPATIBLE_GAME_CONTENT\n'), refused)
            self.assertFalse(any(' ADMIT ' in line or ' COMMIT ' in line or ' ACTIVE ' in line
                                 for _, line in refused))


class ContentAdmissionTest(unittest.TestCase):
    def setUp(self):
        from world.server import WorldServer
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        directory = self.stack.enter_context(tempfile.TemporaryDirectory(prefix='content-'))
        self.server = WorldServer(Path(directory)/'world.sock', Path(directory))
        self.stack.callback(self.server.close)
        self.identities = {n: self.server.create_identity(n) for n in ('alice', 'bob')}

    def connect(self, name, suffix=''):
        sock = self.stack.enter_context(socket.socket(socket.AF_UNIX))
        sock.settimeout(2)
        sock.connect(self.server.socket_path)
        stream = self.stack.enter_context(sock.makefile('rb'))
        sock.sendall(f"HELLO 1 {name} {self.identities[name]['token']}{suffix}\n".encode())
        return sock, stream, stream.readline()

    def test_trainer_named_DATA_is_not_a_suffix(self):
        self.identities['DATA'] = self.server.create_identity('DATA')
        self.server.start()
        _, _, reply = self.connect('DATA', ' SOCIAL')
        self.assertTrue(reply.startswith(b'WELCOME'), reply)

    def test_strict_data_suffix_matching_and_wrong_tags(self):
        from world.client import installed_content_id
        from world.rules import wire
        rules = self.server.set_world_rules(dict(partyEXP=True, reusableTMs=False,
                                                modernSplit=False, megaEvolution=False))
        self.server.start()
        tag = installed_content_id()
        prefix = ' SOCIAL RULES '+wire(rules)
        for suffix in (prefix+' DATA '+('0'*64), prefix+' DATA '+tag.upper(),
                       prefix+' DATA '+tag[:-1], prefix+' DATA '+tag+' DATA '+tag,
                       ' SOCIAL DATA '+tag+' RULES '+wire(rules),
                       prefix+'  DATA '+tag, prefix+' DATA '+tag+' '):
            with self.subTest(suffix=suffix):
                _, _, reply = self.connect('alice', suffix)
                self.assertEqual(reply, b'ERROR CONTENT\n')
                self.assertNotIn('alice', self.server.peers)
        for name in ('alice', 'bob'):
            _, _, reply = self.connect(name, prefix+' DATA '+tag)
            self.assertTrue(reply.startswith(b'WELCOME'), reply)
            self.assertEqual(self.server.peers[name]['content_id'], tag)

    def test_current_python_clients_default_to_installed_data_and_legacy_is_explicit(self):
        from world.client import WorldClient, IntentClient, installed_content_id
        rules = self.server.set_world_rules(dict(partyEXP=True, reusableTMs=False,
                                                modernSplit=False, megaEvolution=False))
        self.server.start()
        with self.assertRaisesRegex(ValueError, 'CONTENT'):
            WorldClient(self.server.socket_path, 'alice', self.identities['alice']['token'],
                        rules=rules, content_id=None)
        with WorldClient(self.server.socket_path, 'alice', self.identities['alice']['token'], rules=rules):
            self.assertEqual(self.server.peers['alice']['content_id'], installed_content_id())
        with IntentClient(self.server.socket_path, 'bob', self.identities['bob']['token']) as control:
            self.assertTrue(control._request({'command': 'world_rules'})['ok'])
            self.assertNotIn('bob', self.server.peers)

    def ready_pair(self, tags):
        from world.client import WorldClient
        clients = []
        for name, tag, x, facing in zip(('alice', 'bob'), tags, (5, 6), (4, 3)):
            client = self.stack.enter_context(WorldClient(self.server.socket_path, name,
                self.identities[name]['token'], social=True, content_id=tag,
                rules=self.server.world_rules if self.server.world_rules['mask'] else None))
            client.send_state(1, 1, 4, x, 5, facing, 7, 1, 'a'*16, 'b'*16)
            clients.append(client)
        while clients[0].snapshot()['peers'].get('bob', {}).get('ready') != 1:
            pass
        return clients

    def test_vanilla_mixed_data_refuses_before_any_party_or_admit(self):
        from world.client import installed_content_id
        self.server.start()
        self.ready_pair((installed_content_id(), None))
        la, lar, _ = self.connect('alice', ' LINK')
        lb, lbr, _ = self.connect('bob', ' LINK')
        for request, channel in ((b'L OFFER 1 bob', b'L'), (b'L OFFER 2 bob', b'L'),
                                 (b'L OFFER 3 bob', b'L'), (b'T OFFER bob', b'T')):
            la.sendall(request+b'\n')
            self.assertEqual(lar.readline(), channel+b' ERROR INCOMPATIBLE_GAME_CONTENT\n')
            self.assertFalse(self.server.link_protocol.reserved(('alice', 'bob')))
        # No invitation/admission/party exchange was ever queued to the target.
        lb.settimeout(.1)
        with self.assertRaises(TimeoutError):
            lbr.readline()

    def test_link_cannot_upgrade_legacy_presence_using_a_control_or_link_claim(self):
        from world.client import installed_content_id
        self.server.start()
        self.ready_pair((None, None))
        _, _, reply = self.connect('alice', ' CONTROL DATA '+installed_content_id())
        self.assertTrue(reply.startswith(b'WELCOME'))
        self.assertIsNone(self.server.peers['alice']['content_id'])
        _, _, reply = self.connect('alice', ' LINK DATA '+installed_content_id())
        self.assertEqual(reply, b'ERROR CONTENT\n')
        _, _, reply = self.connect('alice', ' LINK')
        self.assertTrue(reply.startswith(b'WELCOME'))
        self.assertIsNone(self.server.link_channels['alice']['content_id'])

    def test_matching_new_or_both_absent_legacy_can_admit(self):
        from world.client import installed_content_id
        # Each variant gets its own disposable authority, never an invented ID.
        for tags in ((installed_content_id(), installed_content_id()), (None, None)):
            with self.subTest(tags=tags):
                fixture = ContentAdmissionTest()
                fixture.setUp()
                try:
                    if tags[0] is not None:
                        fixture.server.set_world_rules(dict(partyEXP=True, reusableTMs=False,
                                                           modernSplit=False, megaEvolution=False))
                    fixture.server.start()
                    fixture.ready_pair(tags)
                    la, lar, reply = fixture.connect('alice', ' LINK')
                    self.assertTrue(reply.startswith(b'WELCOME'))
                    lb, lbr, reply = fixture.connect('bob', ' LINK')
                    self.assertTrue(reply.startswith(b'WELCOME'))
                    la.sendall(b'L OFFER 3 bob\n')
                    offer = lbr.readline().split()
                    self.assertEqual(offer[:2], [b'L', b'OFFER'])
                    lb.sendall(b'L ACCEPT '+offer[2]+b'\n')
                    self.assertIn(b'ADMIT', lar.readline())
                    self.assertIn(b'ADMIT', lbr.readline())
                finally:
                    fixture.doCleanups()

    def test_matching_content_does_not_bypass_world_battle_policy(self):
        from world.client import installed_content_id
        self.server.set_world_rules(dict(partyEXP=False, reusableTMs=False,
                                        modernSplit=True, megaEvolution=False))
        self.server.start()
        self.ready_pair((installed_content_id(), installed_content_id()))
        la, lar, _ = self.connect('alice', ' LINK')
        lb, lbr, _ = self.connect('bob', ' LINK')
        la.sendall(b'L OFFER 1 bob\n')
        sid = lbr.readline().split()[2]
        lb.sendall(b'L ACCEPT '+sid+b'\n')
        self.assertIn(b'ADMIT', lar.readline())
        self.assertIn(b'ADMIT', lbr.readline())
        la.sendall(b'L EVENT 1 '+sid+b' 1 0 1 0 8755 '+b'0'*32+b'\n')
        self.assertEqual(lar.readline(), b'L ERROR WORLD_RULES_MISMATCH\n')
        self.assertIn(b'ABORT', lbr.readline())

    def test_nonzero_world_rejects_missing_native_data_before_presence(self):
        from world.rules import wire
        rules = self.server.set_world_rules(dict(partyEXP=True, reusableTMs=False,
                                                modernSplit=False, megaEvolution=False))
        self.server.start()
        _, _, reply = self.connect('alice', ' SOCIAL RULES '+wire(rules))
        self.assertEqual(reply, b'ERROR CONTENT\n')
        self.assertNotIn('alice', self.server.peers)


if __name__ == '__main__':
    unittest.main()
