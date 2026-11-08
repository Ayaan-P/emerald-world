"""Immutable place-scoped characters through real authority authentication and commits."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import unittest
import test_region_admission as region_fixture
from world.mechanics import Candidate, validate_objects
from world.region_characters import validate_region_objects


class RegionCharacterTests(unittest.TestCase):
    def setUp(self):
        self.f=region_fixture.RegionAdmissionTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.server=self.f.server
        self.obj=dict(id='harbor_guide',group=self.server.cave_map[0],num=self.server.cave_map[1],x=3,y=3,gfx=8,
                      text='Welcome to Harbor.',region_revision=self.f.a)
        self.character=dict(version=1,name='Harbor Guide',role='A persistent harbor researcher',goals=['Study Harbor'],
            relationships={},team=[dict(species=278,level=18)],status='active',object_id='harbor_guide',
            offer=dict(id='harbor_trip',revision=1,kind='expedition',place_id='native:LittlerootTown',target=1),
            evidence=[],reason='Agent assigns a researcher to the opened Harbor region')
        self.source="def update(context,state):\n return {'state':state,'tiles':[],'objects':[]}\n"
        self.candidate=Candidate(self.source,hashlib.sha256(self.source.encode()).hexdigest())
        self.commit(dict(state={'world_characters':{'harbor_guide':self.character}},tiles=[],objects=[self.obj]))
        self.assertIsNone(self.server.module_error)

    def commit(self,result):
        future=Future();future.set_result((self.candidate,result));self.server.job=(future,'tick',None,self.server.interaction_cursor)
        self.server.next_tick=float('inf');self.server._poll_mechanics()

    def send(self,conn,line):
        conn['out'].clear();self.server._line(conn,line.encode());return conn['out'].decode()

    def connect(self,name,place,revision,capable=True):
        token=self.server.create_identity(name)['token']
        conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        role='SOCIALCAVEREGION1CHAR1CHARQUEST1'+('CHARREG1' if capable else '')
        self.assertIn('WELCOME',self.send(conn,f'HELLO 1 {name} {token} {role}'))
        self.state(conn,0,9,8,8)
        self.assertIn('SELECTED',self.send(conn,'REGION SELECT '+place))
        self.assertIn('CAVE BEGIN',self.send(conn,'CAVE GET'))
        self.assertIn('CAVE OK',self.send(conn,'CAVE ACK '+revision))
        self.assertNotIn('REGION_OBJECT',self.server._snapshot(conn))
        self.state(conn,*self.server.cave_map,2,3)
        return conn

    def state(self,conn,group,num,x,y):
        out=self.send(conn,f'STATE {conn["seq"]+1} {group} {num} {x} {y} 4 7 1 '+'a'*16+' '+'b'*16)
        self.assertFalse(conn['closing'],out)

    def test_same_map_coordinates_isolate_places_and_native_requests(self):
        alice=self.connect('Alice',self.f.ra['place_id'],self.f.a)
        bob=self.connect('Bob',self.f.rb['place_id'],self.f.b)
        legacy=self.connect('Legacy',self.f.ra['place_id'],self.f.a,False)
        self.assertIn('REGION_OBJECT '+self.f.a+' harbor_guide',self.server._snapshot(alice))
        self.assertNotIn('harbor_guide',self.server._snapshot(bob))
        self.assertNotIn('harbor_guide',self.server._snapshot(legacy))
        def challenge(conn,region=None):
            suffix=' '+region if region else ''
            command='CHARACTER_CHALLENGE_REGION' if region else 'CHARACTER_CHALLENGE'
            return self.send(conn,f'{command} {conn["seq"]+1} harbor_guide 1'+suffix)
        self.assertIn('CHARACTER_REJECT',challenge(alice))
        self.assertIn('CHARACTER_REJECT',challenge(alice,self.f.b))
        self.assertIn('CHARACTER_REJECT',challenge(bob,self.f.a))
        self.assertIn('CHARACTER_REJECT',challenge(legacy,self.f.a))
        self.assertIn('harbor_guide 1 1 278 18',challenge(alice,self.f.a))
        self.assertEqual(self.server.module_state['world_characters']['harbor_guide']['version'],1)
        events=self.server.memory.history()['events']
        change=next(e for e in events if e['event']=='character_changed')
        self.assertEqual(change['places'],[self.f.ra['place_id']])
        self.server.close();self.f.server=self.f.open();self.server=self.f.server
        self.assertEqual(self.server.objects,[self.obj])

    def test_explicit_region_offer_preserves_guild_consent_and_scope(self):
        alice=self.connect('Alice',self.f.ra['place_id'],self.f.a)
        self.server.guilds.command('Alice','create Harbor')
        def accept(revision):
            return self.send(alice,f'CHARACTER_ACCEPT_REGION {alice["seq"]+1} harbor_guide 1 harbor_trip 1 {revision}')
        self.assertIn('UNAVAILABLE',accept(self.f.b))
        self.assertIn('PRIVATE',accept(self.f.a))
        self.server.guilds.command('Alice','chronicle on')
        self.assertIn('STARTED',accept(self.f.a))
        self.assertEqual(self.server.db.execute('SELECT map_name,goal FROM guild_expeditions').fetchone(),('LittlerootTown',1))
        self.assertIn('ALREADY',accept(self.f.a))

    def test_invalid_geometry_and_unopened_revision_cannot_commit(self):
        before=deepcopy(self.server.module_state)
        for patch in ({'region_revision':'a'*64},{'x':0},{'x':1,'y':1}):
            obj=dict(self.obj,**patch)
            with self.assertRaises(ValueError):validate_region_objects(self.server,[obj],before)
        obj=deepcopy(self.obj);obj.pop('region_revision')
        with self.assertRaises(ValueError):validate_objects([obj])
        obj=dict(self.obj,group=0,num=9)
        with self.assertRaises(ValueError):validate_objects([obj])
        failed=dict(self.obj,region_revision='a'*64)
        self.commit(dict(state=before,tiles=[],objects=[failed]))
        self.assertIsNotNone(self.server.module_error)
        self.assertEqual(self.server.objects,[self.obj]);self.assertEqual(self.server.module_state,before)

    def test_region_interaction_records_only_matching_scope(self):
        alice=self.connect('Alice',self.f.ra['place_id'],self.f.a)
        response=self.send(alice,f'INTERACT_REGION {alice["seq"]+1} harbor_guide {self.f.a}')
        self.assertFalse(alice['closing'],response)
        row=self.server.db.execute("SELECT data FROM events WHERE kind='interaction' ORDER BY seq DESC LIMIT 1").fetchone()
        self.assertIsNotNone(row)


if __name__=='__main__':unittest.main()
