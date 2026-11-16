"""Connected original/generated actor work and optional native TV delivery."""
import json,unittest
import test_cast_world_cooperation as fixture
from world import actor_runtime,actor_cooperation

def connect(server,name,role):
 token=server.create_identity(name)['token']
 peer=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
 server._line(peer,('HELLO 1 '+name+' '+token+' '+role).encode())
 assert peer['id']==name
 return peer

class CastTelevisionTests(unittest.TestCase):
 def test_real_work_report_reaches_combined_native_client(self):
  f=fixture.CastWorldWorkTests();f.setUp();self.addCleanup(f.doCleanups)
  self.assertEqual(f.offer()['status'],'succeeded');request=actor_cooperation.discover(f.s)[0]['id']
  self.assertEqual(f.act('researcher','world.respond_cooperation',dict(request=request,decision='accept'))['status'],'succeeded')
  self.assertEqual(f.act('researcher','world.configure_outbreak',dict(map='Route102',species='RALTS',level=12,chance=30,minutes=10))['status'],'succeeded')
  receipt=f.s.db.execute("SELECT max(seq) FROM actor_tool_receipts WHERE actor='researcher'").fetchone()[0]
  self.assertEqual(f.act('researcher','world.deliver_cooperation',dict(request=request,receipt=receipt))['status'],'succeeded')
  delivered=next(e['seq'] for e in f.s.memory.history()['events'] if e['event']=='character_cooperation_delivered')
  self.assertEqual(f.act('canon_rydel','world.publish_bulletin',dict(pages=json.dumps(['Researcher posted a habitat','opportunity on Route102.']),evidence=json.dumps([receipt,delivered]),hours=1))['status'],'succeeded')
  peer=connect(f.s,'Viewer','SOCIALCHAR1OUTBREAK1CONTEST1RENTALS1WORLDTV1')
  for key in ('outbreak_capable','contest_guest_capable','rental_capable','world_bulletin_capable'):self.assertTrue(peer[key])
  snapshot=f.s._snapshot(peer);line=next(l for l in snapshot.splitlines() if l.startswith('WORLD_BULLETIN '))
  self.assertIn('Rydel',bytes.fromhex(line.split()[2]).decode())
  self.assertEqual(bytes.fromhex(line.split()[3]).decode(),'Researcher posted a habitat')
  old=connect(f.s,'Old','SOCIALCHAR1OUTBREAK1CONTEST1RENTALS1')
  self.assertNotIn('WORLD_BULLETIN ',f.s._snapshot(old));self.assertTrue(old['rental_capable'])
  self.assertEqual(f.s.module_state['world_characters']['researcher']['team'],f.c['team'])
  publication=next(e for e in f.s.memory.history()['events'] if e['event']=='character_bulletin_published')
  self.assertEqual(publication['source_events'],[receipt,delivered])
  self.assertIn('not independently verified',publication['limits'])
  self.assertEqual(f.act('canon_rydel','world.withdraw_bulletin',{})['status'],'succeeded')
  self.assertNotIn('WORLD_BULLETIN ',f.s._snapshot(peer))
