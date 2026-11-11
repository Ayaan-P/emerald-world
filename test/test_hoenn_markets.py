import importlib.util
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/world/world_market.c').exists() else ROOT/'engines/expansion-native'
pkg=types.ModuleType('market_fixture');pkg.__path__=[str(ROOT/'world')];sys.modules['market_fixture']=pkg
from market_fixture import hoenn_markets as m

class Memory:
 def __init__(self,db):self.db=db;db.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,kind TEXT)')
 def append(self,kind,value):return self.db.execute('INSERT INTO events(kind) VALUES(?)',(kind,)).lastrowid
class Markets(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');self.s=types.SimpleNamespace(db=self.db,memory=Memory(self.db),revision=0)
  self.args=dict(site='SlateportCity_Mart',items='[43, 114]',minutes=10)
 def test_real_catalog_scopes(self):
  for name,pos in m.SITES.items():self.assertEqual(m.catalog_maps()[pos]['name'],name)
  m.configure(self.s,'steven',{},self.args)
  c=dict(presence=dict(state=[9,13,1,1,0,0,1],state_time=time.monotonic()))
  self.assertRegex(m.wire(self.s,c,b'MK GET 1'),r'^MK SHELF 9 13 15 2 43 114\n$')
  c['presence']['state'][1]=12;self.assertEqual(m.wire(self.s,c,b'MK GET 1'),'MK NONE\n')
  c['presence']['state'][1]=13;c['presence']['state_time']-=10;self.assertEqual(m.wire(self.s,c,b'MK GET 1'),'MK NONE\n')
 def test_ownership_close_expiry(self):
  m.configure(self.s,'a',{},self.args)
  with self.assertRaises(ValueError):m.configure(self.s,'b',{},self.args)
  self.db.execute('UPDATE hoenn_market_shelves SET expires=0')
  m.configure(self.s,'b',{},self.args)
  m.configure(self.s,'b',{},dict(self.args,items='[]',minutes=0))
  self.assertEqual(m.catalog(self.s)['active'],[])
 def test_bad_catalogs_no_event(self):
  for items in ['[4]','[43,43]','[true]','{}','[]','[0]']:
   with self.assertRaises(ValueError):m.configure(self.s,'a',{},dict(self.args,items=items))
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)
 def test_restart_and_outer_rollback(self):
  m.configure(self.s,'a',{},self.args);self.db.commit()
  self.db.execute('SAVEPOINT change')
  m.configure(self.s,'a',{},dict(self.args,items='[28]'))
  self.db.execute('ROLLBACK TO change');self.db.execute('RELEASE change')
  with tempfile.TemporaryDirectory() as d:
   copy=sqlite3.connect(d+'/world.db');self.db.backup(copy);copy.close()
   recovered=types.SimpleNamespace(db=sqlite3.connect(d+'/world.db'))
   self.assertEqual(m.catalog(recovered)['active'][0]['items'],[43,114]);recovered.db.close()
 def test_server_requires_authenticated_link_before_dispatch(self):
  source=(ROOT/'world/server.py').read_text();start=source.index('    def _link_line(');end=source.index("        if raw.startswith(b'MK '):",start)
  prefix=source[start:end]
  self.assertIn("self.link_channels.get(conn['id']) is not conn",prefix)
  self.assertIn("self.peers.get(conn['id']) is not conn['presence']",prefix)

class Native(unittest.TestCase):
 def compile_run(self,body,flag=1):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'h.c').write_text(body)
   subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-fsanitize=undefined','-DPORTABLE',f'-DEW_HOENN_MARKETS={flag}','-I'+str(NATIVE/'include'),str(p/'h.c'),str(NATIVE/'src/world/world_market.c'),'-o',str(p/'h')],check=True,capture_output=True)
   subprocess.run([str(p/'h')],check=True,capture_output=True)
 def test_actual_cache_and_visit_copy(self):
  self.compile_run('''#include <assert.h>
#include <string.h>
#include "platform/world_market.h"
static int requests;int LinkTransport_MarketSend(const char*l){assert(!strcmp(l,"MK GET 1\\n"));requests++;return 1;}
int main(void){unsigned short frozen[9],other[9];char *a[]={"MK","SHELF","9","13","1","2","43","114"};
 assert(WorldMarket_Line(8,a));assert(WorldMarket_Snapshot(9,13,frozen)==2);assert(frozen[2]==0);
 assert(!WorldMarket_Snapshot(9,12,other));
 for(int i=0;i<60;i++)WorldMarket_Pump();
 assert(!WorldMarket_Snapshot(9,13,other));assert(frozen[0]==43);assert(requests==1);
 a[7]="43";assert(!WorldMarket_Line(8,a));a[7]="4";assert(!WorldMarket_Line(8,a));
 a[7]="114";assert(WorldMarket_Line(8,a));WorldMarket_Reset();assert(!WorldMarket_Snapshot(9,13,other));assert(frozen[1]==114);
 a[2]="255";assert(!WorldMarket_Line(8,a));a[2]="9";a[4]="16";assert(!WorldMarket_Line(8,a));return 0;}
''')
 def test_disabled(self):
  self.compile_run('''#include <assert.h>
#include "platform/world_market.h"
int LinkTransport_MarketSend(const char*l){(void)l;assert(0);return 0;}
int main(void){unsigned short a[9];char *t[]={"MK","SHELF","9","13","15","1","28"};assert(!WorldMarket_Line(7,t));assert(!WorldMarket_Snapshot(9,13,a));for(int i=0;i<500;i++)WorldMarket_Pump();return 0;}
''',0)
 def test_actual_shop_routing(self):
  import re
  source=(NATIVE/'src/shop.c').read_text()
  def extract(name):
   match=re.search(r'(?:static )?void '+name+r'\([^;]*?\)\n\{',source)
   self.assertIsNotNone(match);start=match.start();i=match.end();depth=1
   while depth:
    if source[i]=='{':depth+=1
    elif source[i]=='}':depth-=1
    i+=1
   return source[start:i]
  body=r'''#include <assert.h>
#include <stddef.h>
#include "platform/world_market.h"
typedef unsigned char u8;typedef unsigned short u16;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define MART_TYPE_NORMAL 0
#define MART_TYPE_DECOR 1
#define MART_TYPE_DECOR2 2
static u16 sVisitingItems[9];static const u16 *sUsualItems,*selected;
static bool8 sVisitingShelf;static int opens,buys,clears;
static struct {struct {int mapGroup,mapNum;} location;} save;
#define gSaveBlock1Ptr (&save)
static void CreateShopMenu(int type){(void)type;opens++;}
static void SetShopItemsForSale(const u16 *p){selected=p;}
static void ClearItemPurchases(void){clears++;}
static void ScriptContext_Enable(void){}
static void SetShopMenuCallback(void (*cb)(void)){assert(cb==ScriptContext_Enable);}
static void Task_StartShopBuy(u8 task){(void)task;buys++;}
int LinkTransport_MarketSend(const char*p){(void)p;return 1;}
''' + '\n'.join(extract(n) for n in ['CreatePokemartMenu','CreateDecorationShop1Menu','CreateDecorationShop2Menu','Task_HandleShopMenuBuy','Task_HandleVisitingStock']) + r'''
int main(void){const u16 usual[]={1,28,0};char *t[]={"MK","SHELF","9","13","15","1","43"};
 save.location.mapGroup=9;save.location.mapNum=13;assert(WorldMarket_Line(7,t));
 CreatePokemartMenu(usual);assert(sVisitingShelf&&selected==usual&&clears==1);
 Task_HandleVisitingStock(0);assert(selected[0]==43&&buys==1);
 WorldMarket_Reset();assert(selected[0]==43); /* admitted visit survives disconnect */
 Task_HandleShopMenuBuy(0);assert(selected==usual&&buys==2);
 CreatePokemartMenu(usual);assert(!sVisitingShelf&&selected==usual);
 assert(WorldMarket_Line(7,t));CreatePokemartMenu(usual);assert(sVisitingShelf);
 CreateDecorationShop1Menu(usual);assert(!sVisitingShelf);
 CreateDecorationShop2Menu(usual);assert(!sVisitingShelf);return 0;}
'''
  self.compile_run(body)
 def test_stock_purchase_path_unchanged(self):
  source=(NATIVE/'src/shop.c').read_text();base=(pathlib.Path(__file__).parent/'fixtures/market_shop_base.c').read_text()
  for name in ['BuyMenuTryMakePurchase','BuyMenuSubtractMoney','BuyMenuConfirmPurchase','BuyMenuPrintPriceInList','Task_BuyHowManyDialogueHandleInput']:
   def function(s):
    import re
    match=re.search(r'static void '+name+r'\([^;]*?\)\n\{',s);self.assertIsNotNone(match)
    start=match.start();i=match.end();depth=1
    while depth:
     if s[i]=='{':depth+=1
     elif s[i]=='}':depth-=1
     i+=1
    return s[start:i]
   self.assertEqual(function(source),function(base),name)
  self.assertIn('sVisitingShelf = WorldMarket_Snapshot',source)
  self.assertIn('if (sVisitingShelf) SetShopItemsForSale(sUsualItems);',source)
  self.assertIn('SetShopItemsForSale(sVisitingItems);',source)
if __name__=='__main__':unittest.main()
