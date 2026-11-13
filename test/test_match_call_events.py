import ast,json,pathlib,sqlite3,subprocess,sys,tempfile,time,types,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/world/world_rematch_event.c').exists() else ROOT/'engines/expansion-native'
pkg=types.ModuleType('rematch_fixture');pkg.__path__=[str(ROOT/'world')];sys.modules['rematch_fixture']=pkg
catalog=types.ModuleType('rematch_fixture.build_catalog');catalog.catalog_maps=lambda:{(0,17):dict(name='Route102'),(0,18):dict(name='Route103')};sys.modules[catalog.__name__]=catalog
from rematch_fixture import route_rematch_events as event

def function(source,name):
 start=source.index(name+'(');start=source.rfind('\n',0,start)+1;pos=source.index('{',start);depth=1;end=pos+1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
class Events(unittest.TestCase):
 def setUp(self):
  db=sqlite3.connect(':memory:');db.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,data TEXT)')
  def append(kind,row):return db.execute('INSERT INTO events(data) VALUES(?)',(json.dumps(dict(row,event=kind)),)).lastrowid
  self.s=types.SimpleNamespace(db=db,memory=types.SimpleNamespace(append=append),revision=0,combined_regions=False)
  self.c=dict(id='a',presence=dict(state=[0,17,1,1,0,0,1],state_time=time.monotonic()))
 def test_real_config_snapshot_ownership_expiry_restart(self):
  with self.s.db:
   event.configure(self.s,'canon_wally',{},dict(route='Route102',minutes=5))
   event.configure(self.s,'canon_rydel',{},dict(route='Route103',minutes=5))
  self.assertEqual(event.wire(self.s,self.c,b'J GET 2'),'J LIST 00111e00121e\n')
  self.assertEqual(event.wire(self.s,self.c,b'J GET 1'),'J MAP 0 17 30\n')
  with self.assertRaises(ValueError):event.configure(self.s,'other',{},dict(route='Route102',minutes=2))
  copy=sqlite3.connect(':memory:');self.s.db.backup(copy);self.s.db=copy
  self.assertIn('00121e',event.wire(self.s,self.c,b'J GET 2'))
  copy.execute('UPDATE route_rematch_events SET expires=0 WHERE route=?',('Route102',));copy.commit()
  self.assertEqual(event.wire(self.s,self.c,b'J GET 1'),'J NONE\n')
  self.assertEqual(event.wire(self.s,self.c,b'J GET 2'),'J LIST 00121e\n')
  self.c['presence']['state_time']=0
  self.assertEqual(event.wire(self.s,self.c,b'J GET 2'),'J NONE\n')
 def test_authenticated_transport_dispatch(self):
  node=next(n for n in ast.walk(ast.parse((ROOT/'world/server.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='_link_line')
  namespace={'__name__':'rematch_fixture.server'};exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual link handler>','exec'),namespace)
  self.c.update(sock='socket');self.s.connections={'socket':self.c};self.s.link_channels={'a':self.c};self.s.peers={'a':self.c['presence']};out=[]
  self.s._queue=lambda c,line:out.append(line);self.s._error=lambda c,e:out.append(e)
  namespace['_link_line'](self.s,self.c,b'J GET 2');self.assertEqual(out,['J NONE\n'])
  self.s.peers['a']={};out.clear();namespace['_link_line'](self.s,self.c,b'J GET 2');self.assertEqual(out,['PRESENCE'])
 def test_native_cache_eligibility_and_default(self):
  source=(NATIVE/'src/battle_setup.c').read_text()
  funcs='\n'.join(function(source,n) for n in ['EligibleWorldRematch','WorldRematchEvent_EntryReady','HasWorldRematchEvent'])
  prefix=r'''
#include <assert.h>
#include <string.h>
#include "platform/world_rematch_event.h"
typedef int bool32;typedef int s32;typedef unsigned short u16;
#define TRUE 1
#define FALSE 0
#define REMATCH_SPECIAL_TRAINER_START 3
#define ITEM_VS_SEEKER 1
#define I_VS_SEEKER_CHARGING 1
struct RematchTrainer {unsigned trainerIds[2],mapGroup,mapNum;};
static struct RematchTrainer gRematchTable[4]={{{1,2},0,17},{{3,4},0,18},{{5,6},0,19},{{7,8},0,20}};
static struct Save {struct {unsigned mapGroup,mapNum;} location;} save,*gSaveBlock1Ptr=&save;
static int forbidden,registered=1,fought=1,badges=1,seeker,kanto;
static int IsRematchForbidden(int id){return forbidden;}
static int TrainerIsMatchCallRegistered(int id){return registered;}
static int HasTrainerBeenFought(int id){return fought;}
static int HasEnoughBadgesForRematch(void){return badges;}
static int CheckBagHasItem(int item,int count){return seeker;}
static int BattleSetup_UsesKantoTutorialRules(void){return kanto;}
static int DoesCurrentMapMatchRematchTrainerMap(int id,const struct RematchTrainer *table,unsigned g,unsigned m){return table[id].mapGroup==g&&table[id].mapNum==m;}
static char sent[40];int LinkTransport_RematchEventSend(const char *s){strcpy(sent,s);return 1;}
'''
  sender=function((NATIVE/'src/world/link_transport.c').read_text(),'LinkTransport_RematchEventSend')
  prefix=prefix.replace('int LinkTransport_RematchEventSend(const char *s){strcpy(sent,s);return 1;}', 'static struct {int ready,session;} sLink={1,0}; static int Queue(const char *s){strcpy(sent,s);return 1;}')
  funcs=sender+'\n'+funcs
  main=r'''
int main(void){
 char *list[]={"J","LIST","00111e001202"};char *map[]={"J","MAP","0","17","30"};
 char *bad[]={"J","LIST","00111e00111e"};char *none[]={"J","NONE"};
 assert(!LinkTransport_RematchEventSend("J GET 3\n"));
 sLink.ready=0;assert(!LinkTransport_RematchEventSend("J GET 1\n"));sLink.ready=1;
 sLink.session=1;assert(!LinkTransport_RematchEventSend("J GET 1\n"));sLink.session=0;
 assert(LinkTransport_RematchEventSend("J GET 2\n")==EW_MATCH_CALL_EVENTS);
 WorldRematchEvent_Reset();WorldRematchEvent_Pump();
 assert(!strcmp(sent,EW_MATCH_CALL_EVENTS?"J GET 2\n":"J GET 1\n"));
 assert(WorldRematchEvent_Line(3,list)==EW_MATCH_CALL_EVENTS);
 if(EW_MATCH_CALL_EVENTS){
  assert(WorldRematchEvent_Active(0,17)&&WorldRematchEvent_Active(0,18));
  assert(WorldRematchEvent_EntryReady(0));assert(!HasWorldRematchEvent(gRematchTable,0));
  save.location.mapNum=17;assert(HasWorldRematchEvent(gRematchTable,0));
  registered=0;assert(!WorldRematchEvent_EntryReady(0));registered=1;
  fought=0;assert(!WorldRematchEvent_EntryReady(0));fought=1;
  badges=0;assert(!WorldRematchEvent_EntryReady(0));badges=1;
  forbidden=1;assert(!WorldRematchEvent_EntryReady(0));forbidden=0;
  seeker=1;assert(!WorldRematchEvent_EntryReady(0));seeker=0;
  kanto=1;assert(!WorldRematchEvent_EntryReady(0));kanto=0;
  assert(!WorldRematchEvent_EntryReady(3));assert(!WorldRematchEvent_EntryReady(999));
  for(int i=0;i<120;i++)WorldRematchEvent_Pump();
  assert(!WorldRematchEvent_Active(0,18)&&WorldRematchEvent_Active(0,17));
  assert(!WorldRematchEvent_Line(3,bad));assert(!WorldRematchEvent_Active(0,17));
 }
 assert(WorldRematchEvent_Line(5,map));assert(WorldRematchEvent_Active(0,17));
 save.location.mapNum=17;assert(HasWorldRematchEvent(gRematchTable,0));
 if(!EW_MATCH_CALL_EVENTS)assert(!WorldRematchEvent_EntryReady(0));
 WorldRematchEvent_Line(2,none);assert(!WorldRematchEvent_Active(0,17));
 WorldRematchEvent_Line(5,map);WorldRematchEvent_Reset();assert(!WorldRematchEvent_Active(0,17));
 return 0;
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'test.c';path.write_text(prefix+funcs+main)
   for mode in [0,1]:
    subprocess.run(['cc','-std=c99','-fsanitize=undefined','-DPORTABLE',f'-DEW_MATCH_CALL_EVENTS={mode}','-I'+str(NATIVE/'include'),str(path),str(NATIVE/'src/world/world_rematch_event.c'),'-o',tmp+'/test'],check=True)
    subprocess.run([tmp+'/test'],check=True)
 def test_native_match_call_consumers(self):
  for name in ['pokenav_match_call_data.c','pokenav_match_call_list.c','pokenav_menu_handler_gfx.c']:
   s=(NATIVE/'src'/name).read_text()
   self.assertIn('WorldRematchEvent_EntryReady',s)
   self.assertEqual(s.count('gSaveBlock1Ptr->trainerRematches['),2) # only macro alternatives, no unreviewed direct consumer
  s=(NATIVE/'src/pokenav_match_call_data.c').read_text()
  self.assertIn('|| WorldRematchEvent_EntryReady(idx)',s)
if __name__=='__main__':unittest.main()
