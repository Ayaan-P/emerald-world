"""Real World chat dispatch and trade-board logic, with no sockets."""
import ast
import re
import sqlite3
import tempfile
import sys
import threading
import time
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from world.guilds import Guilds
from world.guild_chat import GuildChat
from world.trade_board import TradeBoard,TradeBoardError,TTL
from world.trade_chat import TradeChat

def db():
 d=sqlite3.connect(':memory:');d.execute('CREATE TABLE identities(id TEXT PRIMARY KEY)')
 d.executemany('INSERT INTO identities VALUES(?)',[(x,) for x in ('Alice','Bob','Eve')]);d.commit();return d

def bounded(v,lo,hi):
 if not v.isascii() or not v.isdecimal() or len(v)>20:raise ValueError()
 n=int(v)
 if not lo<=n<=hi:raise ValueError()
 return n

class BoardTests(unittest.TestCase):
 def setUp(self):self.now=1000000;self.db=db();self.board=TradeBoard(self.db,lambda:self.now)
 def tearDown(self):self.db.close()
 def test_offer_list_remove_and_no_implicit_trade(self):
  self.assertIn('Posted listing 1',self.board.command('Alice','offer Treecko for Torchic')[0])
  self.assertTrue(any('Alice: Treecko for Torchic' in x for x in self.board.command('Bob','list')))
  with self.assertRaises(TradeBoardError):self.board.command('Alice','offer another')
  self.assertEqual(self.board.owner(1),'Alice')
  self.assertEqual(self.board.command('Alice','remove'),['Listing removed.'])
  self.assertIsNone(self.board.owner(1))
 def test_expiry_and_validation(self):
  with self.assertRaises(TradeBoardError):self.board.command('Alice','offer '+('x'*61))
  with self.assertRaises(TradeBoardError):self.board.command('Alice','contact 0')
  self.board.command('Alice','offer Egg for item');self.now+=TTL
  self.assertEqual(self.board.command('Bob','list')[-1],'No active listings.')
  self.assertIsNone(self.board.owner(1))
  self.assertIn('Posted listing 2',self.board.command('Alice','offer another')[0])
 def test_listing_survives_restart_and_expires(self):
  with tempfile.TemporaryDirectory() as d:
   path=str(Path(d)/'board.db');store=sqlite3.connect(path);b=TradeBoard(store,lambda:self.now)
   b.command('Alice','offer Torchic for Treecko');store.close()
   store=sqlite3.connect(path);b=TradeBoard(store,lambda:self.now)
   self.assertTrue(any('Torchic for Treecko' in x for x in b.command('Bob','list')))
   self.now+=TTL;self.assertEqual(b.command('Bob','list')[-1],'No active listings.');store.close()
 def test_one_listing_per_trainer_and_cannot_contact_self(self):
  self.board.command('Alice','offer Gible for Torchic')
  with self.assertRaises(TradeBoardError):self.board.command('Alice','contact 1')
  with self.assertRaises(TradeBoardError):self.board.command('Bob','contact 999')
  self.assertIn('Alice',self.board.command('Bob','contact 1')[0])

class ChatTests(unittest.TestCase):
 def setUp(self):
  module=ast.parse((ROOT/'world/server.py').read_text());cls=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='WorldServer')
  methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('_line','_chat','_snapshot')]
  ns={'re':re,'time':time,'bounded':bounded,'ID':re.compile(r'[A-Za-z0-9_-]{1,24}\Z'),'MAX_PEERS':8}
  exec(compile(ast.fix_missing_locations(ast.Module(body=methods,type_ignores=[])),'server.py','exec'),ns)
  class Server:
   _line=ns['_line'];_chat=ns['_chat'];_snapshot=ns['_snapshot']
   def _queue(self,conn,msg):conn.setdefault('snapshots',[]).append(msg)
   def _broadcast(self):
    for p in self.peers.values():self._queue(p,self._snapshot(p))
   def _error(self,conn,why):raise AssertionError(why)
  self.db=db();self.s=Server();self.s.db=self.db;self.s.lock=threading.RLock();self.s.chat_serial=0
  self.s.guilds=Guilds(self.db);self.s.guild_chat=GuildChat(self.s,lambda *x:{'name':'Route101'},3)
  self.s.trade_board=TradeBoard(self.db);self.s.trade_chat=TradeChat(self.s)
  self.s.cave_map=None;self.s.wilds_map=None;self.s.shared_cave=None;self.s.revision=1;self.s.tiles=[];self.s.objects=[]
  class Rally:
   def snapshot(self,conn):return []
  self.s.rally=Rally()
  self.s.peers={n:{'id':n,'seq':0,'chat':True,'closing':False,'chat_history':[],'chat_status':'ready','state':None,'social':True,'peer_limit':8} for n in ('Alice','Bob','Eve')}
 def tearDown(self):self.db.close()
 def send(self,name,text):
  c=self.s.peers[name];c['chat_credit']=4;self.s._line(c,f"CHAT {c['seq']+1} * {text.encode().hex()}".encode())
 def lines(self,name):return [bytes.fromhex(x[3]).decode() for x in self.s.peers[name]['chat_history']]
 def test_contact_is_private_and_does_not_initiate_trade(self):
  self.send('Alice','/trade offer Treecko for Torchic');self.send('Bob','/trade list')
  self.assertTrue(any('Treecko for Torchic' in x for x in self.lines('Bob')))
  self.send('Bob','/trade contact 1')
  self.assertTrue(any('Bob is interested in listing 1' in x for x in self.lines('Alice')))
  self.assertTrue(any('Request queued for Alice' in x for x in self.lines('Bob')))
  self.assertEqual(self.lines('Eve'),[])
  self.assertNotIn('interested'.encode().hex(),self.s._snapshot(self.s.peers['Eve']))
  self.assertEqual(self.s.trade_board.owner(1),'Alice')
 def test_offline_contact_and_normal_chat(self):
  self.send('Alice','/trade offer Eevee');self.s.peers['Alice']['closing']=True
  self.send('Bob','/trade contact 1');self.assertTrue(any('offline' in x for x in self.lines('Bob')))
  self.send('Bob','hello');self.assertEqual(self.lines('Eve'),['hello'])
if __name__=='__main__':unittest.main()
