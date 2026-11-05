"""Exercise the experimental authority through real authenticated dispatch.

No sockets, external world, real identities or personal saves are used.
"""
from pathlib import Path
import tempfile, unittest
from world.server import WorldServer
from world.shared_cave import SharedCave, CaveError

ROWS=['#'*31]+['#'+'.'*29+'#']*29+['#'*31]
BLOB=b'EWGMAP01'+''.join(ROWS).encode('ascii')

class MemoryAuthority(WorldServer):
 def _queue(self, conn, text): conn['out'].extend(text.encode('ascii'))
 def _broadcast(self): pass

class SharedCaveTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
  self.server=MemoryAuthority(root/'socket',root/'world',cave_template=BLOB)
  self.alice=self.server.create_identity('Alice');self.bob=self.server.create_identity('Bob')
 def tearDown(self): self.server.close();self.tmp.cleanup()
 def conn(self,identity=None,role='SOCIALTRAVELCHATRALLYCAVE'):
  conn={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
  if identity:
   self.server._line(conn,('HELLO 1 %s %s %s' % (identity['id'],identity['token'],role)).encode())
   self.assertIn(b'WELCOME 1',conn['out']);conn['out'].clear()
  return conn
 def send(self,c,line):
  self.server._line(c,line.encode());out=c['out'].decode('ascii');c['out'].clear();return out
 def state(self,c,seq,x,y):
  group,num=self.server.cave_map
  return self.send(c,f'STATE {seq} {group} {num} {x} {y} 1 7 1 '+('a'*16)+' '+('b'*16))
 def test_authority_validates_and_sends_same_map_to_both(self):
  for identity in (self.alice,self.bob):
   c=self.conn(identity);lines=self.send(c,'CAVE GET').splitlines();self.assertEqual(len(lines),33)
   digest=self.server.shared_cave.identity;self.assertEqual(lines[0],'CAVE BEGIN '+digest);self.assertEqual(lines[-1],'CAVE END '+digest)
   self.assertEqual([line.split(' ')[-1] for line in lines[1:-1]],ROWS)
   self.assertEqual(self.send(c,'CAVE ACK '+digest),'CAVE OK '+digest+'\n')
   self.assertNotIn('ERROR',self.state(c,1,1,1));self.assertEqual(c['state'][:4],[*self.server.cave_map,1,1])
 def test_same_instance_sees_peer_but_travel_roster_omits_cave(self):
  alice=self.conn(self.alice);bob=self.conn(self.bob);digest=self.server.shared_cave.identity
  for c in (alice,bob): self.send(c,'CAVE GET');self.send(c,'CAVE ACK '+digest)
  self.state(alice,1,1,1);self.state(bob,1,2,1)
  snapshot=self.server._snapshot(alice)
  self.assertIn('PEER Bob ',snapshot);self.assertNotIn('FRIEND Bob ',snapshot)
  self.assertNotIn('Alice',self.server._link_presence());self.assertNotIn('Bob',self.server._link_presence())
 def test_cave_players_are_not_rally_eligible_and_active_rally_blocks_entry(self):
  import time
  alice=self.conn(self.alice);digest=self.server.shared_cave.identity
  self.send(alice,'CAVE GET');self.send(alice,'CAVE ACK '+digest);self.state(alice,1,1,1)
  alice['rally_eligible']=True;alice['rally_report']=time.monotonic();alice['state_time']=time.monotonic()
  self.assertFalse(self.server.rally.fresh(alice))
  bob=self.conn(self.bob);self.send(bob,'CAVE GET');self.send(bob,'CAVE ACK '+digest)
  original=self.server.rally.current;self.server.rally.current=lambda conn: {'id':1} if conn is bob else None
  try: self.assertIn('ERROR',self.state(bob,1,1,1))
  finally: self.server.rally.current=original
 def test_legacy_first_snapshot_never_contains_generated_peer(self):
  alice=self.conn(self.alice);self.send(alice,'CAVE GET');self.send(alice,'CAVE ACK '+self.server.shared_cave.identity);self.state(alice,1,1,1)
  bob=self.conn(self.bob,'SOCIALTRAVELCHATRALLY')
  self.assertNotIn('PEER Alice ',self.server._snapshot(bob))
  self.assertNotIn('FRIEND Alice ',self.server._snapshot(bob))
 def test_capability_is_not_permission_to_publish_or_resume_without_ack(self):
  c=self.conn(self.alice);self.assertIn('ERROR CAVE',self.send(c,'CAVE ACK '+'0'*64))
  # A fresh authenticated presence connection cannot inherit a previous ACK.
  old=self.conn(self.bob);self.send(old,'CAVE GET');self.send(old,'CAVE ACK '+self.server.shared_cave.identity)
  del self.server.peers['Bob'];fresh=self.conn(self.bob)
  self.assertIn('ERROR',self.state(fresh,1,1,1))
 def test_unadmitted_or_wall_position_is_rejected(self):
  c=self.conn(self.alice);self.assertIn('ERROR',self.state(c,1,1,1));self.assertTrue(c['closing'])
  c=self.conn(self.bob);self.send(c,'CAVE GET');self.send(c,'CAVE ACK '+self.server.shared_cave.identity)
  self.assertIn('ERROR',self.state(c,1,0,0));self.assertTrue(c['closing'])
 def test_no_publication_and_legacy_or_control_has_no_access(self):
  c=self.conn();self.assertIn('ERROR AUTH',self.send(c,'CAVE GET'))
  c=self.conn(self.alice,'SOCIAL');self.assertIn('ERROR CAVE',self.send(c,'CAVE GET'))
  c=self.conn(self.bob);self.assertIn('ERROR CAVE',self.send(c,'CAVE PUT '+self.server.shared_cave.identity))
 def test_digest_must_match_issued_offer_and_rate_is_bounded(self):
  c=self.conn(self.alice);self.assertIn('ERROR CAVE',self.send(c,'CAVE ACK '+self.server.shared_cave.identity))
  c=self.conn(self.bob);self.send(c,'CAVE GET');self.assertEqual(self.send(c,'CAVE GET'),'CAVE BUSY\n')
 def test_world_mechanics_cannot_change_ephemeral_cave_geometry(self):
  group,num=self.server.cave_map
  tile={'group':group,'num':num,'x':1,'y':1,'metatile':0x333,'collision':1}
  with self.assertRaises(ValueError): self.server._validated({'state':{},'tiles':[tile]})
  obj={'id':'test','group':group,'num':num,'x':1,'y':1,'gfx':7,'text':'hello'}
  with self.assertRaises(ValueError): self.server._validated({'state':{},'tiles':[],'objects':[obj]})
  # Other catalog maps retain their normal mechanics behavior.
  tile.update(group=0,num=0,x=1,y=1,metatile=0,collision=0)
  self.server._validated({'state':{},'tiles':[tile]})
 def test_no_template_means_reserved_cave_is_not_enterable(self):
  with tempfile.TemporaryDirectory() as d:
   server=MemoryAuthority(Path(d)/'s',Path(d)/'world')
   try:
    identity=server.create_identity('NoCave')
    c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(c,('HELLO 1 %s %s SOCIALCAVE' % (identity['id'],identity['token'])).encode());c['out'].clear()
    server._line(c,b'CAVE GET');self.assertEqual(c['out'],b'CAVE NONE\n');c['out'].clear()
    g,n=server.cave_map;server._line(c,(f'STATE 1 {g} {n} 1 1 1 7 1 '+('a'*16)+' '+('b'*16)).encode())
    self.assertIn(b'ERROR',c['out']);self.assertTrue(c['closing'])
   finally: server.close()
 def test_live_replacement_revokes_acks_and_resynchronizes_without_client_upload(self):
  alice=self.conn(self.alice);bob=self.conn(self.bob,'SOCIALTRAVELCHATRALLY');old=self.server.shared_cave.identity
  self.send(alice,'CAVE GET');self.send(alice,'CAVE ACK '+old)
  changed=bytearray(BLOB);changed[8+2*31+2]=ord('#');new=self.server._replace_cave(bytes(changed))
  self.assertNotEqual(new,old);self.assertEqual(alice['out'].decode(),'CAVE RESET '+new+'\n');alice['out'].clear()
  self.assertEqual(bob['out'],b'') # old clients never receive new protocol frames
  self.assertEqual(self.send(alice,'CAVE ACK '+old),'CAVE RESET '+new+'\n')
  self.assertEqual(self.state(alice,1,1,1),'CAVE RESET '+new+'\n')
  self.assertIsNone(alice['state']);self.assertEqual(self.send(alice,'CAVE GET'),'CAVE BUSY\n')
  alice['cave_next']=0;self.assertEqual(self.send(alice,'CAVE GET').splitlines()[0],'CAVE BEGIN '+new)
  self.assertEqual(self.send(alice,'CAVE ACK '+new),'CAVE OK '+new+'\n');self.assertNotIn('ERROR',self.state(alice,2,1,1))
 def test_live_replacement_is_atomic_and_refuses_occupied_or_unready_cave(self):
  alice=self.conn(self.alice);old=self.server.shared_cave.identity
  self.send(alice,'CAVE GET');self.send(alice,'CAVE ACK '+old);self.state(alice,1,1,1)
  changed=bytearray(BLOB);changed[8+2*31+2]=ord('#')
  with self.assertRaisesRegex(ValueError,'occupied'):self.server._replace_cave(bytes(changed))
  self.assertEqual(self.server.shared_cave.identity,old)
  self.send(alice,'STATE 2 0 0 0 0 1 7 0 '+('a'*16)+' '+('b'*16))
  self.assertTrue(alice['in_generated_cave'])
  with self.assertRaisesRegex(ValueError,'occupied'):self.server._replace_cave(bytes(changed))
  self.send(alice,'STATE 3 0 0 1 1 1 7 1 '+('a'*16)+' '+('b'*16))
  self.assertFalse(alice['in_generated_cave']);self.assertNotEqual(self.server._replace_cave(bytes(changed)),old)
 def test_backpressure_prevents_partial_replacement(self):
  alice=self.conn(self.alice);before=self.server.shared_cave.identity;alice['out'].extend(b'x'*65530)
  changed=bytearray(BLOB);changed[8+2*31+2]=ord('#')
  with self.assertRaisesRegex(ValueError,'busy'):self.server._replace_cave(bytes(changed))
  self.assertEqual(self.server.shared_cave.identity,before);self.assertEqual(len(alice['out']),65530)
 def test_first_live_publication_notifies_capable_peers(self):
  with tempfile.TemporaryDirectory() as d:
   server=MemoryAuthority(Path(d)/'s',Path(d)/'world')
   try:
    identity=server.create_identity('NoCave');c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(c,('HELLO 1 %s %s SOCIALCAVE' % (identity['id'],identity['token'])).encode());c['out'].clear()
    server._line(c,b'CAVE GET');self.assertEqual(c['out'],b'CAVE NONE\n');c['out'].clear()
    new=server._replace_cave(BLOB);self.assertEqual(c['out'].decode(),'CAVE RESET '+new+'\n')
   finally:server.close()
 def test_admin_replace_only_accepts_complete_canonical_template(self):
  import base64,json
  admin={'out':bytearray(),'closing':False}
  changed=bytearray(BLOB);changed[8+2*31+2]=ord('#');encoded=base64.b64encode(changed).decode()
  self.server._admin_line(admin,json.dumps({'command':'replace_cave','template':encoded}).encode())
  result=json.loads(admin['out']);self.assertTrue(result['ok']);self.assertFalse(result['persistent'])
  bad={'out':bytearray(),'closing':False};before=self.server.shared_cave.identity
  self.server._admin_line(bad,b'{"command":"replace_cave","template":"not-base64!"}')
  self.assertFalse(json.loads(bad['out'])['ok']);self.assertEqual(self.server.shared_cave.identity,before);self.assertIsNone(self.server.module_error)
 def test_invalid_geometry_rejected_before_world_starts(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   with self.assertRaises(CaveError): MemoryAuthority(root/'s',root/'world',cave_template=BLOB[:-1])
   self.assertFalse((root/'world').exists())
  with self.assertRaises(CaveError): SharedCave(BLOB[:-1])
  damaged=bytearray(BLOB);damaged[8]=ord('.');
  with self.assertRaises(CaveError): SharedCave(bytes(damaged))
if __name__=='__main__':unittest.main()
