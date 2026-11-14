"""Real authority protocol and durable history, not a native gameplay test."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from test_shared_generated_cave import MemoryAuthority
from world.build_catalog import catalog_maps


class CoreStoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.s=self.open();self.run='a'*32
        self.a=self.connect('Alice');self.b=self.connect('Bob')
    def open(self):return MemoryAuthority(self.root/'socket',self.root/'world')
    def tearDown(self):self.s.close();self.tmp.cleanup()
    def connect(self,name,cap=True):
        row=self.s.db.execute('SELECT token FROM identities WHERE id=?',(name,)).fetchone()
        token=row[0] if row else self.s.create_identity(name)['token']
        c=dict(id=None,out=bytearray(),closing=False,state=None,sock=object())
        self.s._line(c,f"HELLO 1 {name} {token} SOCIALCHATCOMMANDS1{'CORE1' if cap else ''}".encode())
        self.assertEqual(c['id'],name);c['out'].clear();return c
    def place(self,c,name):
        pair=next(pair for pair,m in catalog_maps().items() if m['name']==name)
        c['state']=[*pair,1,1,1,7,1];c['state_time']=time.monotonic()
    def request(self,c,action,key,confirm,run=None):
        c['out'].clear()
        self.s._line(c,f'CORE {run or self.run} {action} {key} {confirm}'.encode())
        line=c['out'].decode().strip()
        if line=='CORE REFUSED':return None
        self.assertTrue(line.startswith('CORE RESULT '),line)
        self.assertLessEqual(len(line),2048)
        return json.loads(bytes.fromhex(line.split()[2]))
    def rescue(self,c):
        self.place(c,'PetalburgWoods')
        self.assertTrue(self.request(c,'REPORT','woods_rescued','complete')['recorded'])
    def offer(self,c):
        self.place(c,'RusturfTunnel');return self.request(c,'OFFER','rusturf_grunt','safe')
    def test_private_progress_explicit_share_changes_later_canonical_offer(self):
        self.rescue(self.a);self.rescue(self.b)
        self.assertEqual(self.s.memory.history()['events'],[])
        first=self.offer(self.b);self.assertEqual(first['branch'],'baseline')
        self.assertIsNone(self.request(self.a,'SHARE','woods_rescued','yes'))
        shared=self.request(self.a,'SHARE','woods_rescued','confirm')
        self.assertEqual(self.request(self.a,'SHARE','woods_rescued','confirm'),shared)
        # Existing encounter stays stable, another trainer gets the new history.
        self.assertEqual(self.offer(self.b),first)
        later=self.offer(self.a);self.assertEqual(later['branch'],'warned')
        self.assertEqual(later['evidence'],[shared['evidence']])
        events=self.s.memory.history()['events'];self.assertEqual(len(events),1)
        public=json.dumps(events)
        for private in ('Alice','Bob',self.run,'party','token'):self.assertNotIn(private,public)
        self.assertEqual(self.b['chat_history'],[])
        self.assertNotIn('CORE',self.s._snapshot(self.b))
        recalled=self.s.memory.recall(through=events[0]['seq'],terms=['devon'])
        self.assertEqual(recalled['events'][0]['seq'],shared['evidence'])
    def test_restart_continuation_and_independent_lineages(self):
        self.rescue(self.a);self.request(self.a,'SHARE','woods_rescued','confirm')
        first=self.offer(self.a)
        self.s.close();self.s=self.open();self.a=self.connect('Alice')
        self.assertEqual(self.offer(self.a),first)
        self.assertIsNone(self.request(self.a,'OFFER','rusturf_grunt','safe',run='b'*32))
        self.assertTrue(self.request(self.a,'REPORT','goods_recovered','complete')['recorded'])
        self.assertIsNone(self.offer(self.a))
        self.request(self.a,'SHARE','goods_recovered','confirm')
        self.place(self.a,'RustboroCity_DevonCorp_3F')
        result=self.request(self.a,'OFFER','devon_return','safe')
        self.assertEqual(result['branch'],'warned')
        self.assertIn('Rusturf rescue',result['briefing'])
        self.assertEqual(result['effects'],['supplemental_briefing','objective_hint'])
    def test_capability_location_prerequisite_and_session_refusal(self):
        self.place(self.a,'RusturfTunnel')
        self.assertIsNone(self.request(self.a,'REPORT','goods_recovered','complete'))
        self.assertIsNone(self.request(self.a,'REPORT','woods_rescued','complete'))
        self.rescue(self.a);self.a['state_time']=0
        self.assertIsNone(self.request(self.a,'REPORT','woods_rescued','complete'))
        self.a['core_story_capable']=False
        self.assertIsNone(self.request(self.a,'SHARE','woods_rescued','confirm'))
        self.a['core_story_capable']=True;self.s.peers['Alice']=dict(self.a)
        self.assertIsNone(self.request(self.a,'SHARE','woods_rescued','confirm'))
        self.assertEqual(self.s.memory.history()['events'],[])
    def test_sharing_rolls_back_history_and_receipt_together(self):
        self.rescue(self.a)
        self.s.db.execute("CREATE TRIGGER fail_share BEFORE INSERT ON core_story_shared BEGIN SELECT RAISE(ABORT,'failed'); END")
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.core_story.handle(self.a,['CORE',self.run,'SHARE','woods_rescued','confirm'])
        self.assertEqual(self.s.memory.history()['events'],[])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_memory_lookup').fetchone()[0],0)
    def test_offline_snapshot_rewind_and_compact_native_wire(self):
        self.place(self.a,'RustboroCity_DevonCorp_3F')
        self.assertEqual(self.request(self.a,'SYNC','3','private')['progress'],3)
        first=self.request(self.a,'OFFER','devon_return','safe')
        self.assertIsNotNone(first)
        self.assertEqual(self.s.memory.history()['events'],[])
        self.request(self.a,'SYNC','7','private')
        self.assertIsNone(self.request(self.a,'OFFER','devon_return','safe'))
        self.request(self.a,'SYNC','1','private')
        self.assertIsNone(self.request(self.a,'OFFER','devon_return','safe'))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM core_story_offers').fetchone()[0],0)
        self.assertIsNone(self.request(self.a,'SYNC','2','private'))
        self.place(self.a,'RusturfTunnel');self.a['out'].clear()
        self.s._line(self.a,f'CORE {self.run} OFFER rusturf_grunt safe 42'.encode())
        wire=self.a['out'].decode().split()
        self.assertEqual(wire[:6],['CORE','REPLY','42',self.run,'OFFER','rusturf_grunt'])
        self.assertEqual(wire[6],self.s.memory.world_id)
        self.assertEqual(bytes.fromhex(wire[8]).decode(),'The Aqua thief has cornered Peeko. Recover the Devon goods and bring Peeko home. Defeat the Aqua grunt and finish the Peeko rescue.')
        self.assertEqual(self.b['chat_history'],[])

    def test_unrelated_history_and_contract_do_not_claim_native_connection(self):
        with self.s.db:self.s.memory.append('landmark_discovery_shared',dict(place_id='native:PetalburgWoods',landmark='Devon warned',revision='a'))
        self.rescue(self.a);self.assertEqual(self.offer(self.a)['branch'],'baseline')
        c=dict(id=None,out=bytearray(),closing=False,sock=object())
        self.s._admin_line(c,b'{"command":"core_story_contract"}')
        contract=json.loads(c['out']);self.assertTrue(contract['ok']);self.assertFalse(contract['native_connected'])
        self.assertNotIn('Alice',json.dumps(contract))


if __name__=='__main__':unittest.main()
