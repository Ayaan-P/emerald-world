import json,socket,tempfile,time,unittest
from pathlib import Path
from world.server import WorldServer
from world import combined_regions as regions
from world.build_catalog import validate_coords,validate_tile

class CombinedPresence(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.s=WorldServer(str(self.root/'socket'),str(self.root/'world'),combined_regions=True);self.addCleanup(self.s.close);self.s.start();self.sockets=[]
  self.addCleanup(lambda:[s.close() for s in self.sockets])
 def socket(self):
  s=socket.socket(socket.AF_UNIX);s.settimeout(2);s.connect(str(self.root/'socket'));self.sockets.append(s);f=s.makefile('rb');self.addCleanup(f.close);return s,f
 def until(self,f,prefix):
  for _ in range(100):
   line=f.readline()
   if line.startswith(prefix):return line
   if not line:break
  self.fail('Missing '+repr(prefix))
 def connect(self,name,proof=True):
  identity=self.s.create_identity(name);p,pf=self.socket();p.sendall(('HELLO 1 '+name+' '+identity['token']+' SOCIAL\n').encode());self.until(pf,b'WELCOME');self.until(pf,b'END')
  l,lf=self.socket();l.sendall(('HELLO 1 '+name+' '+identity['token']+' LINK\n').encode());self.until(lf,b'WELCOME')
  if proof:l.sendall(('RGC 1 '+regions.DIGEST+'\n').encode());self.until(pf,b'END')
  return p,pf,l,lf
 def state(self,p,seq,g,n,x,y):p.sendall((f'STATE {seq} {g} {n} {x} {y} 2 7 1 '+'a'*16+' '+'b'*16+'\n').encode())
 def test_actual_pallet_presence_return_to_hoenn_and_client_hashes(self):
  a,af,al,alf=self.connect('Alice');b,bf,bl,blf=self.connect('Bob')
  self.state(a,1,38,0,10,10);self.assertIn(b'38 0 10 10',self.until(bf,b'PEER Alice'))
  self.state(a,2,0,1,10,12);self.assertIn(b'0 1 10 12',self.until(bf,b'PEER Alice'))
  self.assertEqual(self.s.db.execute("SELECT party_hash,bag_hash FROM identities WHERE id='Alice'").fetchone(),('a'*16,'b'*16))
 def test_no_presence_before_proof_then_matching_proof(self):
  a,af,al,alf=self.connect('Alice',False);self.state(a,1,38,0,10,10);time.sleep(.05)
  self.assertIsNone(self.s.peers['Alice']['state'])
  al.sendall(('RGC 1 '+regions.DIGEST+'\n').encode());self.until(af,b'END');self.state(a,2,38,0,10,10)
  for _ in range(50):
   if self.s.peers['Alice']['state']:break
   time.sleep(.01)
  self.assertEqual(self.s.peers['Alice']['state'][:4],[38,0,10,10])
 def test_bad_digest_rejected_both_channels(self):
  a,af,al,alf=self.connect('Alice',False);al.sendall(('RGC 1 '+'0'*64+'\n').encode())
  self.assertEqual(self.until(af,b'ERROR'),b'ERROR REGISTRY\n');self.assertEqual(self.until(alf,b'ERROR'),b'ERROR REGISTRY\n')
 def test_link_disconnect_revokes_presence(self):
  a,af,al,alf=self.connect('Alice');self.state(a,1,38,0,10,10);alf.close();al.close()
  for _ in range(100):
   if 'Alice' not in self.s.peers:break
   time.sleep(.01)
  self.assertNotIn('Alice',self.s.peers)
 def test_timeout_rejects_nonmatching_client(self):
  a,af,al,alf=self.connect('Alice',False)
  with self.s.lock:self.s.peers['Alice']['registry_wait']=time.monotonic()-10
  self.assertEqual(self.until(af,b'ERROR'),b'ERROR REGISTRY_REQUIRED\n')
 def test_invalid_pallet_coordinates_rejected(self):
  a,af,al,alf=self.connect('Alice');self.state(a,1,38,0,24,10);self.assertTrue(self.until(af,b'ERROR'))

class CatalogAndWorld(unittest.TestCase):
 def test_per_map_allocations_and_unchanged_vanilla(self):
  self.assertEqual(len(regions.catalog()),937);self.assertEqual(regions.coords(38,0,23,19)['name'],'PalletTown_Frlg')
  for tile in (639,640,728):regions.tile([38,0,1,1,tile,0])
  with self.assertRaises(ValueError):regions.tile([38,0,1,1,729,0])
  validate_tile([0,1,1,1,512,0]);regions.tile([0,1,1,1,512,0])
  with self.assertRaises(ValueError):validate_coords(38,0,1,1)
 def test_profile_restart_and_downgrade_protection(self):
  with tempfile.TemporaryDirectory() as d:
   s=WorldServer(d+'/s',d+'/world',combined_regions=True);s.close()
   s=WorldServer(d+'/s',d+'/world',combined_regions=True);s.close()
   with self.assertRaises(ValueError):WorldServer(d+'/s',d+'/world')
  with tempfile.TemporaryDirectory() as d:
   s=WorldServer(d+'/s',d+'/world');s.close()
   with self.assertRaises(ValueError):WorldServer(d+'/s',d+'/world',combined_regions=True)
 def test_default_legacy_hoenn_transport(self):
  with tempfile.TemporaryDirectory() as d:
   s=WorldServer(d+'/s',d+'/world');ident=s.create_identity('Legacy');s.start()
   try:
    with socket.socket(socket.AF_UNIX) as p:
     p.settimeout(2);p.connect(d+'/s');f=p.makefile('rb')
     try:
      p.sendall(('HELLO 1 Legacy '+ident['token']+'\n').encode());self.assertTrue(f.readline().startswith(b'WELCOME'))
      p.sendall(('STATE 1 0 1 10 12 2 7 1 '+'a'*16+' '+'b'*16+'\n').encode())
      for _ in range(50):
       if s.peers['Legacy']['state']:break
       time.sleep(.01)
      self.assertEqual(s.peers['Legacy']['state'][:4],[0,1,10,12])
     finally:f.close()
   finally:s.close()
