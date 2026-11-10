import json,socket,tempfile,time,unittest
from pathlib import Path
from world.server import WorldServer
from world import combined_regions as regions
from world.build_catalog import validate_coords,validate_tile

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

class WireHandlers(unittest.TestCase):
 def setUp(self):
  from unittest.mock import Mock
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.s=WorldServer(self.tmp.name+'/s',self.tmp.name+'/world',combined_regions=True);self.addCleanup(self.s.close)
  self.s.selector=Mock();self.s.selector.get_map.return_value={}
 def connection(self):
  from unittest.mock import Mock
  sock=Mock();c=dict(sock=sock,id=None,seq=-1,state=None,out=bytearray(),closing=False,born=time.monotonic());self.s.connections[sock]=c;return c
 def send(self,c,line):
  c['out'].clear();self.s._line(c,line.encode());return c['out'].decode()
 def peer(self,name,proof=True):
  ident=self.s.create_identity(name);p=self.connection();self.assertIn('WELCOME',self.send(p,'HELLO 1 '+name+' '+ident['token']+' SOCIAL'))
  l=self.connection();self.assertIn('WELCOME',self.send(l,'HELLO 1 '+name+' '+ident['token']+' LINK'))
  if proof:self.send(l,'RGC 1 '+regions.DIGEST)
  return p,l
 def state(self,p,seq,g,n,x,y):return self.send(p,f'STATE {seq} {g} {n} {x} {y} 2 7 1 '+'a'*16+' '+'b'*16)
 def test_pallet_peer_snapshot_and_hoenn_return(self):
  a,al=self.peer('Alice');b,bl=self.peer('Bob');self.state(a,1,38,0,10,10)
  self.assertEqual(a['state'][:4],[38,0,10,10]);self.assertIn('PEER Alice 38 0 10 10',self.s._snapshot(b))
  self.state(a,2,0,1,10,12);self.assertIn('PEER Alice 0 1 10 12',self.s._snapshot(b))
  self.assertEqual(self.s.db.execute("SELECT party_hash,bag_hash FROM identities WHERE id='Alice'").fetchone(),('a'*16,'b'*16))
 def test_no_proof_no_presence_timeout_and_wrong_digest(self):
  a,al=self.peer('Alice',False);self.state(a,1,38,0,10,10);self.assertIsNone(a['state']);self.assertNotIn('PEER',self.s._snapshot(a))
  self.assertIn('ERROR REGISTRY',self.send(al,'RGC 1 '+'0'*64));self.assertTrue(a['closing'])
  b,bl=self.peer('Bob',False);b['registry_wait']=time.monotonic()-10;self.assertIn('REGISTRY_REQUIRED',self.state(b,1,0,1,1,1))
 def test_reconnect_invalidates_old_link_and_coordinates(self):
  a,al=self.peer('Alice');self.state(a,1,38,0,24,10);self.assertIn(b'ERROR',a['out']);self.assertIsNone(a['state'])
  self.s._drop(al);self.assertNotIn('Alice',self.s.peers)
  new,nl=self.peer('Alice',False);self.state(new,1,38,0,1,1);self.assertIsNone(new['state'])
  self.send(al,'RGC 1 '+regions.DIGEST);self.assertFalse(regions.admitted(self.s,new))
  self.send(nl,'RGC 1 '+regions.DIGEST);self.state(new,2,38,0,1,1);self.assertEqual(new['state'][:2],[38,0])
 def test_default_world_legacy_and_combined_mismatch(self):
  self.s.close();self.s=WorldServer(self.tmp.name+'/s2',self.tmp.name+'/legacy');self.addCleanup(self.s.close)
  from unittest.mock import Mock
  self.s.selector=Mock();self.s.selector.get_map.return_value={}
  a,al=self.peer('Alice',False);self.state(a,1,0,1,1,1);self.assertEqual(a['state'][:2],[0,1])
  self.send(al,'RGC 1 '+regions.DIGEST);self.assertTrue(a['closing'])
