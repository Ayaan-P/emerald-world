"""Exercise persistent shared stories through real authority/native-chat dispatch."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from test_shared_generated_cave import MemoryAuthority
from world.opportunities import validate

ROOT=Path(__file__).resolve().parents[2]


class OpportunityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.s=MemoryAuthority(self.root/'sock',self.root/'world')
        self.doc=json.loads((ROOT/'examples/river_opportunities.json').read_text())
        self.a=self.connect('Alice');self.b=self.connect('Bob')
        self.assertTrue(self.admin(dict(command='publish_opportunities',pack=self.doc))['ok'])

    def tearDown(self):self.s.close();self.tmp.cleanup()

    def connect(self,name):
        who=self.s.create_identity(name)
        conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.s._line(conn,f"HELLO 1 {who['id']} {who['token']} SOCIALTRAVELCHATRALLYCAVE".encode())
        self.assertIn(b'WELCOME 1',conn['out']);conn['out'].clear()
        self.s._line(conn,('STATE 1 0 0 1 1 1 7 1 '+'a'*16+' '+'b'*16).encode())
        self.assertEqual(conn['state'][:2],[0,0]);conn['out'].clear()
        return conn

    def admin(self,request):
        conn=dict(out=bytearray());self.s._admin_line(conn,json.dumps(request).encode())
        return json.loads(conn['out'])

    def chat(self,conn,message):
        conn['chat_credit']=4
        self.s._line(conn,f"CHAT {conn['seq']+1} * {message.encode().hex()}".encode())
        result=[bytes.fromhex(entry[3]).decode() for entry in conn['chat_history']]
        conn['chat_history']=[];conn['out'].clear();return result

    def choose(self,conn,scene,choice):
        lines=self.chat(conn,'/story river')
        command=next(line for line in lines if line.startswith(f'/story pick river {scene} {choice} '))
        return command,self.chat(conn,command)

    def test_shared_relief_loop_changes_another_players_story(self):
        sentinel=self.root/'native.sav';sentinel.write_bytes(b'untouched')
        self.assertTrue(any('Floodwater' in line for line in self.chat(self.b,'/story')))
        self.choose(self.a,'bank','repair')
        self.assertFalse(self.b['chat_history']) # Alice's choices are not broadcast.
        bob=self.chat(self.b,'/story');self.assertFalse(any('Floodwater' in line for line in bob))
        self.assertTrue(any('two volunteers' in line for line in bob))
        self.choose(self.a,'relief','help');self.choose(self.b,'relief','help')
        self.choose(self.b,'launch','open')
        self.assertTrue(any('remembers your help' in line for line in self.chat(self.a,'/story')))
        late=self.connect('Cara')
        self.assertFalse(any('remembers your help' in line for line in self.chat(late,'/story')))
        self.assertEqual(sentinel.read_bytes(),b'untouched')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_consequences').fetchone()[0],4)

    def test_alternative_changes_place_and_restart_preserves_private_history(self):
        command,_=self.choose(self.a,'bank','cut')
        self.assertTrue(any('Bird nests' in line for line in self.chat(self.b,'/story')))
        replay=self.chat(self.a,command);self.assertTrue(any('nesting reedbed is gone' in line for line in replay))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_consequences').fetchone()[0],1)
        self.s.close();self.s=MemoryAuthority(self.root/'sock',self.root/'world')
        self.assertTrue(any(s['id']=='reeds' for p in self.s.opportunities.offers('Bob','PetalburgCity') for s in p['scenes']))
        self.assertEqual(self.s.opportunities.offers('Alice','PetalburgCity')[0]['revision'],1)

    def test_stale_remote_and_repeated_actions_refused(self):
        lines=self.chat(self.b,'/story');stale=next(line for line in lines if ' bank cut ' in line)
        self.choose(self.a,'bank','repair')
        self.assertTrue(any('place changed' in line for line in self.chat(self.b,stale)))
        self.a['state_time']-=100
        self.assertTrue(any('Stand ready' in line for line in self.chat(self.a,'/story')))
        self.assertFalse(self.admin(dict(command='publish_opportunities',pack=dict(self.doc,title='Replacement')))['ok'])

    def test_atomic_effect_receipt_and_history_rollback(self):
        self.s.db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON story_receipts BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.Error):
            self.s.opportunities.choose('Alice','PetalburgCity','river','bank','repair',0,'request')
        for table in ('story_places','story_players','story_consequences','story_receipts'):
            self.assertEqual(self.s.db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
        self.s.db.execute('DROP TRIGGER fail_receipt')
        self.s.opportunities.choose('Alice','PetalburgCity','river','bank','repair',0,'request')
        with self.assertRaises(ValueError):self.s.opportunities.choose('Alice','PetalburgCity','river','bank','cut',0,'request')

    def test_validation_and_private_quality_not_in_public_consequence(self):
        broken=copy.deepcopy(self.doc);broken['scenes']['bank']['choices']['repair']['effects']['trust']=True
        with self.assertRaises(ValueError):validate(broken,{'PetalburgCity'})
        self.choose(self.a,'bank','repair')
        changes=json.loads(self.s.db.execute('SELECT changes FROM story_consequences').fetchone()[0])
        self.assertEqual(changes,{'flood':-1})
        self.assertNotIn('story_players',json.dumps(self.s.inspect()))


if __name__=='__main__':unittest.main()
