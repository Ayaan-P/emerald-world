from copy import deepcopy
import unittest,time
import test_procedural_adventures as fixture
adventure=fixture.adventure
from world import actor_runtime as runtime,actor_objects,object_choices
from world.procedural_adventures import catalog
from world.battle_campaigns import command,active
from world.guilds import GuildError


def field_adventure():
    doc=adventure();doc['trainers']=doc['trainers'][1:]
    props=[dict(id='device',gfx=0,text='Choose a field move.'),dict(id='panel',gfx=0,text='An unlit panel.')]
    states={}
    for phase in ('idle','lit','restored'):
        states[phase]=dict(objects={p['id']:dict(dx=0,dy=0,gfx=p['gfx'],text=p['text']) for p in props},on={'device':{'spark':'lit','cool':'restored'}},use={},choices={'device':['spark','cool']},moves={'device':{'spark':[85],'cool':[55]}})
    states['lit']['objects']['panel'].update(dx=1,gfx=1,text='The panel is lit.')
    states['restored']['objects']['panel']['text']='The panel has cooled.'
    doc['mechanisms']=[dict(id='field_device',place=0,props=props,program=dict(initial='idle',states=states))]
    doc['campaign']['entry']='field';doc['campaign']['nodes']=dict(field=dict(expedition=dict(network='field_device',label='Investigate the field device',resolutions=dict(lit=dict(label='Light the panel',next=['battle']),restored=dict(label='Cool the panel',next=[])))),battle=dict(opponent='visitor_1',win=[],loss=[]))
    return doc

class FieldAdventureTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AdventureTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.f.plan=self.plan;self.now=0
    def tick(self):
        self.now+=10
        return runtime.tick(self.s,now=self.now)
    def plan(self,doc=None,name='build'):
        from world import actor_blueprints as blueprints
        import json
        revision=0;draft=name
        def put(path,value):
            nonlocal revision
            op=dict(op='set',path=path,value=value)
            raw=json.dumps([op],separators=(',',':'))
            if len(raw)>700:
                put(path,{} if isinstance(value,dict) else [None]*len(value))
                for k,v in (value.items() if isinstance(value,dict) else enumerate(value)):
                    put(path+'/'+str(k),v)
            else:
                with self.s.db:blueprints.edit(self.s,'harbor_guide',{},dict(id=draft,revision=revision,patch=raw))
                revision+=1
        put('',doc or field_adventure())
        state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1
        c['plan']=dict(id=name,purpose='Create an authored field expedition.',steps=[dict(id='snapshot',tool='world.inspect_blueprint',args=dict(id=draft),after=[]),dict(id='build',tool='world.build_adventure',args=dict(document=dict(result='snapshot',key='document')),after=['snapshot'])])
        self.f.p.f.f.f.f.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertIsNone(self.s.module_error)
        self.assertEqual(self.tick()['status'],'succeeded')
    def build(self,doc=None):
        self.plan(doc);self.assertEqual(self.tick()['status'],'pending');self.f.p.admit();self.assertEqual(self.tick()['status'],'succeeded');return catalog(self.s)[0]
    def nearby(self,client,obj):
        peer=client.sock.conn;cave=self.s._connection_cave(peer)
        x,y=next((obj['x']+dx,obj['y']+dy) for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)) if cave.walkable(obj['x']+dx,obj['y']+dy) and not any(o.get('region_revision')==obj['region_revision'] and (o['x'],o['y'])==(obj['x']+dx,obj['y']+dy) for o in self.s.objects))
        facing={(0,1):1,(0,-1):2,(-1,0):3,(1,0):4}[(obj['x']-x,obj['y']-y)]
        client.send_state(peer['seq']+1,*self.s.cave_map,x,y,facing,7,1,'a'*16,'b'*16)
    def test_real_move_commit_and_shared_branch_witnesses(self):
        entry=self.build();clients=[self.f.p.f.connect(n) for n in ('One','Two')];peers=[c.sock.conn for c in clients]
        for i,(client,peer) in enumerate(zip(clients,peers)):
            peer.update(character_region_capable=True,world_props_capable=True,campaign_run=str(i+1)*32);client.select_region(entry['places'][0]['place_id'])
            self.nearby(client,next(o for o in self.s.objects if o['id']=='device'))
        a,b=peers;command(self.s,a,['share','new_journey']);group=active(self.s,a)[1]['shared'];command(self.s,b,['join',group]);command(self.s,a,['begin'])
        for p in peers:command(self.s,p,['expedition-ready'])
        with self.assertRaises(GuildError):command(self.s,a,['expedition-check','lit'])
        before_x=next(o for o in self.s.objects if o['id']=='panel')['x']
        from world.campaign_board import rows
        self.assertTrue(any('Wayfarer 1' in text for text,_ in rows(self.s,a)))
        object_choices.command(self.s,a,['moves']);token=a['object_moves']['token']
        with self.assertRaises(GuildError):object_choices.command(self.s,a,['move',token,'spark','55'])
        object_choices.command(self.s,a,['moves']);token=a['object_moves']['token']
        object_choices.command(self.s,a,['move',token,'spark','85']);self.f.p.admit();actor_objects.poll_player(self.s)
        self.assertEqual(next(o for o in self.s.objects if o['id']=='panel')['gfx'],1)
        self.assertEqual(next(o for o in self.s.objects if o['id']=='panel')['x'],before_x+1)
        self.assertEqual(self.s.module_state['world_object_network_state']['field_device']['phase'],'lit')
        for p in peers:p['state_time']=time.monotonic();command(self.s,p,['expedition-check','lit'])
        self.assertEqual(active(self.s,a)[1]['choices'],['battle']);self.assertEqual(active(self.s,b)[1]['choices'],['battle'])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_move_intents WHERE seq IS NOT NULL').fetchone()[0],1)
        command(self.s,a,['leave']);self.assertEqual(self.s.module_state['world_object_network_state']['field_device']['phase'],'lit')
    def test_invalid_definition_is_atomic(self):
        for mutation in ('occupied','unknown','initial','cycle'):
            with self.subTest(mutation=mutation):
                doc=field_adventure()
                if mutation=='occupied':doc['mechanisms'][0]['props'][0]['id']='harbor_guide'
                if mutation=='unknown':doc['campaign']['nodes']['field']['expedition']['network']='not_created'
                if mutation=='initial':doc['mechanisms'][0]['program']['states']['idle']['objects']['device']['dx']=1
                if mutation=='cycle':doc['campaign']['nodes']['battle']['win']=['field']
                self.f.plan(doc,name='invalid_'+mutation);self.assertEqual(self.tick()['status'],'blocked');self.assertEqual(catalog(self.s),[])
    def test_restart_and_repeat_preserve_definition(self):
        doc=field_adventure();self.f.plan(doc);self.assertEqual(self.tick()['status'],'pending');self.f.p.admit()
        self.s.close();base=self.f.p.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server;self.f.s=self.s;self.f.p.s=self.s
        self.assertEqual(self.tick()['status'],'succeeded');self.assertTrue(catalog(self.s)[0]['published'])
        self.f.p.f.f.f.f.f.f.server=self.s;self.f.plan(doc,name='repeat');self.assertEqual(self.tick()['status'],'succeeded');self.assertIsNone(self.s.deployment)
    def test_nonbattle_two_place_creation_and_failed_admission_resume(self):
        import json
        doc=field_adventure();doc['trainers']=[]
        second=json.loads(json.dumps(doc['mechanisms'][0]).replace('field_device','second_device').replace('"device"','"device_two"').replace('"panel"','"panel_two"'))
        second['place']=1;doc['mechanisms'].append(second)
        doc['campaign']['nodes']=dict(field=dict(mechanism=dict(network='field_device',phase='lit',label='First device'),next=['second']),second=dict(mechanism=dict(network='second_device',phase='restored',label='Second device'),next=[]))
        self.plan(doc);self.assertEqual(self.tick()['status'],'pending');before=catalog(self.s)
        self.s.deployment=None;self.assertEqual(self.tick()['status'],'blocked');self.assertNotIn('field_device',self.s.module_state.get('world_object_networks',{}))
        self.plan(doc,name='resume');self.assertEqual(self.tick()['status'],'pending');self.f.p.admit();self.assertEqual(self.tick()['status'],'succeeded')
        self.assertEqual(before[0]['places'],catalog(self.s)[0]['places']);self.assertEqual(len(self.s.module_state['world_object_networks']),2)
        self.assertNotIn('visitor_1',self.s.module_state['world_characters'])
    def test_bad_geometry_and_reused_mechanism_preserve_world(self):
        doc=field_adventure();doc['mechanisms'][0]['program']['states']['lit']['objects']['panel']['dx']=30
        self.plan(doc);self.assertEqual(self.tick()['status'],'blocked');self.assertEqual(catalog(self.s),[])
        self.assertNotIn('device',{o['id'] for o in self.s.objects})
        self.plan(field_adventure(),name='valid');self.assertEqual(self.tick()['status'],'pending');self.f.p.admit();self.assertEqual(self.tick()['status'],'succeeded')
        newer=field_adventure();newer['label']='Other';newer['campaign']['id']='different';newer['trainers'][0]['id']='other_trainer';newer['campaign']['nodes']['battle']['opponent']='other_trainer'
        self.plan(newer,name='conflict');self.assertEqual(self.tick()['status'],'blocked');self.assertEqual(len(catalog(self.s)),1)
    def test_campaign_free_places_social_resident_and_shared_play(self):
        from world import returning_places
        from world.npc_conversations import command as speak
        doc=field_adventure();doc.pop('campaign')
        doc['constraints']['places']=3;doc['constraints']['branching']=2
        entry=self.build(doc);self.assertTrue(entry['published']);self.assertIsNone(entry['campaign'])
        self.assertEqual(len(entry['places']),3)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM battle_campaigns').fetchone()[0],0)
        clients=[self.f.p.f.connect(n) for n in ('Player','Visitor')]
        place=entry['places'][0]['place_id']
        for client in clients:
            client.sock.conn.update(character_region_capable=True,world_props_capable=True)
            client.select_region(place)
            returning_places.command(self.s,client.sock.conn,['watch',place])
        a,b=[c.sock.conn for c in clients]
        self.nearby(clients[0],next(o for o in self.s.objects if o['id']=='device'))
        object_choices.command(self.s,a,['moves']);token=a['object_moves']['token']
        object_choices.command(self.s,a,['move',token,'spark','85']);self.f.p.admit();actor_objects.poll_player(self.s)
        self.assertEqual(self.s.module_state['world_object_network_state']['field_device']['phase'],'lit')
        self.assertIsNone(active(self.s,a));self.assertIsNone(active(self.s,b))
        clients[1].select_region(entry['places'][2]['place_id'])
        clients[1].send_state(b['seq']+1,*self.s.cave_map,1,1,1,7,1,'a'*16,'b'*16)
        clients[1].send_state(b['seq']+1,0,9,8,8,1,7,1,'a'*16,'b'*16)
        clients[1].select_region(place)
        self.nearby(clients[1],next(o for o in self.s.objects if o['id']=='device'))
        snapshot=self.s._snapshot(b)
        self.assertIn('REGION_PROP '+entry['places'][0]['revision']+' panel',snapshot)
        self.assertIn('The panel is lit.'.encode().hex(),snapshot)
        self.assertTrue(any('changed appearance' in line or 'moved to tile' in line for line in returning_places.command(self.s,b,['read',place])))
        # Social resident has no compulsory battle/campaign enrollment.
        # Consume already-inspected extended native snapshots; RegionClient only parses the base protocol.
        a['out'].clear()
        clients[0].send_state(a['seq']+1,0,9,8,8,1,7,1,'a'*16,'b'*16)
        clients[0].select_region(entry['places'][1]['place_id'])
        self.nearby(clients[0],next(o for o in self.s.objects if o['id']=='visitor_1'))
        speak(self.s,a,['say-public','visitor_1','Hello there.'])
        self.assertIsNone(a.get('character_pending'));self.assertIsNone(active(self.s,a))
    def test_quiet_network_without_population_restarts_and_repeats(self):
        doc=field_adventure();doc.pop('campaign');doc['trainers']=[];doc['mechanisms']=[]
        self.plan(doc);self.assertEqual(self.tick()['status'],'pending');self.f.p.admit()
        self.s.close();base=self.f.p.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server;self.f.s=self.s;self.f.p.s=self.s
        self.assertEqual(self.tick()['status'],'succeeded');self.assertTrue(catalog(self.s)[0]['published'])
        self.f.p.f.f.f.f.f.f.server=self.s;self.plan(doc,name='repeat_quiet');self.assertEqual(self.tick()['status'],'succeeded')
        self.assertIsNone(self.s.deployment);self.assertEqual(len(catalog(self.s)),1)
    def test_optional_campaign_may_leave_residents_and_mechanisms_unassigned(self):
        doc=field_adventure();doc['trainers']=adventure()['trainers']
        doc['constraints']['places']=3;doc['constraints']['branching']=2
        doc['campaign']['entry']='battle';doc['campaign']['nodes']={'battle':dict(opponent='visitor_1',win=[],loss=[])}
        entry=self.build(doc);self.assertTrue(entry['published']);self.assertEqual(entry['campaign'],'new_journey')
        self.assertIn('visitor_0',self.s.module_state['world_characters'])
        self.assertIn('field_device',self.s.module_state['world_object_networks'])
    def test_campaign_free_invalid_geometry_still_rejected(self):
        doc=field_adventure();doc.pop('campaign')
        doc['mechanisms'][0]['program']['states']['lit']['objects']['panel']['dx']=30
        self.plan(doc);self.assertEqual(self.tick()['status'],'blocked')
        self.assertEqual(catalog(self.s),[]);self.assertNotIn('device',{o['id'] for o in self.s.objects})
    def test_quiet_network_still_validates_projected_geometry(self):
        from unittest.mock import patch
        doc=field_adventure();doc.pop('campaign');doc['trainers']=[];doc['mechanisms']=[]
        self.plan(doc);validate=self.s._validated;seen=[]
        def inspect(result):
            if result['state'].get('world_region_networks'):
                seen.append(True)
                raise ValueError('reject synthetic geometry')
            return validate(result)
        with patch.object(self.s,'_validated',side_effect=inspect):
            self.assertEqual(self.tick()['status'],'blocked')
        self.assertTrue(seen);self.assertEqual(catalog(self.s),[])
