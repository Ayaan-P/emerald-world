"""Two authenticated disposable clients exercise shared cave authority over Unix sockets.

This is a protocol test, not native graphical or WAN acceptance.
"""
from pathlib import Path
import socket, tempfile, unittest
from world.server import WorldServer

ROWS=['#'*31]+['#'+'.'*29+'#']*29+['#'*31]
BLOB=b'EWGMAP01'+''.join(ROWS).encode('ascii')

class SharedCaveSocket(unittest.TestCase):
 def test_two_clients_fetch_ack_and_see_each_other(self):
  with tempfile.TemporaryDirectory(prefix='ew-cave-') as d:
   root=Path(d);server=WorldServer(root/'s',root/'world',cave_template=BLOB)
   clients=[]
   try:
    a=server.create_identity('Alice');b=server.create_identity('Bob');server.start()
    def connect(identity):
     sock=socket.socket(socket.AF_UNIX);sock.settimeout(5);sock.connect(server.socket_path)
     stream=sock.makefile('rwb',buffering=0);clients.append((sock,stream))
     stream.write(('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE\n' % (identity['id'],identity['token'])).encode())
     self.assertTrue(stream.readline().startswith(b'WELCOME 1 '));return stream
    def until(stream,prefix):
     for _ in range(256):
      line=stream.readline()
      if not line: self.fail('authority closed the stream')
      if line.startswith(b'ERROR '): self.fail(line.decode().strip())
      if line.startswith(prefix): return line.decode().strip()
     self.fail('expected line not received')
    def fetch(stream):
     stream.write(b'CAVE GET\n');begin=until(stream,b'CAVE BEGIN ');identity=begin.split()[-1]
     for i in range(31):
      line=until(stream,b'CAVE ROW ');parts=line.split(' ')
      self.assertEqual(parts[:4],['CAVE','ROW',identity,str(i)]);self.assertEqual(parts[4],ROWS[i])
     self.assertEqual(until(stream,b'CAVE END '),'CAVE END '+identity)
     stream.write(('CAVE ACK '+identity+'\n').encode());self.assertEqual(until(stream,b'CAVE OK '),'CAVE OK '+identity)
     return identity
    alice,bob=connect(a),connect(b);self.assertEqual(fetch(alice),fetch(bob))
    group,num=server.cave_map;hashes='a'*16+' '+'b'*16
    alice.write(f'STATE 1 {group} {num} 1 1 1 7 1 {hashes}\n'.encode())
    bob.write(f'STATE 1 {group} {num} 2 1 1 7 1 {hashes}\n'.encode())
    self.assertTrue(until(alice,b'PEER Bob ').startswith('PEER Bob '))
   finally:
    for sock,stream in clients: stream.close();sock.close()
    server.close()
if __name__=='__main__':unittest.main()
