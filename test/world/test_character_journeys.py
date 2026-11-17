"""Actual authority multi-segment journeys and production native playback logic."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib,json,os,tempfile,subprocess,unittest
from pathlib import Path
import test_region_characters as region_fixture
from world.character_actions import action_step,compile_actions
from world.mechanics import Candidate
from world.character_walks import walking

class JourneyTests(unittest.TestCase):
 def setUp(self):
  self.f=region_fixture.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.server;self.revision=self.f.enable_shared_xl();self.peer=self.f.connect_shared_xl(walking=True)
  self.path=[[x,70] for x in range(71,89)]+[[88,71],[88,72]]
  self.action=dict(id='harbor_guide',expected_version=2,evidence=[self.s.memory.history()['events'][-1]['seq']],
      reason='Travel to the next clearing independently',changes={},object=dict(self.f.obj,x=88,y=72),journey=self.path)
  ctx=self.s.inspect();ctx['runtime']=dict(previous_source=self.f.candidate.source)
  source=compile_actions([self.action],ctx);self.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.definition=hashlib.sha256(json.dumps([self.action],sort_keys=True).encode()).hexdigest()
  self.snapshots=[];self.tick(0)
 def tick(self,n):
  self.s.tick=n
  result=action_step([self.action],self.definition,dict(state=self.s.module_state,tiles=[],objects=self.s.objects),self.s._context())
  future=Future();future.set_result((self.candidate,result))
  self.s.job=(future,'tick',None,self.s.interaction_cursor);self.s.next_tick=float('inf');self.s._poll_mechanics()
  self.assertIsNone(self.s.module_error)
  self.snapshots.append(deepcopy(self.s.module_state['world_character_controls']['harbor_guide']['walk']))
 def test_progress_collision_segment_boundaries_completion_and_restart(self):
  legacy=self.f.connect_shared_xl('Legacy')
  for n in range(1,6):self.tick(n)
  control=self.s.module_state['world_character_controls']['harbor_guide']
  self.assertEqual(control['walk']['index'],5)
  self.assertTrue(walking(self.s.module_state,'harbor_guide')) # Segment end is not journey completion.
  self.assertNotIn('harbor_guide',self.s._snapshot(legacy))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_journey_receipts').fetchone()[0],0)
  self.tick(6);self.assertEqual(self.s.objects[0]['x'],76)
  self.f.state(self.peer,*self.s.wilds_map,77,70);self.tick(7);self.assertEqual(self.s.objects[0]['x'],76)
  self.f.state(self.peer,*self.s.wilds_map,70,70)
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.server=self.s
  previous=[self.s.objects[0]['x'],self.s.objects[0]['y']]
  for n in range(8,40):
   self.tick(n);point=[self.s.objects[0]['x'],self.s.objects[0]['y']]
   self.assertLessEqual(abs(point[0]-previous[0])+abs(point[1]-previous[1]),1);previous=point
  self.assertEqual(previous,self.path[-1]);self.assertFalse(walking(self.s.module_state,'harbor_guide'))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_journey_receipts').fetchone()[0],1)
  event=next(e for e in self.s.memory.history()['events'] if e['event']=='character_journey_arrived')
  self.assertEqual((event['revision'],event['steps'],event['destination']),(self.revision,len(self.path)-1,self.path[-1]))
  from world.canonical_cast import decision_evidence
  from world.world_memory import native_place
  self.assertTrue(decision_evidence(event,'canon_steven',dict(places=[],journey_interests=[self.revision])))
  self.assertFalse(decision_evidence(event,'canon_steven',dict(places=[],journey_interests=['0'*64])))
 def test_full_path_is_validated_before_departure(self):
  from world.character_journeys import validate
  after=deepcopy(self.s.module_state);c=after['world_character_controls']['harbor_guide']
  c['journey']['path'][-1]=[0,0]
  with self.assertRaises(ValueError):validate(self.s,self.s.module_state,after,self.s.objects)
  c['journey']['path']=self.path;c['journey']['segment']=10
  with self.assertRaises(ValueError):validate(self.s,self.s.module_state,after,self.s.objects)
 def test_production_native_drains_actual_segment_snapshots(self):
  source=Path(os.environ.get('EW_NATIVE_SOURCE','engines/expansion-native'))/'src/world/world_bridge.c'
  if not source.exists():self.skipTest('exact native source unavailable')
  for n in range(1,30):self.tick(n)
  from test_save_isolation import function
  code="""#include <assert.h>
#include <string.h>
typedef unsigned char u8;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define MAP_OFFSET 7
#define DIR_WEST 1
#define DIR_EAST 2
#define DIR_NORTH 3
#define DIR_SOUTH 4
struct CharacterWalk {char id[25];unsigned index,count,path[6][2];};
struct Peer {struct CharacterWalk walk;unsigned x,y;};
struct Remote {char walkId[25];struct CharacterWalk playingWalk;unsigned walkStep;bool8 walkActive;};
struct ObjectEvent {struct {int x,y;} currentCoords;int facingDirection,heldMovementFinished;};
static unsigned moves,teleports;
static void ObjectEventClearHeldMovementIfActive(struct ObjectEvent *o){o->heldMovementFinished=0;}
static void MoveObjectEventToMapCoords(struct ObjectEvent *o,int x,int y){o->currentCoords.x=x;o->currentCoords.y=y;teleports++;}
static void ObjectEventTurn(struct ObjectEvent *o,int d){o->facingDirection=d;}
static u8 GetWalkNormalMovementAction(u8 d){return d;}
static int ObjectEventSetHeldMovement(struct ObjectEvent *o,u8 d){o->currentCoords.x+=(d==2)-(d==1);o->currentCoords.y+=(d==4)-(d==3);o->heldMovementFinished=0;moves++;return 0;}
""" + function(source.read_text(),'SyncCharacterWalk')
  rows=[]
  for w in self.snapshots:
   points=','.join('{%d,%d}'%tuple(p) for p in w['path'])
   rows.append('{{"%s",%d,%d,{%s}},0,0}'%(w['id'],w['index'],len(w['path']),points))
  code+='\nint main(void){struct Remote r={0};struct ObjectEvent o={{78,77},2,0};struct Peer snapshots[]={'+','.join(rows)+'};\n'
  code+='for(unsigned i=0;i<sizeof(snapshots)/sizeof(snapshots[0]);i++){for(unsigned j=0;j<16;j++){SyncCharacterWalk(&r,&snapshots[i],&o,0);o.heldMovementFinished=1;}}\n'
  code+='assert(o.currentCoords.x==95 && o.currentCoords.y==79);assert(moves==19);assert(teleports==0);return 0;}'
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'check.c').write_text(code)
   subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'check.c'),'-o',str(p/'check')],check=True)
   subprocess.run([str(p/'check')],check=True)
