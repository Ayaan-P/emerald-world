"""Opted-in anonymous campaign claim -> independent decision -> optional battle."""
from copy import deepcopy
from concurrent.futures import Future
import hashlib,json,tempfile,unittest
import test_character_companions as fixture
from world import actor_runtime,actor_battle_formats,character_reactions as reactions,trainer_experiences as reports,battle_campaigns
from world.character_actions import compile_actions,action_step
from world.mechanics import Candidate
from world.runtime_gm import IntentQueue

class CampaignFormatTests(unittest.TestCase):
 def test_report_changes_optional_format_not_owned_pokemon_or_normal_story(self):
  f=fixture.CompanionIdentityTests();f.setUp();self.addCleanup(f.doCleanups);s=f.s
  c=deepcopy(f.c);c.update(version=2,campaign_interests=['native:LittlerootTown'])
  self.assertIsNone(f.f.commit({'may':c},f.f.npc));original=deepcopy(c['team'])
  identities=s.db.execute('SELECT * FROM character_companions ORDER BY individual').fetchall()
  p=f.f.peer(role='SOCIALCHAR1CHARPK1OUTBREAK1CONTEST1RENTALS1WORLDTV1CHARFORM1');p['core_active_run']='a'*32
  with tempfile.TemporaryDirectory() as path:
   q=IntentQueue(path)
   try:
    reactions.configure(q,s.inspect(),'may','Choose how anonymous reports inform your next optional challenge; no growth inferred.')
    fetch=lambda query:dict(ok=True,world_id=s.memory.world_id,**s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
    key=next(iter(reports.catalog()))
    with self.assertRaises(ValueError):reports.handle(s,p,'a'*32,key,'2:0:9:1',automatic=True)
    reports.participation(s,p,'a'*32,'on','confirm');seq=reports.handle(s,p,'a'*32,key,'2:0:9:1',automatic=True)['evidence']
    self.assertEqual(len(reactions.observe(q,s.inspect(),fetch)),1)
    item=q.claim();context=s.inspect();context['runtime']=dict(kind='character',observed_event=json.loads(item['result']),previous_source=s.candidate.source)
    prepared=reactions.prepare(context,fetch)
    action=dict(id='may',expected_version=2,evidence=[seq],reason='Try coordinated play, without assuming the reported battle was verified.',changes=dict(plan=dict(id='adapt_format',purpose='Offer an optional different battle format.',steps=[dict(id='format',tool='world.set_battle_format',args=dict(format='doubles'),after=[])])),object=deepcopy(f.f.npc))
    reactions.check_response(dict(character_actions=[action],tests='assert True'),prepared)
    source=compile_actions([action],context);definition=hashlib.sha256(json.dumps([action],sort_keys=True).encode()).hexdigest()
    result=action_step([action],definition,dict(state=s.module_state,tiles=[],objects=s.objects));future=Future();future.set_result((Candidate(source,hashlib.sha256(source.encode()).hexdigest()),result))
    s.job=(future,'deploy',None,s.interaction_cursor);s._poll_mechanics();self.assertIsNone(s.module_error)
    self.assertEqual(actor_runtime.tick(s,now=10)['status'],'succeeded')
   finally:q.close()
  revision,mode=actor_battle_formats.current(s,'may');self.assertEqual(mode,1)
  self.assertNotIn('character_pending',p)
  self.assertEqual(s.module_state['world_characters']['may']['team'],original)
  self.assertEqual(s.db.execute('SELECT * FROM character_companions ORDER BY individual').fetchall(),identities)
  # A separately chosen short campaign still binds the same accepted battle;
  # native result reporting remains private, with no public victory claim.
  with s.db:battle_campaigns.publish(s,'may',{},dict(campaign=json.dumps(dict(id='optional',title='Optional practice',entry='first',nodes=dict(first=dict(opponent='may',win=[],loss=[]))))))
  p['campaign_run']='a'*32;battle_campaigns.command(s,p,['start','optional'])
  wire=f.f.send(p,f'CHARACTER_CHALLENGE 1 may 3 {revision}')
  self.assertTrue(wire.startswith(f'CHARACTER_BATTLE_V4 1 may 3 2 {revision} 1 1 '),wire)
  self.assertEqual(p['character_pending']['campaign_binding'][1],'optional')
  self.assertEqual(p['character_pending']['team'],original)
  with s.db:actor_battle_formats.configure(s,'may',{},dict(format='singles'))
  self.assertEqual(p['character_pending']['battle_format'],1)
  event=next(e for e in s.memory.history()['events'] if e['seq']==seq)
  self.assertIn('client attestation',event['limits'])
