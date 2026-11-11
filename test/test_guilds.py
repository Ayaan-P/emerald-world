import ast
import sys
import re
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from world import guilds
from world.guild_chat import GuildChat
from world.landmark_survey import LandmarkSurvey
from world.private_commands import route as route_private_command

def database(path=':memory:'):
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE identities(id TEXT PRIMARY KEY, party_hash TEXT, bag_hash TEXT)')
    db.executemany('INSERT INTO identities VALUES(?,?,?)',[(x,'0'*16,'0'*16) for x in ('Alice','Bob','Eve','Cara')])
    db.commit()
    return db

def bounded(value,lo,hi):
    if not value.isascii() or not value.isdecimal() or len(value)>20: raise ValueError()
    n=int(value)
    if not lo<=n<=hi: raise ValueError()
    return n

class GuildTests(unittest.TestCase):
    def setUp(self):
        self.db=database();self.g=guilds.Guilds(self.db,{(0,9):{'name':'Route101'}})
    def tearDown(self): self.db.close()
    def test_invitation_membership_and_leadership(self):
        self.g.command('Alice','create Rockets')
        with self.assertRaises(guilds.GuildError):self.g.command('Bob','accept Rockets')
        self.g.command('Alice','invite Bob')
        self.assertIn('Rockets',self.g.command('Bob','invites')[0])
        self.g.command('Bob','accept rockets')
        self.assertEqual(self.g.members('Bob'),('Rockets',['Alice','Bob']))
        with self.assertRaises(guilds.GuildError):self.g.command('Bob','kick Alice')
        with self.assertRaises(guilds.GuildError):self.g.command('Alice','leave')
        self.g.command('Alice','transfer Bob')
        self.g.command('Bob','kick Alice')
        self.assertEqual(self.g.members('Bob'),('Rockets',['Bob']))
        self.g.command('Bob','disband')
        with self.assertRaises(guilds.GuildError):self.g.members('Bob')
    def test_no_cross_guild_invite_or_name_collision(self):
        self.g.command('Alice','create Rockets')
        with self.assertRaises(guilds.GuildError):self.g.command('Eve','create rockets')
        self.g.command('Eve','create Trainers')
        with self.assertRaises(guilds.GuildError):self.g.command('Eve','invite Alice')
        with self.assertRaises(guilds.GuildError):self.g.command('Alice','invite Missing')
        self.g.command('Alice','invite Bob');self.g.command('Eve','invite Bob')
        self.g.command('Bob','accept Trainers')
        self.assertEqual(self.g.command('Bob','invites'),['No guild invitations.'])
    def test_capacity_and_stale_invites(self):
        self.g.command('Alice','create Rockets');self.g.command('Alice','invite Bob')
        self.db.executemany('INSERT INTO guild_members VALUES(?,1)',[(f'P{i}',) for i in range(49)])
        self.db.commit()
        with self.assertRaises(guilds.GuildError):self.g.command('Bob','accept Rockets')
        self.g.command('Alice','disband')
        self.assertEqual(self.g.command('Bob','invites'),['No guild invitations.'])
    def test_expedition_counts_each_member_once_and_persists_completion(self):
        self.g.command('Alice','create Rockets');self.g.command('Alice','invite Bob');self.g.command('Bob','accept Rockets')
        with self.assertRaises(guilds.GuildError):self.g.command('Bob','expedition start Route101 2')
        with self.assertRaises(guilds.GuildError):self.g.command('Alice','expedition start BadMap 2')
        self.g.command('Alice','expedition start route101 2')
        self.assertIsNone(self.g.visit('Eve','Route101'))
        self.assertIsNone(self.g.visit('Alice','Other'))
        self.assertIsNone(self.g.visit('Alice','Route101'))
        self.assertIsNone(self.g.visit('Alice','Route101'))
        self.assertIn('1/2',self.g.command('Bob','expedition')[0])
        self.assertEqual(self.g.visit('Bob','Route101'),('Rockets','Route101',2,['Alice','Bob']))
        self.assertIsNone(self.g.visit('Bob','Route101'))
        self.assertIn('complete',self.g.command('Alice','expedition')[0])
        self.assertIn('10 guild XP',self.g.command('Alice','info')[1])
        self.g.command('Alice','expedition start Route101 1')
        self.assertIn('0/1',self.g.command('Alice','expedition')[0])
        self.g.command('Alice','expedition cancel')
        self.assertIn('No expedition',self.g.command('Alice','expedition')[0])
    def test_discovery_and_consent_based_applications(self):
        self.g.command('Alice','create Rockets');self.g.command('Eve','create Trainers')
        self.assertTrue(any('Rockets' in x for x in self.g.command('Bob','list')))
        self.g.command('Bob','apply Rockets');self.g.command('Bob','apply Trainers')
        self.assertIn('Bob',self.g.command('Alice','applications')[0])
        with self.assertRaises(guilds.GuildError):self.g.command('Cara','approve Bob')
        self.g.command('Alice','approve Bob')
        self.assertEqual(self.g.members('Bob'),('Rockets',['Alice','Bob']))
        self.assertEqual(self.g.command('Eve','applications'),['No pending guild applications.'])
        with self.assertRaises(guilds.GuildError):self.g.command('Bob','apply Trainers')
    def test_application_persists_and_leader_can_reject(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'world.db');db=database(path);g=guilds.Guilds(db)
            g.command('Alice','create Rockets');g.command('Bob','apply Rockets');db.close()
            db=sqlite3.connect(path);g=guilds.Guilds(db)
            self.assertIn('Bob',g.command('Alice','applications')[0]);g.command('Alice','reject Bob')
            self.assertEqual(g.command('Alice','applications'),['No pending guild applications.']);db.close()
    def test_persistent_board_access_limits_and_leader_clear(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'world.db');db=database(path);g=guilds.Guilds(db)
            g.command('Alice','create Rockets');g.command('Alice','invite Bob');g.command('Bob','accept Rockets')
            g.command('Alice','post Meet at the gym tomorrow')
            with self.assertRaises(guilds.GuildError):g.command('Eve','board')
            with self.assertRaises(guilds.GuildError):g.command('Bob','clear')
            with self.assertRaises(guilds.GuildError):g.command('Bob','post '+('x'*71))
            db.close();db=sqlite3.connect(path);g=guilds.Guilds(db)
            self.assertEqual(g.command('Bob','board'),['Alice: Meet at the gym tomorrow'])
            for i in range(25):g.command('Bob',f'post Message {i}')
            count=db.execute('SELECT COUNT(*) FROM guild_posts').fetchone()[0]
            self.assertEqual(count,20);self.assertEqual(len(g.command('Bob','board')),8)
            g.command('Alice','clear');self.assertEqual(g.command('Bob','board'),['Guild board is empty.']);db.close()
    def test_meetup_requires_simultaneous_current_members_and_finishes_once(self):
        self.g.command('Alice','create Rockets');self.g.command('Alice','invite Bob');self.g.command('Bob','accept Rockets')
        self.g.command('Alice','meet start Route101 2')
        self.assertIsNone(self.g.complete_meet('Alice','Route101',['Alice','Eve']))
        self.assertIsNone(self.g.complete_meet('Alice','Other',['Alice','Bob']))
        self.assertEqual(self.g.complete_meet('Bob','Route101',['Alice','Bob']),('Rockets','Route101',2,['Alice','Bob']))
        self.assertIsNone(self.g.complete_meet('Bob','Route101',['Alice','Bob']))
        self.assertIn('complete',self.g.command('Alice','meet')[0])
        self.assertIn('15 guild XP',self.g.command('Alice','info')[1])
        self.assertTrue(any('Rockets: level 1, 15 guild XP' in x for x in self.g.command('Eve','standings')))
    def test_expedition_survives_restart_with_member_progress(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'world.db');db=database(path);catalog={(0,9):{'name':'Route101'}};g=guilds.Guilds(db,catalog)
            g.command('Alice','create Rockets');g.command('Alice','invite Bob');g.command('Bob','accept Rockets')
            g.command('Alice','expedition start Route101 2');g.visit('Alice','Route101');db.close()
            db=sqlite3.connect(path);g=guilds.Guilds(db,catalog)
            self.assertIn('1/2',g.command('Bob','expedition')[0]);self.assertIsNotNone(g.visit('Bob','Route101'));db.close()
            db=sqlite3.connect(path);g=guilds.Guilds(db,catalog);self.assertIn('complete',g.command('Alice','expedition')[0]);self.assertIn('10 guild XP',g.command('Alice','info')[1]);db.close()
    def test_membership_survives_database_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/'world.db');db=database(p);g=guilds.Guilds(db)
            g.command('Alice','create Rockets');g.command('Alice','invite Bob');db.close()
            db=sqlite3.connect(p);g=guilds.Guilds(db);g.command('Bob','accept Rockets')
            db.close();db=sqlite3.connect(p);g=guilds.Guilds(db)
            self.assertEqual(g.members('Bob'),('Rockets',['Alice','Bob']));db.close()

class ChatIntegrationTests(unittest.TestCase):
    def setUp(self):
        # Execute the actual server methods against a fake in-memory authority.
        module=ast.parse((ROOT/'world/server.py').read_text())
        cls=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='WorldServer')
        methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('_line','_line_impl','_chat','_snapshot','_connection_cave')]
        ns={'re':re,'time':time,'bounded':bounded,'ID':re.compile(r'[A-Za-z0-9_-]{1,24}\\Z'), 'GuildError':guilds.GuildError, 'HASH':re.compile(r'[0-9a-fA-F]{16}\Z'), 'PRESENCE_HEARTBEAT_INTERVAL':1, 'TRAVEL_FRESH_SECONDS':3, 'MAX_PEERS':8, 'validate_coords':lambda *args:{'name':'Route101'}}
        ns['ID']=re.compile(r'[A-Za-z0-9_-]{1,24}\Z')
        ns.update(route_private_command=route_private_command,
                  __name__='world.server', __package__='world')
        exec(compile(ast.fix_missing_locations(ast.Module(body=methods,type_ignores=[])),'server.py','exec'),ns)
        class Server:
            _line=ns['_line'];_line_impl=ns['_line_impl'];_chat=ns['_chat'];_snapshot=ns['_snapshot']
            _connection_cave=ns['_connection_cave']
            def _queue(self,conn,msg):conn.setdefault('snapshots',[]).append(msg)
            def _broadcast(self):
                for p in self.peers.values():self._queue(p,self._snapshot(p))
            def _error(self,conn,why):raise AssertionError(why)
            def _event(self,*args):pass
            def _flush_states(self,force=False):pass
            def _link_presence(self):return {}
            def _deliver_links(self,msg):pass
            def _schedule_presence(self,now):pass
        self.db=database();self.s=Server();self.s.db=self.db;self.s.guilds=guilds.Guilds(self.db,{(0,9):{'name':'Route101'}});self.s.lock=threading.RLock();self.s.chat_serial=0;self.s.guild_chat=GuildChat(self.s,lambda *args:{'name':'Route101'},3)
        self.s.combined_regions=False  # Explicit legacy authority, as in WorldServer.__init__.
        self.s.cave_map=None;self.s.wilds_map=None;self.s.shared_cave=None;self.s.pending_states={};self.s.last_presence_broadcast=0
        self.s.landmark_survey=LandmarkSurvey(self.s)
        self.s.revision=1;self.s.tiles=[];self.s.objects=[]
        class Rally:
            def snapshot(self,conn):return []
        self.s.rally=Rally()
        class Links:
            def update_presence(self,presence):return []
        self.s.link_protocol=Links()
        self.s.peers={n:{'id':n,'seq':0,'chat':True,'closing':False,'chat_history':[],'chat_status':'ready','state':None,'social':True,'peer_limit':8} for n in ('Alice','Bob','Eve')}
    def tearDown(self):self.db.close()
    def send(self,name,text,target='*'):
        conn=self.s.peers[name];conn['chat_credit']=4
        raw=f"CHAT {conn['seq']+1} {target} {text.encode().hex()}".encode()
        self.s._line(conn,raw)
    def lines(self,name):return [bytes.fromhex(x[3]).decode() for x in self.s.peers[name]['chat_history']]
    def test_commands_private_and_guild_chat_only_reaches_members(self):
        self.send('Alice','/guild create Rockets');self.send('Alice','/guild invite Bob')
        self.assertTrue(any('invited you' in x for x in self.lines('Bob')))
        self.send('Bob','/guild accept Rockets');self.send('Bob','/g meet at the gym')
        self.assertIn('[Guild] meet at the gym',self.lines('Alice'))
        self.assertIn('[Guild] meet at the gym',self.lines('Bob'))
        self.assertEqual(self.lines('Eve'),[])
        bob_wire=self.s._snapshot(self.s.peers['Bob'])
        eve_wire=self.s._snapshot(self.s.peers['Eve'])
        self.assertIn('CHATMSG ',bob_wire)
        self.assertIn('[Guild] meet at the gym'.encode().hex(),bob_wire)
        self.assertNotIn('[Guild] meet at the gym'.encode().hex(),eve_wire)
        self.assertFalse(any('/guild' in x for x in self.lines('Eve')))
    def test_application_and_approval_notify_only_relevant_players(self):
        self.send('Alice','/guild create Rockets');self.send('Bob','/guild list');self.send('Bob','/guild apply Rockets')
        self.assertTrue(any('Bob applied to Rockets' in x for x in self.lines('Alice')))
        self.assertEqual(self.lines('Eve'),[])
        self.send('Alice','/guild approve Bob')
        self.assertTrue(any('application was accepted' in x for x in self.lines('Bob')))
        self.assertEqual(self.s.guilds.members('Bob'),('Rockets',['Alice','Bob']))
        self.assertEqual(self.lines('Eve'),[])
    def test_guild_online_shows_only_members_and_no_coordinates(self):
        self.send('Alice','/guild create Rockets');self.send('Alice','/guild invite Bob');self.send('Bob','/guild accept Rockets')
        self.s.peers['Bob']['state']=[0,9,5,6,1,7,1];self.s.peers['Bob']['state_time']=time.monotonic()
        self.s.peers['Eve']['state']=[0,9,3,4,1,7,1]
        self.send('Alice','/guild online')
        self.assertIn('Guild: Bob: Route101',self.lines('Alice'))
        self.assertFalse(any('Eve' in x for x in self.lines('Alice')))
        self.assertFalse(any('5,6' in x for x in self.lines('Alice')))
        self.assertEqual(self.lines('Eve'),[])
        self.send('Eve','/guild online')
        self.assertTrue(any('not in a guild' in x for x in self.lines('Eve')))
    def test_board_notifications_and_content_are_guild_private(self):
        self.send('Alice','/guild create Rockets');self.send('Alice','/guild invite Bob');self.send('Bob','/guild accept Rockets')
        self.send('Alice','/guild post Meet me tomorrow')
        self.assertTrue(any('Guild board:' in x for x in self.lines('Bob')))
        self.send('Bob','/guild board')
        self.assertIn('Guild: Alice: Meet me tomorrow',self.lines('Bob'))
        self.assertEqual(self.lines('Eve'),[])
    def test_expedition_can_use_leaders_fresh_current_map(self):
        self.send('Alice','/guild create Rockets')
        self.send('Alice','/guild expedition start here 1')
        self.assertTrue(any('Stand ready' in x for x in self.lines('Alice')))
        conn=self.s.peers['Alice'];conn['state']=[0,9,5,6,1,7,1];conn['state_time']=time.monotonic()
        self.send('Alice','/guild expedition start here 1')
        self.assertTrue(any('Expedition started: 1 trainers visit Route101' in x for x in self.lines('Alice')))
        self.send('Alice','/guild expedition')
        self.assertTrue(any('Route101 0/1' in x for x in self.lines('Alice')))
    def test_field_reports_complete_a_guild_expedition_privately(self):
        self.send('Alice','/guild create Rockets');self.send('Alice','/guild invite Bob');self.send('Bob','/guild accept Rockets')
        self.send('Alice','/guild expedition start Route101 2')
        def visit(name):
            conn=self.s.peers[name]
            raw=f"STATE {conn['seq']+1} 0 9 5 6 1 7 1 {'0'*16} {'0'*16}".encode()
            self.s._line(conn,raw)
        visit('Alice');visit('Alice')
        bob=self.s.peers['Bob']
        busy=f"FIELD {bob['seq']+1} 0 9 5 6 1 7 0 {'0'*16} {'0'*16}".encode()
        self.s._line(bob,busy)
        self.assertFalse(any('expedition complete' in x for x in self.lines('Alice')))
        visit('Bob')
        self.assertTrue(any('expedition complete' in x for x in self.lines('Alice')))
        self.assertTrue(any('expedition complete' in x for x in self.lines('Bob')))
        self.assertEqual(self.lines('Eve'),[])
    def test_meetup_requires_fresh_ready_reports_at_same_time(self):
        self.send('Alice','/guild create Rockets');self.send('Alice','/guild invite Bob');self.send('Bob','/guild accept Rockets')
        def report(name,ready=1):
            conn=self.s.peers[name];kind='STATE' if ready else 'FIELD'
            raw=f"{kind} {conn['seq']+1} 0 9 5 6 1 7 {ready} {'0'*16} {'0'*16}".encode()
            self.s._line(conn,raw)
        report('Alice');self.send('Alice','/guild meet start here 2');report('Alice')
        self.s.peers['Alice']['state_time']=time.monotonic()-10
        self.s.peers['Alice']['guild_last_ready_time']=time.monotonic()-10
        report('Bob')
        self.assertFalse(any('meetup complete' in x for x in self.lines('Bob')))
        report('Alice',1)
        self.assertTrue(any('meetup complete' in x for x in self.lines('Alice')))
        self.assertTrue(any('meetup complete' in x for x in self.lines('Bob')))
        self.assertEqual(self.lines('Eve'),[])
    def test_ordinary_public_chat_unchanged(self):
        self.send('Alice','hello everyone')
        self.assertEqual(self.lines('Bob'),['hello everyone']);self.assertEqual(self.lines('Eve'),['hello everyone'])
    def test_nonmember_gets_private_error(self):
        self.send('Eve','/g hello');self.assertIn('not in a guild',self.lines('Eve')[0]);self.assertEqual(self.lines('Alice'),[])
if __name__=='__main__':unittest.main()
