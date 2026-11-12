"""Independent actors collaborate across original locations, without travel claims."""
import copy,json,tempfile,unittest
import test_canonical_cast as fixture
from test_canonical_world_actions import pack
from world import canonical_cast as cast,canonical_world_actions as actions,character_reactions as reactions
from world.runtime_gm import IntentQueue
from world.build_catalog import catalog_maps

SHOP='MauvilleCity_BikeShop'
HOUSE='MossdeepCity_StevensHouse'

class SharedProjectTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.p=pack();self.p['qualities']['stage']['scope']='project'
  self.p['qualities']['local']={'scope':'place','initial':0,'max':3}
  self.p['scenes']['organize']['place']=SHOP
  self.p['scenes']['organize']['choices']['open']['effects']['local']=1
  self.p['scenes']['contribute']['place']=HOUSE
  self.p['scenes']['contribute']['actors']=['canon_steven']
  self.p['scenes']['solo']['place']=SHOP
  self.p['scenes']['shared']['place']=HOUSE
  self.p['scenes']['shared']['text']='The shared project is ready after both independent contributions.'
  self.f.apply(self.actor('canon_rydel'))
  a=self.actor('canon_steven');a['changes'].update(initiative=self.p,companion='steven_wild_once',
   activity_projects=dict(companion=dict(scene='contribute',requires=dict(stage=[2,2]))))
  self.f.apply(a)
 def actor(self,who,version=0):
  a=self.f.action(version);a['id']=who;a['changes']['places']=['native:LittlerootTown','native:'+SHOP,'native:'+HOUSE];return a
 def schedule(self,who,version,scene,choice,place,revision,evidence):
  a=self.actor(who,version);a['changes'].update(evidence=[evidence],
   world_action=dict(pack='workshop',scene=scene,choice=choice,place=place,revision=revision),
   intentions=[dict(id='collaborate',kind='world_action',target='workshop',reason='Contribute to the shared project from my own normal location.')])
  if who=='canon_steven':
   a['changes'].update(initiative=self.p,companion='steven_wild_once',activity_projects=dict(companion=dict(scene='contribute',requires=dict(stage=[2,2]))))
  return a
 def partner(self):
  peer=self.f.peer();peer['state'][:2]=next(k for k,v in catalog_maps().items() if v['name']==HOUSE)
  cast.response(self.s,peer,'a'*32,'steven')
  return self.s.core_story.handle(peer,['CORE','a'*32,'ALLY','steven','confirm'])
 def test_cross_town_actions_unlock_real_existing_partner_admission(self):
  with self.assertRaises(ValueError):self.partner()
  evidence=cast.records(self.s.module_state)['canon_rydel']['evidence'][0]
  self.f.apply(self.schedule('canon_rydel',1,'organize','open',SHOP,0,evidence))
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_steven','Consider shared projects independently.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.fetch),[])
    first=actions.step(self.s,now=10)
    self.assertEqual(first['actor'],'canon_rydel')
    self.assertEqual(self.s.opportunities.public_state(self.p,SHOP)[1],dict(stage=1,local=1))
    self.assertEqual(self.s.opportunities.public_state(self.p,HOUSE)[1],dict(stage=1,local=0))
    available=self.s.opportunities.actor_actions('canon_steven')
    self.assertEqual(available[0]['revision'],1)
    self.assertEqual(available[0]['place'],HOUSE)
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    item=q.claim();ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    response=self.schedule('canon_steven',1,'contribute','join',HOUSE,1,first['seq'])
    reactions.check_response(dict(canonical_actions=[response],tests='assert True'),reactions.prepare(ctx,self.f.fetch))
    self.f.apply(response)
    self.assertEqual(actions.step(self.s,now=16)['actor'],'canon_steven')
   finally:q.close()
  self.assertTrue(self.partner()['ok'])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
  self.assertEqual(self.s.objects,[])
  self.assertEqual(self.s.opportunities.public_state(self.p,SHOP)[1],dict(stage=2,local=1))
  self.assertEqual(self.s.opportunities.public_state(self.p,HOUSE)[1],dict(stage=2,local=0))
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.s=self.f.f.case.server
  self.assertTrue(self.partner()['ok'])
  self.assertIsNone(actions.step(self.s,now=30))
  # A real player decision changes the same project across both locations.
  self.s.opportunities.choose('Alice',HOUSE,'workshop','shared','consider',2,'reflect')
  with self.assertRaises(ValueError):self.partner()
  self.assertEqual(self.s.opportunities.public_state(self.p,SHOP)[1]['stage'],1)

 def test_cross_location_stale_choices_and_private_state_remain_separate(self):
  with self.s.db:self.s.opportunities.actor_choose('canon_rydel',dict(pack='workshop',scene='organize',choice='open',place=SHOP,revision=0))
  with self.assertRaises(ValueError):
   with self.s.db:self.s.opportunities.actor_choose('canon_steven',dict(pack='workshop',scene='contribute',choice='join',place=HOUSE,revision=0))
  with self.s.db:self.s.opportunities.actor_choose('canon_steven',dict(pack='workshop',scene='contribute',choice='join',place=HOUSE,revision=1))
  with self.assertRaises(ValueError):self.s.opportunities.choose('Bob',SHOP,'workshop','solo','read',1,'stale')
  p=copy.deepcopy(self.p);p['id']='private_mix';p['qualities']['secret']=dict(scope='player',initial=0,max=3)
  p['scenes']['shared']['choices']['consider']['effects']['secret']=1
  self.s.opportunities.publish(p)
  for actor,scene,choice,place,rev in [('canon_rydel','organize','open',SHOP,0),('canon_steven','contribute','join',HOUSE,1)]:
   with self.s.db:self.s.opportunities.actor_choose(actor,dict(pack=p['id'],scene=scene,choice=choice,place=place,revision=rev))
  self.s.opportunities.choose('Alice',HOUSE,p['id'],'shared','consider',2,'choose')
  self.assertEqual(self.s.opportunities._load(p['id'],'Alice',SHOP)[3]['secret'],1)
  self.assertEqual(self.s.opportunities._load(p['id'],'Bob',SHOP)[3]['secret'],0)
  self.assertNotIn('secret',self.s.opportunities.public_state(p,HOUSE)[1])
  self.assertEqual(self.s.opportunities.public_state(self.p,HOUSE)[1]['stage'],2)

 def test_cross_town_commit_rolls_back_as_one_project(self):
  before=self.s.opportunities.public_state(self.p,SHOP)
  with self.assertRaisesRegex(RuntimeError,'abort'):
   with self.s.db:
    self.s.opportunities.actor_choose('canon_rydel',dict(pack='workshop',scene='organize',choice='open',place=SHOP,revision=0))
    self.assertEqual(self.s.opportunities.public_state(self.p,HOUSE)[1]['stage'],1)
    raise RuntimeError('abort')
  self.assertEqual(self.s.opportunities.public_state(self.p,SHOP),before)
  self.assertEqual(self.s.opportunities.public_state(self.p,HOUSE)[1]['stage'],0)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_consequences').fetchone()[0],0)
