import ast,json,pathlib,sqlite3,subprocess,sys,tempfile,time,types,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];NATIVE=ROOT if (ROOT/'src/world/world_map_offers.c').exists() else ROOT/'engines/expansion-native'
pkg=types.ModuleType('map_fixture');pkg.__path__=[str(ROOT/'world')];sys.modules[pkg.__name__]=pkg
catalog=types.ModuleType('map_fixture.build_catalog');catalog.catalog_maps=lambda:{(0,17):{'name':'Route102'},(0,2):{'name':'MauvilleCity'}};sys.modules[catalog.__name__]=catalog
shops=types.ModuleType('map_fixture.actor_shops');shops.ITEMS={28:'Potion'};sys.modules[shops.__name__]=shops
from map_fixture import map_opportunities as offers

def function(source,name):
 start=source.index(name+'(');start=source.rfind('\n',0,start)+1;pos=source.index('{',start);end=pos+1;depth=1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
class Offers(unittest.TestCase):
 def setUp(self):
  db=sqlite3.connect(':memory:');db.executescript('CREATE TABLE shared_outbreaks(map TEXT,species TEXT,level INTEGER,chance INTEGER,expires REAL);CREATE TABLE shared_fishing(map TEXT,population TEXT,expires REAL);CREATE TABLE hoenn_market_shelves(site TEXT,items TEXT,expires REAL);')
  self.s=types.SimpleNamespace(db=db,combined_regions=False);self.c=dict(id='private',presence=dict(state=[0,17,1,1,0,0,0],state_time=time.monotonic(),outbreak_capable=True,fishing_capable=True))
  db.execute('INSERT INTO shared_outbreaks VALUES(?,?,?,?,?)',('Route102','RALTS',5,10,time.time()+60));db.execute('INSERT INTO hoenn_market_shelves VALUES(?,?,?)',('MauvilleCity_Mart','[28]',time.time()+60));db.commit()
 def page(self,key='Route102',page=1,features=7):
  wire=offers.wire(self.s,self.c,f'WM GET {key} {page} 1 {features}'.encode());f=wire.split();return f,bytes.fromhex(f[-1]).decode().split('|') if f[1]=='PAGE' else []
 def test_public_projection_not_sightings_or_private_state(self):
  before=list(self.s.db.iterdump());fields,lines=self.page();self.assertEqual(lines,['Land encounter','RALTS','Lv 5 10 pct','Saved rules win']);self.assertNotIn('private',str(lines));self.assertLessEqual(int(fields[5]),5)
  self.assertEqual(before,list(self.s.db.iterdump()))
  _,lines=self.page('MauvilleCity');self.assertEqual(lines[1],'Potion');self.assertIn('Buy at town mart',lines)
 def test_fishing_pages_native_weights_and_scope(self):
  data={rod:[['MAGIKARP',5,10] for _ in range(n)] for rod,n in [('old',2),('good',3),('super',5)]}
  self.s.db.execute('INSERT INTO shared_fishing VALUES(?,?,?)',('Route102',json.dumps(data),time.time()+60));self.s.db.commit()
  _,lines=self.page(page=2);self.assertEqual(lines[:3],['Old rod 1','MAGIKARP','Lv 5-10 70 pct'])
  self.c['presence']['outbreak_capable']=False;self.c['presence']['fishing_capable']=False
  _,lines=self.page();self.assertIn('No active offers',lines)
  self.assertEqual(offers.wire(self.s,self.c,b'WM GET SecretBase 0 1 7'),'WM NONE 1\n')
 def test_expiry_stale_presence_and_empty_source(self):
  self.s.db.execute('UPDATE shared_outbreaks SET expires=0');self.s.db.commit();_,lines=self.page();self.assertIn('No active offers',lines)
  self.c['presence']['state_time']=0;self.assertEqual(self.page()[0][:2],['WM','NONE'])
 def test_actual_authenticated_dispatch(self):
  node=next(n for n in ast.walk(ast.parse((ROOT/'world/server.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='_link_line')
  ns={'__name__':'map_fixture.server','__package__':'map_fixture'};exec(compile(ast.Module(body=[node],type_ignores=[]),'server','exec'),ns)
  self.c['sock']='s';self.s.connections={'s':self.c};self.s.link_channels={'private':self.c};self.s.peers={'private':self.c['presence']};out=[];self.s._queue=lambda c,s:out.append(s);self.s._error=lambda c,e:out.append(e)
  ns['_link_line'](self.s,self.c,b'WM GET Route102 1 1 7');self.assertTrue(out[0].startswith('WM PAGE'))
  out.clear();self.s.peers['private']={};ns['_link_line'](self.s,self.c,b'WM GET Route102 1 1 7');self.assertEqual(out,['PRESENCE'])
 def test_compiled_cache_and_actual_sender(self):
  sender=function((NATIVE/'src/world/link_transport.c').read_text(),'LinkTransport_MapOffersSend')
  main=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "platform/world_map_offers.h"
static struct {int ready,session;} sLink={1,0};static char sent[100];static unsigned calls;
static int Queue(const char *line){strcpy(sent,line);calls++;return 1;}
SENDER
int main(void){
 WorldMapOffers_Reset();WorldMapOffers_Select("Route102",3);
 if(!EW_MAP_OFFERS){assert(calls==0);assert(!LinkTransport_MapOffersSend("WM GET Route102 0 1 3\n"));return 0;}
 assert(strstr(sent,"WM GET Route102 0 1 3"));
 char *reply[]={"WM","PAGE","1","0","2","5","417c427c437c44"};
 assert(WorldMapOffers_Line(7,reply));assert(!strcmp(WorldMapOffers_Text(0),"A"));assert(!WorldMapOffers_Line(7,reply));
 WorldMapOffers_Select("Route103",3);assert(!WorldMapOffers_Line(7,reply));assert(strcmp(WorldMapOffers_Text(0),"A"));
 reply[2]="2";assert(WorldMapOffers_Line(7,reply));
 for(int i=0;i<300;i++)WorldMapOffers_Pump();assert(!strcmp(WorldMapOffers_Text(1),"unavailable"));
 WorldMapOffers_Select(NULL,0);WorldMapOffers_Dirty();WorldMapOffers_Select(NULL,0);assert(!WorldMapOffers_Dirty());
 sLink.session=1;assert(!LinkTransport_MapOffersSend("WM GET Route102 0 99 3\n"));sLink.session=0;sLink.ready=0;assert(!LinkTransport_MapOffersSend("WM GET Route102 0 99 3\n"));
 return 0;}
'''.replace('SENDER',sender)
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'main.c';path.write_text(main)
   for mode in (0,1):
    subprocess.run(['cc','-std=c99','-fsanitize=undefined','-DPORTABLE',f'-DEW_MAP_OFFERS={mode}','-I'+str(NATIVE/'include'),str(path),str(NATIVE/'src/world/world_map_offers.c'),'-o',tmp+'/test'],check=True);subprocess.run([tmp+'/test'],check=True)
 def test_navigation_and_render_source_guards(self):
  src=(NATIVE/'src/pokenav_region_map.c').read_text();self.assertIn('if(DrawWorldOffers(state,regionMap))return;',src)
  self.assertIn('GetStringWidth(FONT_NARROW,dest,0)>96',src)
  self.assertIn('return POKENAV_MAP_FUNC_FLY',src);self.assertIn('return POKENAV_MAP_FUNC_ZOOM_IN',src);self.assertIn('return POKENAV_MAP_FUNC_EXIT',src)
  self.assertIn('WorldMapOffers_Reset();',src)
if __name__=='__main__':unittest.main()
