"""Real server/socket tests for the native link channel's authority boundary."""
import socket
import tempfile
import unittest
from contextlib import ExitStack
from world.server import WorldServer


class LinkRoleTests(unittest.TestCase):
    def test_two_native_roles_relay_consented_rounds_on_real_sockets(self):
        with tempfile.TemporaryDirectory(prefix='link-wire-') as root, ExitStack() as stack:
            server = WorldServer(root + '/world.sock', root + '/state')
            identities = {name: server.create_identity(name) for name in ('alice', 'bob')}
            server.start()
            stack.callback(server.close)

            def connect(name, role):
                conn = stack.enter_context(socket.socket(socket.AF_UNIX))
                conn.settimeout(2)
                conn.connect(root + '/world.sock')
                stream = stack.enter_context(conn.makefile('rb'))
                conn.sendall(('HELLO 1 {id} {token} '.format(**identities[name]) + role + '\n').encode())
                self.assertTrue(stream.readline().startswith(b'WELCOME'))
                return conn, stream

            native_a, native_a_read = connect('alice', 'SOCIAL')
            native_b, _ = connect('bob', 'SOCIAL')
            native_a.sendall(b'STATE 1 1 4 5 5 4 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb\n')
            native_b.sendall(b'STATE 1 1 4 6 5 3 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb\n')
            while not native_a_read.readline().startswith(b'PEER bob '):
                pass
            link_a, read_a = connect('alice', 'LINK')
            link_b, read_b = connect('bob', 'LINK')
            link_a.sendall(b'L OFFER 1 bob\n')
            try:
                offered = read_b.readline().decode().split()
            except TimeoutError:
                self.fail('link offer did not arrive; states=' + repr({name: p['state'] for name,p in server.peers.items()})
                          + '; sender=' + repr(read_a.readline()))
            self.assertEqual(offered[:2], ['L','OFFER'])
            sid = offered[2]
            link_b.sendall(f'L ACCEPT {sid}\n'.encode())
            self.assertEqual(read_a.readline().decode(), f'L ADMIT {sid} 1 0\n')
            self.assertEqual(read_b.readline().decode(), f'L ADMIT {sid} 1 1\n')
            zero = '0'*32
            for conn, slot in ((link_a,0),(link_b,1)):
                conn.sendall(f'L EVENT 1 {sid} 1 {slot} 1 0 8755 {zero}\n'.encode())
            for stream in (read_a,read_b):
                self.assertEqual(stream.readline().decode(), f'L COMMIT 1 {sid} 1 0 {zero} {zero}\n')
            for conn, slot in ((link_a,0),(link_b,1)):
                conn.sendall(f'L EVENT 4 {sid} 1 {slot} 1 0 0 {zero}\n'.encode())
            for stream in (read_a,read_b):
                self.assertEqual(stream.readline().decode(), f'L COMMIT 3 {sid} 1 0 {zero} {zero}\n')
            self.assertEqual(set(server.peers), {'alice','bob'})
            self.assertEqual(set(server.link_channels), {'alice','bob'})

    def test_link_requires_live_presence_and_cannot_replace_it(self):
        with tempfile.TemporaryDirectory(prefix='link-role-') as root, ExitStack() as stack:
            server = WorldServer(root + '/world.sock', root + '/state')
            identity = server.create_identity('alice')
            server.start()
            stack.callback(server.close)

            def connection(role=''):
                conn = stack.enter_context(socket.socket(socket.AF_UNIX))
                conn.settimeout(2)
                conn.connect(root + '/world.sock')
                stream = stack.enter_context(conn.makefile('rb'))
                conn.sendall(('HELLO 1 {id} {token}'.format(**identity) + role + '\n').encode())
                return conn, stream

            _, absent = connection(' LINK')
            self.assertEqual(absent.readline(), b'ERROR PRESENCE\n')
            _, presence = connection(' SOCIAL')
            self.assertTrue(presence.readline().startswith(b'WELCOME 1 alice '))
            _, link = connection(' LINK')
            welcome = link.readline()
            self.assertTrue(welcome.startswith(b'WELCOME 1 alice '), welcome)
            self.assertTrue(welcome.endswith(b' LINK\n'), welcome)
            self.assertEqual(list(server.peers), ['alice'])
            _, duplicate = connection(' LINK')
            self.assertEqual(duplicate.readline(), b'ERROR DUPLICATE\n')

    def test_legacy_clients_cannot_send_link_commands(self):
        with tempfile.TemporaryDirectory(prefix='link-role-') as root:
            server = WorldServer(root + '/world.sock', root + '/state')
            identity = server.create_identity('alice')
            try:
                server.start()
                with socket.socket(socket.AF_UNIX) as conn:
                    conn.settimeout(2)
                    conn.connect(root + '/world.sock')
                    with conn.makefile('rb') as stream:
                        conn.sendall(('HELLO 1 {id} {token}\n'.format(**identity)).encode())
                        self.assertTrue(stream.readline().startswith(b'WELCOME'))
                        conn.sendall(b'L OFFER 1 bob\n')
                        line = b''
                        for _ in range(16):
                            line = stream.readline()
                            if line.startswith(b'ERROR'):
                                break
                        self.assertEqual(line, b'ERROR MALFORMED\n')
            finally:
                server.close()
