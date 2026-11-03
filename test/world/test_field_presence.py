"""Presence is not permission to interact. Exercise the real socket authority."""
from contextlib import ExitStack
from pathlib import Path
import socket
import tempfile
import unittest

from world.server import WorldServer
from world.client import WorldClient


class FieldPresence(unittest.TestCase):
    def test_busy_field_cannot_offer_or_accept_native_link(self):
        with tempfile.TemporaryDirectory(prefix='ewp-') as root, ExitStack() as stack:
            server = WorldServer(Path(root)/'sock', Path(root)/'state').start()
            stack.callback(server.close)
            clients, links = [], []
            for name in ('alice', 'bob'):
                identity = server.create_identity(name)
                clients.append(stack.enter_context(WorldClient(server.socket_path, name, identity['token'], social=True)))
                sock = stack.enter_context(socket.socket(socket.AF_UNIX))
                sock.settimeout(3)
                sock.connect(server.socket_path)
                stream = stack.enter_context(sock.makefile('rb'))
                sock.sendall(f'HELLO 1 {name} {identity["token"]} LINK\n'.encode())
                self.assertTrue(stream.readline().endswith(b' LINK\n'))
                links.append((sock, stream))

            def publish(index, seq, ready):
                clients[index].sock.sendall(f'FIELD {seq} 0 1 {10+index} 12 {4 if index == 0 else 3} 7 {ready} {"a"*16} {"b"*16}\n'.encode())
                other = clients[1-index]
                for _ in range(20):
                    peer = other.snapshot()['peers'].get(clients[index].trainer_id)
                    if peer and peer['ready'] == ready:
                        return
                self.fail('presence update was not observed')

            publish(0, 1, 1)
            publish(1, 1, 0)
            for index, target in ((0, 'bob'), (1, 'alice')):
                links[index][0].sendall(f'L OFFER 1 {target}\n'.encode())
                self.assertEqual(links[index][1].readline(), b'L ERROR NOT_READY\n')
            publish(1, 2, 1)
            links[0][0].sendall(b'L OFFER 1 bob\n')
            offer = links[1][1].readline().split()
            self.assertEqual(offer[:2], [b'L', b'OFFER'])
            publish(1, 3, 0)
            links[1][0].sendall(b'L ACCEPT ' + offer[2] + b'\n')
            self.assertEqual(links[1][1].readline(), b'L ERROR NOT_READY\n')

    def test_field_keeps_legacy_snapshots_ready_only_and_validates_every_field(self):
        with tempfile.TemporaryDirectory(prefix='ewp-') as root, ExitStack() as stack:
            server = WorldServer(Path(root)/'sock', Path(root)/'state').start()
            stack.callback(server.close)
            a = server.create_identity('alice')
            b = server.create_identity('bob')
            actor = stack.enter_context(WorldClient(server.socket_path, 'alice', a['token'], social=True))
            legacy = stack.enter_context(WorldClient(server.socket_path, 'bob', b['token']))
            actor.sock.sendall(f'FIELD 1 0 1 10 12 2 7 0 {"a"*16} {"b"*16}\n'.encode())
            # Sequence a ready update behind the busy update. Seeing the ready
            # one proves we consumed the prior snapshot rather than racing it.
            actor.send_state(2, 0, 1, 11, 12, 2, 7, 1, 'a'*16, 'b'*16)
            seen = []
            for _ in range(10):
                peers = legacy.snapshot()['peers']
                if peers:
                    seen.append(peers['alice'])
                    break
            self.assertEqual([p['ready'] for p in seen], [1])
            for index, (social, state) in enumerate(((False, '0 1 10 12 2 7 0'),
                                  (True, '255 255 0 0 1 7 0'),
                                  (True, '0 1 32767 12 2 7 0'),
                                  (True, '0 1 10 12 0 7 0'),
                                  (True, '0 1 10 12 2 256 0'),
                                  (True, '0 1 10 12 2 7 2'))):
                with self.subTest(social=social, state=state):
                    name = f'invalid{index}'
                    identity = server.create_identity(name)
                    client = WorldClient(server.socket_path, name, identity['token'], social=social)
                    try:
                        # Drain the initial snapshot, then malformed input must
                        # disconnect without replacing any valid state.
                        client.snapshot()
                        client.sock.sendall(f'FIELD 1 {state} {"a"*16} {"b"*16}\n'.encode())
                        with self.assertRaisesRegex(ValueError, 'ERROR MALFORMED'):
                            while True:
                                client.snapshot()
                    finally:
                        client.close()

    def test_four_trainers_keep_busy_field_positions_without_becoming_ready(self):
        with tempfile.TemporaryDirectory(prefix='ewp-') as root, ExitStack() as stack:
            server = WorldServer(Path(root)/'sock', Path(root)/'state').start()
            stack.callback(server.close)
            clients = []
            for name in ('alice', 'bob', 'carol', 'dave'):
                identity = server.create_identity(name)
                clients.append(stack.enter_context(WorldClient(server.socket_path, name, identity['token'], social=True)))
            for index, client in enumerate(clients):
                client.sock.sendall(f'FIELD 1 0 1 {10+index} 12 2 7 0 {"a"*16} {"b"*16}\n'.encode())
            for index, client in enumerate(clients):
                for _ in range(12):
                    view = client.snapshot()['peers']
                    if len(view) == 3:
                        break
                self.assertEqual(set(view), {c.trainer_id for c in clients if c is not client})
                self.assertTrue(all(p['ready'] == 0 for p in view.values()))
                self.assertEqual(view[clients[(index+1)%4].trainer_id]['x'], 10+(index+1)%4)
            # A busy field trainer cannot consent to a meeting or native link.
            clients[0].meet(2, 'bob')
            for _ in range(12):
                snapshot = clients[0].snapshot()
                self.assertIsNone(snapshot['meeting'])
                if len(snapshot['peers']) == 3:
                    break
            clients[1].send_state(2, 0, 0, 0, 0, 1, 7, 0, 'a'*16, 'b'*16)
            for _ in range(12):
                view = clients[0].snapshot()['peers']
                if 'bob' not in view:
                    break
            self.assertEqual(set(view), {'carol', 'dave'})


if __name__ == '__main__':
    unittest.main()
