from copy import deepcopy
import json,sqlite3,unittest
from unittest.mock import patch
import test_actor_population as fixture
from world import actor_runtime as runtime
from world.procedural_adventures import catalog,encode
from world.battle_campaigns import command,active


def adventure(seed=8):
    return dict(label='Wayfarer',constraints=dict(places=2,rooms=2,loops=0,branching=1,style='rooms',seed=seed,corridor_width=1),
        trainers=[dict(place=i,id='visitor_'+str(i),name='Visitor '+str(i),role='An original explorer.',goals=['Explore.'],team=[dict(species=280,level=8+i)],gfx=7,text='Ready for a battle?') for i in range(2)],
        campaign=dict(id='new_journey',title='An open journey',entry='first',nodes=dict(first=dict(opponent='visitor_0',win=['second'],loss=['second']),second=dict(opponent='visitor_1',win=[],loss=[]))))

class AdventureTests(unittest.TestCase):
    def setUp(self):
        self.p=fixture.PopulationTests();self.p.setUp();self.addCleanup(self.p.doCleanups);self.s=self.p.s
    def plan(self,doc=None,name='build'):
        state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1
        c['plan']=dict(id=name,purpose='Build an explorable authored adventure.',steps=[dict(id='build',tool='world.build_adventure',args=dict(document=encode(doc or adventure())),after=[])])
        self.p.f.f.f.f.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertIsNone(self.s.module_error)
    def build(self,doc=None):
        self.plan(doc);self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.p.admit();self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded');return catalog(self.s)[0]
    def test_places_population_campaign_and_actual_protocol(self):
        old=self.s.shared_cave.identity;entry=self.build();self.assertTrue(entry['published']);self.assertEqual(self.s.shared_cave.identity,old)
        client=self.p.f.connect('Explorer');peer=client.sock.conn
        peer.update(character_capable=True,character_pokemon_capable=True,character_region_capable=True,world_props_capable=True,cave_link_capable=True,campaign_run='a'*32)
        command(self.s,peer,['start','new_journey'])
        from world.campaign_board import rows
        self.assertTrue(any('Wayfarer 1' in text for text,_ in rows(self.s,peer)))
        for i,place in enumerate(entry['places']):
            if i==0:client.select_region(place['place_id'])
            o=next(o for o in self.s.objects if o['id']=='visitor_'+str(i));cave=self.s._connection_cave(peer)
            x,y=next((o['x']+dx,o['y']+dy) for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)) if cave.walkable(o['x']+dx,o['y']+dy) and not any(p.get('region_revision')==place['revision'] and (p['x'],p['y'])==(o['x']+dx,o['y']+dy) for p in self.s.objects))
            facing={(0,1):1,(0,-1):2,(-1,0):3,(1,0):4}[(o['x']-x,o['y']-y)]
            client.send_state(peer['seq']+1,*self.s.cave_map,x,y,facing,7,1,'a'*16,'b'*16)
            self.assertIn('REGION_OBJECT '+place['revision']+' '+o['id'],self.s._snapshot(peer))
            # Use the normal authority native battle transport, not direct stage mutation.
            peer['character_outbox']=[]
            self.s._line(peer,f'CHARACTER_CHALLENGE_REGION {150+i*100} {o["id"]} 1 {place["revision"]}'.encode())
            self.assertIsNotNone(peer.get('character_pending'))
            self.s._line(peer,f'CHARACTER_RESULT {150+i*100} {o["id"]} 1 1'.encode())
            if i==0:
                command(self.s,peer,['choose','second'])
                from world.actor_linked_navigation import graph
                from world.cave_links import interact,line
                edge=next(e for e in graph(self.s) if e['source']==place['revision'])
                gate=next(o for o in self.s.objects if o['id']==edge['object'])
                gx,gy=next((gate['x']+dx,gate['y']+dy) for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)) if cave.walkable(gate['x']+dx,gate['y']+dy))
                client.send_state(peer['seq']+1,*self.s.cave_map,gx,gy,1,7,1,'a'*16,'b'*16)
                self.assertTrue(interact(self.s,peer,gate,70));line(self.s,peer,['LINK','ACCEPT','70']);line(self.s,peer,['LINK','ACK','70',edge['destination']])
                client.send_state(peer['seq']+1,*self.s.cave_map,1,1,1,7,1,'a'*16,'b'*16);line(self.s,peer,['LINK','ARRIVED','70',edge['destination']])
        self.assertEqual(active(self.s,peer)[1]['status'],'complete')
    def test_failed_admission_resumes_exact_places_and_cast(self):
        self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');before=catalog(self.s);self.assertFalse(before[0]['published'])
        self.s.deployment=None;self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
        self.plan(name='resume');self.assertEqual(runtime.tick(self.s,now=22)['status'],'pending');self.p.admit();self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded')
        self.assertEqual(catalog(self.s)[0]['places'],before[0]['places']);self.assertEqual(len(catalog(self.s)),1)
        self.plan(name='repeat');self.assertEqual(runtime.tick(self.s,now=34)['status'],'succeeded');self.assertIsNone(self.s.deployment);self.assertIsNone(runtime.tick(self.s,now=40))
    def test_invalid_campaign_rolls_back_places_population_and_registry(self):
        before=self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0]
        doc=adventure();doc['campaign']['nodes']['second']['win']=['first'];self.plan(doc)
        self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked');self.assertEqual(catalog(self.s),[])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],before);self.assertNotIn('visitor_0',self.s.module_state['world_characters'])
    def test_original_identity_and_capacity_guards(self):
        doc=adventure();doc['trainers'][0]['id']='harbor_guide';doc['campaign']['nodes']['first']['opponent']='harbor_guide';self.plan(doc)
        self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked');self.assertEqual(catalog(self.s),[])
        self.plan(name='capacity')
        with patch.object(self.s,'_validated',side_effect=ValueError('capacity')):
            self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
        self.assertEqual(catalog(self.s),[])
    def test_restart_after_admission_before_campaign_publication(self):
        self.plan();runtime.tick(self.s,now=10);self.p.admit();self.assertFalse(catalog(self.s)[0]['published'])
        self.s.close();base=self.p.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
        self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded');self.assertTrue(catalog(self.s)[0]['published'])
    def test_multiple_seeds_and_organic_layouts(self):
        # Pure compiler placement is also exercised by real admission in independent worlds.
        for seed in (19,31):
            with self.subTest(seed=seed):
                doc=adventure(seed);doc['constraints']['style']='organic';doc['label']='Other';doc['campaign']['id']='journey_'+str(seed)
                for i,t in enumerate(doc['trainers']):t['id']='guest_'+str(seed)+'_'+str(i)
                for i,n in enumerate(doc['campaign']['nodes'].values()):n['opponent']=doc['trainers'][i]['id']
                self.plan(doc,name='seed_'+str(seed));self.assertEqual(runtime.tick(self.s,now=seed*10)['status'],'pending');self.p.admit();self.assertEqual(runtime.tick(self.s,now=seed*10+6)['status'],'succeeded')

    def test_real_adventure_can_include_seeded_wildlife_and_plain_places(self):
        from world.shared_cave import SharedCave
        from world.habitat_composer import compose
        from world.species_cohort import catalogue
        criteria=dict(types=['water','ice'],generations=list(range(1,10)),bst=[200,550],levels=[8,18],seed=42)
        doc=adventure();doc['trainers']=[];doc.pop('campaign');doc['habitats']=[dict(place=0,profile='ice',rate=25,criteria=criteria)]
        entry=self.build(doc);expected=compose(encode(criteria));ids=catalogue('expansion-native')
        blob=self.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(entry['places'][0]['revision'],)).fetchone()[0]
        cave=SharedCave(blob);self.assertEqual(cave.version,10);self.assertEqual(cave.wildlife[0],25)
        for i,(name,level) in enumerate(expected['slots']):
            self.assertEqual(int.from_bytes(cave.wildlife[1+3*i:3+3*i],'little'),ids[name]);self.assertEqual(cave.wildlife[3+3*i],level)
        plain=SharedCave(self.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(entry['places'][1]['revision'],)).fetchone()[0]);self.assertEqual(plain.version,1)
        self.assertIn('CAVE WILD '+cave.identity,cave.frames())
        self.assertTrue(self.s.module_state['world_region_networks'])

    def test_two_clients_enter_composed_habitat_through_real_link_protocol(self):
        from world.actor_linked_navigation import graph
        from world.shared_cave import SharedCave
        criteria=dict(types=['water','ice'],generations=list(range(1,10)),bst=[200,550],levels=[8,18],seed=42)
        doc=adventure();doc['trainers']=[];doc.pop('campaign');doc['habitats']=[dict(place=1,profile='ice',rate=25,criteria=criteria)]
        entry=self.build(doc); source,target=entry['places']; source_cave=SharedCave(self.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(source['revision'],)).fetchone()[0]);wild=SharedCave(self.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(target['revision'],)).fetchone()[0])
        edge=next(e for e in graph(self.s) if e['source']==source['revision'] and e['destination']==target['revision']);gate=next(o for o in self.s.objects if o['id']==edge['object'])
        x,y=next((gate['x']+dx,gate['y']+dy) for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)) if source_cave.walkable(gate['x']+dx,gate['y']+dy))
        facing={(0,1):1,(0,-1):2,(-1,0):3,(1,0):4}[(gate['x']-x,gate['y']-y)]
        def send(conn,command):
            conn['out'].clear();self.s._line(conn,command.encode());return conn['out'].decode()
        def connect(name,modern):
            token=self.s.create_identity(name)['token'];conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
            caps='SOCIALCAVE10REGION1CHAR1CHARQUEST1CHARREG1WORLDOBJ1CAVELINK1'+('CAVELINKW1' if modern else '')
            self.assertIn('WELCOME',send(conn,f'HELLO 1 {name} {token} {caps}'))
            send(conn,'STATE 1 0 9 8 8 1 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb')
            self.assertIn('REGION SELECTED',send(conn,'REGION SELECT '+source['place_id']))
            send(conn,'CAVE GET');self.assertIn('CAVE OK',send(conn,'CAVE ACK '+source['revision']))
            send(conn,f'STATE 2 {self.s.cave_map[0]} {self.s.cave_map[1]} {x} {y} {facing} 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb')
            return conn
        legacy=connect('LegacyX',False);seq=legacy['seq']+1
        self.assertNotIn('LINK OFFER',send(legacy,f'INTERACT_REGION {seq} {gate["id"]} {source["revision"]}'))
        for name in ('QuestA','QuestB'):
            peer=connect(name,True);seq=peer['seq']+1
            self.assertIn('LINK OFFER',send(peer,f'INTERACT_REGION {seq} {gate["id"]} {source["revision"]}'))
            data=send(peer,f'LINK ACCEPT {seq}');self.assertIn(wild.wildlife.hex(),data)
            self.assertIn('LINK COMMIT',send(peer,f'LINK ACK {seq} {wild.identity}'))
            send(peer,f'STATE {seq+1} {self.s.cave_map[0]} {self.s.cave_map[1]} 1 1 1 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb')
            self.assertIn('LINK DONE',send(peer,f'LINK ARRIVED {seq} {wild.identity}'))
            self.assertEqual(self.s._connection_cave(peer).wildlife,wild.wildlife)
        self.assertEqual(legacy['cave_ack'],source['revision'])

    def test_authored_slots_populate_habitat_without_changing_plain_place(self):
        from world.shared_cave import SharedCave
        from world.species_cohort import catalogue
        doc=adventure();doc['trainers']=[];doc.pop('campaign');doc['habitats']=[dict(place=0,profile='granite',rate=17,slots=[['ZUBAT',8]]*12)]
        entry=self.build(doc);blob=self.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(entry['places'][0]['revision'],)).fetchone()[0]
        cave=SharedCave(blob);self.assertEqual(cave.wildlife[0],17);self.assertEqual(int.from_bytes(cave.wildlife[1:3],'little'),catalogue('expansion-native')['ZUBAT']);self.assertEqual(cave.wildlife[3],8)
    def test_malformed_authored_species_rolls_back(self):
        doc=adventure();doc['trainers']=[];doc.pop('campaign');doc['habitats']=[dict(place=0,profile='granite',rate=17,slots=[['NOT_A_POKEMON',8]]*12)]
        before=self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0]
        self.plan(doc);self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked');self.assertEqual(catalog(self.s),[])
        self.assertEqual(before,self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0])

    def test_network_can_combine_named_styles_and_distinct_habitat(self):
        from world.procedural_regions import generate
        doc=adventure();doc['trainers']=[];doc.pop('campaign');doc['place_names']=['Echo Grotto','Moonlit Vault'];doc['constraints']['place_styles']=['maze','organic']
        doc['habitats']=[dict(place=1,profile='ice',rate=25,criteria=dict(types=['water','ice'],generations=list(range(1,10)),bst=[200,550],levels=[8,18],seed=42))]
        layout=generate(doc['label'],encode(doc['constraints']));self.assertEqual([p['blueprint']['style'] for p in layout['places']],['maze','organic'])
        entry=self.build(doc);self.assertEqual([p['label'] for p in entry['places']],doc['place_names'])
        from world.shared_cave import SharedCave
        caves=[SharedCave(self.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(p['revision'],)).fetchone()[0]) for p in entry['places']]
        self.assertEqual([c.version for c in caves],[1,10]);self.assertEqual(caves[1].wildlife[0],25)
    def test_bad_place_styles_fail_without_opening_places(self):
        from world.procedural_regions import generate
        for styles in (['rooms'],['maze','unknown'],['maze',None]):
            doc=adventure();doc['constraints']['place_styles']=styles
            with self.assertRaises(ValueError):generate(doc['label'],encode(doc['constraints']))

    def test_named_places_are_published_and_stable_on_resume(self):
        doc=adventure();doc['trainers']=[];doc.pop('campaign');doc['place_names']=['Echo Grotto','Moonlit Vault']
        entry=self.build(doc);self.assertEqual([p['label'] for p in entry['places']],doc['place_names'])
        for p in entry['places']:
            label=self.s.db.execute('SELECT label FROM generated_area_archive WHERE identity=?',(p['revision'],)).fetchone()[0];self.assertEqual(label,p['label'])
        self.plan(doc,name='repeat_names');self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded');self.assertEqual(catalog(self.s)[0]['places'],entry['places'])
    def test_invalid_place_names_cannot_create_partial_world(self):
        before=self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0]
        for names in (['One'],['Same','same'],['Valid','bad/name'],['a'*21,'Good']):
            doc=adventure();doc['trainers']=[];doc.pop('campaign');doc['place_names']=names
            with self.assertRaises(ValueError):
                from world.procedural_adventures import start
                start(self.s,'harbor_guide',{},dict(document=encode(doc)))
            self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],before)

    def test_invalid_habitat_never_publishes_partial_places(self):
        before=self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0]
        criteria=dict(types=['water'],generations=[1],bst=[200,550],levels=[8,18],seed=42)
        doc=adventure();doc['trainers']=[];doc.pop('campaign');doc['habitats']=[dict(place=0,profile='ice',rate=25,criteria=criteria),dict(place=0,profile='ice',rate=25,criteria=criteria)]
        self.plan(doc);self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked');self.assertEqual(catalog(self.s),[])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],before)

    def test_campaign_conflict_and_actor_change_never_overwritten(self):
        self.plan();runtime.tick(self.s,now=10);self.p.admit()
        from world.battle_campaigns import publish
        with self.s.db:publish(self.s,'another_author',{},dict(campaign=encode(adventure()['campaign'])))
        self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertFalse(catalog(self.s)[0]['published'])
        self.assertEqual(self.s.db.execute("SELECT actor FROM battle_campaigns WHERE id='new_journey'").fetchone()[0],'another_author')
        self.assertIn('visitor_0',self.s.module_state['world_characters'])

    def test_generated_challenge_can_be_declined_without_native_battle(self):
        doc=adventure();doc['campaign']['nodes']['first']['decline']=['second']
        entry=self.build(doc);self.assertTrue(entry['published'])
        client=self.p.f.connect('Explorer');peer=client.sock.conn;peer['campaign_run']='a'*32
        command(self.s,peer,['start','new_journey'])
        command(self.s,peer,['decline-challenge'])
        self.assertEqual(active(self.s,peer)[1]['choices'],['second'])
        self.assertNotIn('outcome',active(self.s,peer)[1]['history'][0])
        self.assertIsNone(peer.get('character_pending'))
        self.assertEqual(len(entry['places']),2)
