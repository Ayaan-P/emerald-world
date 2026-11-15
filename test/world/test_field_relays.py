"""Execute relay gameplay through real CHAT/STATE authority paths, no sockets."""
import copy
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from test_shared_generated_cave import MemoryAuthority
from world.field_relays import COURSE


class FieldRelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.s=MemoryAuthority(self.root/'sock',self.root/'world')
        self.addCleanup(lambda:self.s.close())
        self.now=1000.0
        self.clock=patch('world.server.time.monotonic',side_effect=lambda:self.now);self.clock.start();self.addCleanup(self.clock.stop)
        self.s.relays.clock=lambda:self.now
        self.a=self.connect('Alice');self.b=self.connect('Bob');self.c=self.connect('Cara')
        self.chat(self.a,'/guild create Runners')
        for peer in (self.b,self.c):
            self.chat(self.a,'/guild invite '+peer['id'])
            self.chat(peer,'/guild accept Runners')
        for peer in self.s.peers.values():peer['chat_history']=[]

    def connect(self,name):
        who=self.s.create_identity(name)
        c=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.s._line(c,f"HELLO 1 {who['id']} {who['token']} SOCIALCHATCOMMANDS1".encode())
        self.assertEqual(c['id'],name);c['out'].clear()
        return c

    def chat(self,c,text):
        c['chat_credit']=4
        self.s._line(c,f"CHAT {c['seq']+1} * {text.encode().hex()}".encode())
        out=[bytes.fromhex(m[3]).decode() for m in c['chat_history']];c['chat_history']=[];c['out'].clear()
        return out

    def state(self,c,point):
        self.s._line(c,f"STATE {c['seq']+1} {' '.join(map(str,point))} 1 7 1 {'a'*16} {'b'*16}".encode())
        self.assertEqual(c['state'][:4],point)

    def start(self):
        self.chat(self.a,'/guild relay start '+COURSE['id'])
        run=self.s.relays._current('Alice');self.chat(self.b,'/guild relay join '+run['id'])
        for i,c in enumerate((self.a,self.b)):self.state(c,COURSE['legs'][i]['start'])
        self.chat(self.a,'/guild relay ready');self.chat(self.b,'/guild relay ready')
        self.assertEqual(run['phase'],'countdown')
        self.now+=2;self.state(self.a,COURSE['legs'][0]['start']);self.state(self.b,COURSE['legs'][1]['start'])
        self.now+=1;self.s.relays.tick();self.assertEqual(run['phase'],'running')
        return run

    def checkpoint(self,c,point):
        self.now+=0.5;self.state(c,point)
        # Idle teammates still send ordinary native presence heartbeats.
        other=self.b if c is self.a else self.a
        self.state(other,other['state'][:4])

    def finish(self):
        run=self.start()
        for point in COURSE['legs'][0]['checkpoints']:self.checkpoint(self.a,point)
        self.s.relays.tick();self.assertEqual(run['leg'],1)
        for point in COURSE['legs'][1]['checkpoints']:self.checkpoint(self.b,point)
        return run

    def test_real_two_runner_loop_automatically_tracks_and_persists_private_time(self):
        sentinel=self.root/'normal.sav';sentinel.write_bytes(b'no changes')
        run=self.finish()
        self.assertIsNone(self.s.relays._current('Alice'))
        row=self.s.db.execute('SELECT team,milliseconds,splits FROM relay_records').fetchone()
        self.assertEqual(json.loads(row[0]),['Alice','Bob']);self.assertGreater(row[1],0)
        self.assertEqual(len(json.loads(row[2])),2)
        self.assertTrue(any('finished' in bytes.fromhex(m[3]).decode() for m in self.a['chat_history']))
        self.assertEqual(self.c['chat_history'],[])
        self.assertTrue(any('No completed' in x for x in self.chat(self.c,'/guild relay records')))
        self.assertTrue(any(COURSE['id'] in x for x in self.chat(self.a,'/guild relay records')))
        self.assertEqual(sentinel.read_bytes(),b'no changes')
        self.s.close();self.s=MemoryAuthority(self.root/'sock',self.root/'world');self.s.relays.clock=lambda:self.now
        self.assertEqual(self.s.relays.runs,{})
        self.a=self.connect('Alice')
        self.assertTrue(any(COURSE['id'] in x for x in self.chat(self.a,'/guild relay records')))

    def test_baton_requires_correct_runner_order_and_adjacent_handoff_presence(self):
        run=self.start()
        self.state(self.b,COURSE['legs'][0]['checkpoints'][0]);self.assertEqual(run['checkpoint'],0)
        self.state(self.a,COURSE['legs'][0]['checkpoints'][-1]);self.assertEqual(run['checkpoint'],0)
        for p in COURSE['legs'][0]['checkpoints']:self.checkpoint(self.a,p)
        self.assertEqual(run['phase'],'handoff');self.assertEqual(run['leg'],0)
        self.state(self.b,COURSE['legs'][1]['start']);self.assertEqual(run['leg'],1)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM relay_records').fetchone()[0],0)

    def test_countdown_leaving_pad_requires_new_ready_and_is_not_a_start(self):
        self.chat(self.a,'/guild relay start '+COURSE['id']);run=self.s.relays._current('Alice')
        self.chat(self.b,'/guild relay join '+run['id'])
        for i,c in enumerate((self.a,self.b)):self.state(c,COURSE['legs'][i]['start']);self.chat(c,'/guild relay ready')
        self.state(self.a,COURSE['legs'][0]['checkpoints'][0])
        self.assertEqual(run['phase'],'lobby');self.assertEqual(run['ready'],set())

    def test_disconnect_replacement_timeout_and_restart_never_mint_records(self):
        self.start();self.b['closing']=True;self.s.relays.tick()
        self.assertEqual(self.s.relays.runs,{})
        self.b['closing']=False;self.start();self.now+=181;self.s.relays.tick()
        self.assertEqual(self.s.relays.runs,{})
        self.start();self.s.peers['Bob']=dict(self.b);self.s.relays.tick()
        self.assertEqual(self.s.relays.runs,{})
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM relay_records').fetchone()[0],0)

    def test_cancel_and_failed_finish_write_leave_no_record(self):
        self.start();self.chat(self.b,'/guild relay leave');self.assertEqual(self.s.relays.runs,{})
        self.s.db.execute("CREATE TRIGGER fail_relay BEFORE INSERT ON relay_records BEGIN SELECT RAISE(ABORT,'fixture'); END")
        self.finish();self.assertEqual(self.s.relays.runs,{})
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM relay_records').fetchone()[0],0)

    def test_course_validation_and_consent_boundary(self):
        bad=copy.deepcopy(COURSE);bad['legs'][1]['start']=[0,0,10,10]
        with self.assertRaises(ValueError):self.s.relays.publish(bad)
        bad=copy.deepcopy(COURSE);bad['title']='Conflicting course'
        with self.assertRaises(ValueError):self.s.relays.publish(bad)
        self.a['private_commands']=False
        self.assertTrue(any('matched RC12' in x for x in self.chat(self.a,'/guild relay start '+COURSE['id'])))
        self.assertEqual(self.s.relays.runs,{})

class AuthoredRelayCourseTests(unittest.TestCase):
    def test_all_course_pads_are_clear_connected_ground_away_from_npcs(self):
        import struct
        import hashlib
        from collections import deque
        root=Path(__file__).resolve().parents[2]
        raw=(root/'data/layouts/PetalburgCity/map.bin').read_bytes()
        # Verified against released native main 7d463da; no rendered playtest claim.
        self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),'35f0172ca20a07e800bc248b803e740364a24715')
        tiles=struct.unpack('<'+'H'*900,raw)
        doc=json.loads((root/'data/maps/PetalburgCity/map.json').read_text())
        def clear(x,y):return 0<=x<30 and 0<=y<30 and (tiles[y*30+x]>>10)&3==0 and tiles[y*30+x]>>12==3
        points=[tuple(p[2:]) for leg in COURSE['legs'] for p in [leg['start']]+leg['checkpoints']]
        for x,y in points:
            self.assertTrue(clear(x,y),(x,y))
            for obj in doc['object_events']:
                self.assertFalse(abs(x-obj['x'])<=obj.get('movement_range_x',0) and abs(y-obj['y'])<=obj.get('movement_range_y',0))
        seen={points[0]};queue=deque(seen)
        while queue:
            x,y=queue.popleft()
            for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if p not in seen and clear(*p):seen.add(p);queue.append(p)
        self.assertTrue(set(points)<=seen)
