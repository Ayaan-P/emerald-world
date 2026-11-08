import unittest
import test_field_relays
from world.mount_motion import decode
from world.field_relays import COURSE


class MountedRaces(unittest.TestCase):
    setUp=test_field_relays.FieldRelayTests.setUp
    chat=test_field_relays.FieldRelayTests.chat
    def connect(self,name):
        who=self.s.create_identity(name)
        c=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.s._line(c,f"HELLO 1 {who['id']} {who['token']} SOCIALCHATCOMMANDS1MOUNTS1".encode())
        self.assertEqual(c['id'],name);c['out'].clear();return c
    def state(self,c,point,trail='.',species=78):
        self.s._line(c,f"MSTATE {c['seq']+1} {' '.join(map(str,point))} 1 7 1 {'a'*16} {'b'*16} {species} 0 {trail}".encode())
        self.assertFalse(c['closing']);self.assertEqual(c['state'][:4],point)
    def start(self):
        for i,c in enumerate((self.a,self.b)):self.state(c,COURSE['legs'][i]['start'])
        self.chat(self.a,'/guild play start relay petalburg_mount1')
        r=self.s.relays._current('Alice');self.chat(self.b,'/guild relay join '+r['id'])
        self.chat(self.a,'/guild relay ready');self.chat(self.b,'/guild relay ready')
        self.now+=2
        for i,c in enumerate((self.a,self.b)):self.state(c,COURSE['legs'][i]['start'])
        self.now+=1;self.s.relays.tick();return r
    def test_complete_mounted_race_preserves_turns_and_skipped_endpoint(self):
        r=self.start();self.assertEqual(r['phase'],'running')
        # 10,12 is visited but absent from the final sampled position.
        self.state(self.a,[0,0,11,12],'10,11/10,12/11,12')
        self.assertEqual(r['checkpoint'],1)
        # Witness every turn/tile, rather than drawing a straight line.
        self.state(self.a,[0,0,18,13],'/'.join([f'{x},12' for x in range(12,19)]+['18,13']))
        self.assertEqual(r['checkpoint'],2)
        self.state(self.a,[0,0,21,12],'19,13/20,13/21,13/21,12')
        self.s.relays.tick();self.assertEqual(r['leg'],1)
        self.state(self.b,[0,0,22,10],'22,11/22,10')
        self.state(self.b,[0,0,23,10],'23,10')
        self.state(self.b,[0,0,23,13],'23,11/23,12/23,13')
        self.assertIsNone(self.s.relays._current('Alice'))
        self.assertEqual(self.s.db.execute('SELECT course FROM relay_records').fetchone()[0],'petalburg_mount1')
    def test_trace_loss_and_dismount_cancel_not_invent_visits(self):
        self.start();self.state(self.a,[0,0,12,12],'!')
        self.assertIsNone(self.s.relays._current('Alice'))
        r=self.start();self.state(self.a,COURSE['legs'][0]['start'],species=0)
        self.assertIsNone(self.s.relays._current('Alice'))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM relay_records').fetchone()[0],0)
    def test_peer_mounts_only_in_matched_snapshot(self):
        self.state(self.a,[0,0,10,10]);self.state(self.b,[0,0,22,12])
        snapshot=self.s._snapshot(self.b)
        if isinstance(snapshot,bytes):snapshot=snapshot.decode()
        self.assertIn('MOUNTS 1',snapshot);self.assertIn('RIDER Alice 78 0',snapshot)
        self.b['mount_capable']=False
        snapshot=self.s._snapshot(self.b)
        if isinstance(snapshot,bytes):snapshot=snapshot.decode()
        self.assertNotIn('MOUNTS',snapshot);self.assertNotIn('RIDER',snapshot)
    def test_noncontiguous_or_diagonal_witnesses_never_interpolate(self):
        prior=[0,0,10,10,1,7,1];after=[0,0,12,12,1,7,1]
        self.assertEqual(decode('12,12',prior,after,(78,0),(78,0),True),([],True))
        self.assertEqual(decode('.',prior,after,(78,0),(78,0),True),([],True))
        with self.assertRaises(ValueError):decode('10,11/'*20,prior,after,(78,0),(78,0),True)
