"""World-owned rule contracts through the real authority and desktop session."""
import json
from pathlib import Path
import socket
import tempfile
import unittest
from world.server import WorldServer
from world.client import WorldClient, IntentClient, admin_request
from world.session import DesktopSession


class WorldRulesTest(unittest.TestCase):
    def test_legacy_world_persists_vanilla_identity(self):
        with tempfile.TemporaryDirectory(prefix='wr-') as directory:
            root = Path(directory)
            server = WorldServer(root/'transport/world.sock', root)
            try:
                rules = server.inspect()['world_rules']
                self.assertEqual(rules['mask'], 0)
                self.assertEqual(rules['version'], 1)
            finally:
                server.close()
            server = WorldServer(root/'transport/world.sock', root)
            try:
                self.assertEqual(server.inspect()['world_rules'], rules)
            finally:
                server.close()

    def test_expanded_roster_is_separate_world_opt_in(self):
        from world.rules import make
        with tempfile.TemporaryDirectory(prefix='wr-') as directory:
            root=Path(directory)
            server=WorldServer(root/'world.sock',root)
            try:
                self.assertFalse(server.world_rules['rules']['expandedRoster'])
                value=server.set_world_rules(dict(partyEXP=False,reusableTMs=False,modernSplit=False,
                                                 megaEvolution=False,expandedRoster=True))
                self.assertEqual(value['mask'],16)
                self.assertFalse(value['rules']['modernSplit'])
                identity=server.create_identity('alice')
                server.start()
                with self.assertRaisesRegex(ValueError,'RULES'):
                    WorldClient(server.socket_path,'alice',identity['token'])
                with WorldClient(server.socket_path,'alice',identity['token'],rules=value):
                    self.assertEqual(server.world_rules['mask'],16)
            finally:
                server.close()

    def test_nonvanilla_version_identity_and_digest_survive_restart(self):
        from world.rules import read
        with tempfile.TemporaryDirectory(prefix='wr-') as directory:
            root=Path(directory)
            server=WorldServer(root/'world.sock',root)
            before=server.world_rules
            value=server.set_world_rules(dict(partyEXP=True,reusableTMs=False,modernSplit=True,megaEvolution=False))
            self.assertEqual(value['version'],before['version']+1)
            self.assertEqual(value['world_id'],before['world_id'])
            self.assertNotEqual(value['digest'],before['digest'])
            server.close()
            server=WorldServer(root/'world.sock',root)
            try:
                self.assertEqual(server.inspect()['world_rules'],value)
                self.assertEqual(read(root),value)
            finally:
                server.close()

    def test_concurrent_legacy_initialization_publishes_one_world_identity(self):
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
        from unittest.mock import patch
        import os
        import threading
        from world.rules import read
        with tempfile.TemporaryDirectory(prefix='wr-') as directory:
            root=Path(directory)
            entered,release=threading.Event(),threading.Event()
            replace=os.replace
            def delayed(source,target):
                if not entered.is_set():
                    entered.set()
                    self.assertTrue(release.wait(3))
                return replace(source,target)
            with patch('world.rules.os.replace',side_effect=delayed), ThreadPoolExecutor(2) as pool:
                first=pool.submit(read,root,create=True)
                self.assertTrue(entered.wait(2))
                second=pool.submit(read,root,create=True)
                try:
                    with self.assertRaises(FutureTimeout):
                        second.result(timeout=.1)
                finally:
                    release.set()
                self.assertEqual(first.result(),second.result())
                self.assertEqual(read(root),first.result())

    def test_invalid_schema_and_atomic_publication_preserve_last_policy(self):
        from unittest.mock import patch
        from world.rules import read, make, publish, MANIFEST
        with tempfile.TemporaryDirectory(prefix='wr-') as directory:
            root=Path(directory)
            original=publish(root,make())
            for invalid in [dict(original,mask=True),dict(original,schema=2),dict(original,digest='0'*64),
                            dict(original,version=0),dict(original,unknown=1)]:
                with self.assertRaises(ValueError):
                    publish(root,invalid)
                self.assertEqual(read(root),original)
            next_policy=make(original['world_id'],2,dict(partyEXP=True,reusableTMs=False,modernSplit=False,megaEvolution=False))
            with patch('world.rules.os.replace',side_effect=OSError('publication failed')):
                with self.assertRaises(OSError):
                    publish(root,next_policy)
            self.assertEqual(read(root),original)
            self.assertEqual(list(root.glob('.rules-*')),[])
            (root/MANIFEST).unlink()
            (root/MANIFEST).symlink_to(root/'outside')
            with self.assertRaises((OSError,ValueError)):
                read(root,create=True)
            self.assertFalse((root/'outside').exists())

    def test_owner_cannot_change_rules_while_disconnected_profile_is_running(self):
        from world.launcher import ProfileLock
        with tempfile.TemporaryDirectory(prefix='wr-') as directory:
            root=Path(directory)
            server=WorldServer(root/'world.sock',root)
            try:
                server.create_identity('alice')
                with ProfileLock(root,'alice'):
                    with self.assertRaises(ValueError):
                        server.set_world_rules(dict(partyEXP=True,reusableTMs=False,modernSplit=False,megaEvolution=False))
                self.assertEqual(server.world_rules['mask'],0)
            finally:
                server.close()

    def test_host_authority_and_two_client_admission(self):
        with tempfile.TemporaryDirectory(prefix='wr-') as directory:
            session = DesktopSession(Path(directory))
            session.create_world('shared')
            session.host('shared')
            server = session.server
            try:
                rules = session.set_world_rules(dict(partyEXP=True, reusableTMs=True,
                    modernSplit=True, megaEvolution=False))
                self.assertEqual(rules['mask'], 7)
                a, b = server.create_identity('alice'), server.create_identity('bob')
                with IntentClient(server.socket_path, 'alice', a['token']) as control:
                    self.assertEqual(control._request({'command':'world_rules'})['world_rules'], rules)
                    self.assertFalse(control._request({'command':'set_world_rules','rules':{}})['ok'])
                with self.assertRaisesRegex(ValueError, 'RULES'):
                    WorldClient(server.socket_path, 'alice', a['token'])
                from world.rules import make
                wrong = make(rules['world_id'], rules['version'] + 1, rules['rules'])
                with self.assertRaisesRegex(ValueError, 'RULES'):
                    WorldClient(server.socket_path, 'alice', a['token'], rules=wrong)
                # Trainer save flags are deliberately not part of admission or state.
                with WorldClient(server.socket_path, 'alice', a['token'], rules=rules) as one:
                    with WorldClient(server.socket_path, 'bob', b['token'], rules=rules) as two:
                        self.assertEqual(one.rules, two.rules)
                        result = admin_request(server.socket_path, {'command':'set_world_rules',
                            'rules':dict(partyEXP=False, reusableTMs=False, modernSplit=False, megaEvolution=False)})
                        self.assertFalse(result['ok'])
                        self.assertEqual(server.inspect()['world_rules'], rules)
            finally:
                session.close()

    def test_agreeing_clients_cannot_override_world_battle_rules(self):
        from contextlib import ExitStack
        from world.rules import wire
        with tempfile.TemporaryDirectory(prefix='wr-') as directory, ExitStack() as stack:
            root = Path(directory)
            server = WorldServer(root/'world.sock',root)
            stack.callback(server.close)
            rules = server.set_world_rules(dict(partyEXP=False,reusableTMs=False,modernSplit=True,megaEvolution=False))
            identities = {n:server.create_identity(n) for n in ('alice','bob')}
            server.start()
            def connect(name,role,claim=True):
                sock=stack.enter_context(socket.socket(socket.AF_UNIX))
                sock.settimeout(2)
                sock.connect(server.socket_path)
                stream=stack.enter_context(sock.makefile('rb'))
                from world.client import installed_content_id
                suffix = ' RULES '+wire(rules)+' DATA '+installed_content_id() if claim else ''
                sock.sendall(f"HELLO 1 {name} {identities[name]['token']} {role}{suffix}\n".encode())
                self.assertTrue(stream.readline().startswith(b'WELCOME'))
                return sock,stream
            a,ar=connect('alice','SOCIAL')
            b,br=connect('bob','SOCIAL')
            a.sendall(b'STATE 1 1 4 5 5 4 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb\n')
            b.sendall(b'STATE 1 1 4 6 5 3 7 1 cccccccccccccccc dddddddddddddddd\n')
            while not ar.readline().startswith(b'PEER bob '):
                pass
            la,lar=connect('alice','LINK',False)
            lb,lbr=connect('bob','LINK',False)
            la.sendall(b'L OFFER 1 bob\n')
            sid=lbr.readline().decode().split()[2]
            lb.sendall(f'L ACCEPT {sid}\n'.encode())
            self.assertIn(b'ADMIT',lar.readline())
            self.assertIn(b'ADMIT',lbr.readline())
            la.sendall(f"L EVENT 1 {sid} 1 0 1 0 8755 {'0'*32}\n".encode())
            self.assertEqual(lar.readline(),b'L ERROR WORLD_RULES_MISMATCH\n')
            self.assertIn(b'ABORT',lbr.readline())

class HostedRulesTest(unittest.TestCase):
    def test_owner_only_https_rules_and_remote_session_propagation(self):
        from test.world.test_hosting import HostingTests
        from world.hosting import HostingService, HostingError
        from world.hosting_client import HostingClient, write_private
        from world.rules import read
        fixture = HostingTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        manager = fixture.manager()
        self.addCleanup(manager.close)
        service = HostingService(manager, ('127.0.0.1',0)).start()
        self.addCleanup(service.close)
        endpoint = dict(host='localhost',port=service.address[1])
        access = dict(manager.create_account(),endpoint=endpoint,pin=fixture.pin)
        write_private(fixture.root/'access.json',access)
        owner = HostingClient.enroll(fixture.root/'access.json',fixture.root/'owner.json')
        created=owner.create('Rules','Owner',request_id='rules')
        world=created['world']['id']
        rules=owner.set_world_rules(world,dict(partyEXP=True,reusableTMs=True,modernSplit=True,megaEvolution=True))
        self.assertEqual(owner.world_rules(world),rules)
        access2=dict(manager.create_account(),endpoint=endpoint,pin=fixture.pin)
        write_private(fixture.root/'other-access.json',access2)
        outsider=HostingClient.enroll(fixture.root/'other-access.json',fixture.root/'other.json')
        with self.assertRaises(HostingError):
            outsider.set_world_rules(world,dict.fromkeys(rules['rules'],False))
        owner.save_invitation(created,fixture.root/'native.json')
        client_root=fixture.root/'client'
        client_root.mkdir()
        session=DesktopSession(client_root)
        self.addCleanup(session.close)
        session.connect_remote('remote',fixture.root/'native.json',('localhost',fixture.port),fixture.pin)
        self.assertEqual(read(client_root/'remote'),rules)
        self.assertEqual(read(client_root/'remote')['mask'],15)
        newer=owner.set_world_rules(world,dict(partyEXP=False,reusableTMs=True,modernSplit=True,megaEvolution=False,expandedRoster=True))
        self.assertEqual(session.refresh_world_rules('Owner'),newer)
        self.assertEqual(read(client_root/'remote'),newer)
        rules=newer
        from world.windows_client import WindowsGuestSession
        from world.rules import wire
        windows = WindowsGuestSession('localhost',fixture.port,fixture.pin,fixture.root/'native.json',
                                      data_root=fixture.root/'windows',binary='/bin/true')
        self.addCleanup(windows.close)
        windows.prepare()
        command=windows.game_args()
        self.assertEqual(command[command.index('--world-rules')+1],wire(rules))

class NativeRulesTest(unittest.TestCase):
    def test_immutable_native_rules_and_gameplay_getters(self):
        import subprocess
        root = Path(__file__).resolve().parents[2]
        directory = tempfile.TemporaryDirectory(prefix='rc4-world-rules-')
        self.addCleanup(directory.cleanup)
        artifact = Path(directory.name)
        artifact.mkdir(parents=True, exist_ok=True)
        source = artifact / 'rules_fixture.c'
        source.write_text(r'''#include <assert.h>
#include "gba/types.h"
#include "platform/world_rules.h"
int main(void) {
    assert(WorldRules_Mask() == 0);
    assert(!WorldRules_Init("0:7:bad"));
    assert(WorldRules_Init("2:7:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"));
    assert(WorldRules_Enabled(WORLD_RULE_PARTY_EXP));
    assert(WorldRules_Enabled(WORLD_RULE_REUSABLE_TMS));
    assert(WorldRules_Enabled(WORLD_RULE_MODERN_SPLIT));
    assert(!WorldRules_Enabled(WORLD_RULE_MEGA_EVOLUTION));
    assert(!WorldRules_Init("3:0:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"));
    assert(WorldRules_Mask() == 7);
    return 0;
}
''')
        subprocess.run(['gcc','-std=gnu99','-DPORTABLE','-DMODERN=1','-DNONMATCHING',
            '-DUBFIX','-DVER_64BIT','-Werror','-iquote','include',str(source),
            'src/platform/world_rules.c','-o',str(artifact/'rules_fixture')],cwd=root,check=True)
        subprocess.run([str(artifact/'rules_fixture')],check=True)
        for name, rule in [('src/battle_script_commands.c','PARTY_EXP'),
                           ('src/party_menu.c','REUSABLE_TMS'),
                           ('include/battle_move_split.h','MODERN_SPLIT')]:
            self.assertIn('WorldRules_Enabled(WORLD_RULE_'+rule+')', (root/name).read_text())
        menu = (root/'src/platform/world_menu.c').read_text()
        self.assertNotIn('FlagSet(FLAG_PARTY_EXP_SHARE)', menu)
        self.assertNotIn('FlagSet(FLAG_REUSABLE_TMS)', menu)
        self.assertNotIn('FlagSet(FLAG_MODERN_MOVE_SPLIT)', menu)

    def test_actual_native_hello_is_admitted_by_world_authority(self):
        import subprocess
        from contextlib import ExitStack
        from world.rules import wire
        root=Path(__file__).resolve().parents[2]
        generated=root/'include'
        if not (generated/'constants/map_groups.h').exists():
            generated=root.parent/'rc3/include'
        if not (generated/'constants/map_groups.h').exists():
            self.skipTest('Generate native engine headers before bridge fixture compilation.')
        directory = tempfile.TemporaryDirectory(prefix='rc4-world-rules-hello-')
        self.addCleanup(directory.cleanup)
        artifact=Path(directory.name)
        artifact.mkdir(parents=True,exist_ok=True)
        source=artifact/'hello_fixture.c'
        source.write_text(r'''#include "src/platform/world_bridge.c"
int main(int argc, char **argv) {
    if (argc != 4 || !WorldRules_Init(argv[1])) return 2;
    strcpy(sWorld.trainer,argv[2]);
    strcpy(sWorld.token,argv[3]);
    QueueHello(TRUE);
    return fwrite(sWorld.output,1,sWorld.outputSize,stdout) != sWorld.outputSize;
}
''')
        binary=artifact/'hello_fixture'
        result=subprocess.run(['gcc','-std=gnu99','-DPORTABLE','-DMODERN=1','-DNONMATCHING',
            '-DUBFIX','-DVER_64BIT','-Werror','-ffunction-sections','-fdata-sections',
            '-iquote',str(root),'-iquote',str(root/'include'),'-iquote',str(generated),
            '-iquote',str(generated/'constants'),str(source),str(root/'src/platform/world_rules.c'),
            str(root/'src/platform/content_compat.c'),
            '-Wl,--gc-sections','-o',str(binary)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with tempfile.TemporaryDirectory(prefix='wr-') as directory, ExitStack() as stack:
            state=Path(directory)
            server=WorldServer(state/'world.sock',state)
            stack.callback(server.close)
            value=server.set_world_rules(dict(partyEXP=True,reusableTMs=True,modernSplit=True,megaEvolution=True))
            identities=[server.create_identity(name) for name in ('alice','bob')]
            server.start()
            for identity in identities:
                hello=subprocess.check_output([str(binary),wire(value),identity['id'],identity['token']])
                sock=stack.enter_context(socket.socket(socket.AF_UNIX))
                sock.settimeout(2)
                sock.connect(server.socket_path)
                stream=stack.enter_context(sock.makefile('rb'))
                sock.sendall(hello)
                self.assertTrue(stream.readline().startswith(b'WELCOME'))
            with server.lock:
                self.assertEqual(set(server.peers),{'alice','bob'})
                self.assertTrue(all(peer['rules_validated'] for peer in server.peers.values()))
                self.assertEqual(server.world_rules,value)

    def test_new_offline_world_persists_vanilla_policy(self):
        from world.rules import read
        from world.offline import offline_profile
        with tempfile.TemporaryDirectory(prefix='wr-') as directory:
            state=Path(directory)
            with offline_profile(state,'alice'):
                value=read(state)
                self.assertIsNotNone(value)
                self.assertEqual(value['mask'],0)
            with offline_profile(state,'alice'):
                self.assertEqual(read(state),value)

    def test_launcher_passes_world_policy_outside_private_save(self):
        from world.rules import make, publish, wire
        from world.launcher import game_command, profile_paths
        from world.offline import offline_profile
        with tempfile.TemporaryDirectory(prefix='wr-') as directory:
            state = Path(directory)
            value = make(rules=dict(partyEXP=True,reusableTMs=True,modernSplit=False,megaEvolution=False))
            publish(state,value)
            paths = profile_paths(state,'alice')
            command = game_command('/bin/true',state,paths)
            self.assertEqual(command[command.index('--world-rules')+1],wire(value))
            with offline_profile(state,'alice') as paths:
                command = game_command('/bin/true',state/'.offline',paths,online=False)
                self.assertEqual(command[command.index('--world-rules')+1],wire(value))

if __name__ == '__main__':
    unittest.main()
