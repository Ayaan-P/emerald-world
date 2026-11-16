"""Explicit native offer acceptance -> real generated-place visits -> character change."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
import unittest
import test_guild_world_memory as guild_fixture
from test_character_chapters import plan
from world.character_chapters import validate_plan,compile_plan,chapter_step
from world.mechanics import Candidate
from world.characters import validate_offer


class CharacterPlaceOfferTests(unittest.TestCase):
    def setUp(self):
        self.f=guild_fixture.GuildWorldMemoryTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.server=self.f.server
        self.blob=b'EWGMAP0A'+(''.join(['#'*127]+['#'+'.'*125+'#']*125+['#'*127])).encode()
        self.revision=self.server._replace_cave(self.blob,label='Research Highlands')
        self.place=self.server.memory.place(self.revision)
        p=plan();p['chapters']=[p['chapters'][0],p['chapters'][2]]
        p['chapters'][0]['offer']=dict(id='highland_trip',revision=1,kind='expedition',place_id=self.place,region_revision=self.revision,target=2)
        p['chapters'][1]['when']=dict(event='guild_goal_completed',character_id=p['id'],character_offer_id='highland_trip',character_offer_revision=1)
        self.plan=validate_plan(p);context=self.server.inspect();self.after=context['world_memory']['through']
        source=compile_plan(p,context);self.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        self.definition=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest();self.tick()
        self.alice=self.peer('Alice');self.bob=self.peer('Bob')

    def tick(self):
        result=chapter_step(self.plan,self.definition,self.after,self.server._context(),dict(state=self.server.module_state,tiles=[],objects=self.server.objects))
        future=Future();future.set_result((self.candidate,result));self.server.job=(future,'tick',None,self.server.interaction_cursor)
        self.server.next_tick=float('inf');self.server._poll_mechanics();self.assertIsNone(self.server.module_error)

    def send(self,conn,line):
        conn['out'].clear();self.server._line(conn,line.encode());self.assertFalse(conn['closing'],conn['out']);return conn['out'].decode()

    def peer(self,name,capable=True,xl=True):
        token=self.server.create_identity(name)['token'];self.server.peers.pop(name,None)
        conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        role='SOCIALTRAVELCHATRALLY'+('CAVE16' if xl else '')+'CHAR1CHARQUEST1'+('PLACEQUEST1' if capable else '')
        self.assertIn('WELCOME',self.send(conn,f'HELLO 1 {name} {token} {role}'))
        self.state(conn,0,9,8,8);self.f.connections[name]=conn;return conn

    def state(self,conn,g,n,x,y):
        return self.send(conn,f'STATE {conn["seq"]+1} {g} {n} {x} {y} 4 7 1 '+'a'*16+' '+'b'*16)

    def accept(self,conn=None):
        conn=conn or self.alice
        return self.send(conn,f'CHARACTER_ACCEPT {conn["seq"]+1} field_researcher 1 highland_trip 1')

    def enter(self,conn):
        self.assertIn('XLWILDS',self.send(conn,'CAVE GET'))
        self.assertIn('CAVE OK',self.send(conn,'CAVE ACK '+self.revision))
        self.state(conn,*self.server.wilds_map,70,70)

    def test_explicit_consent_then_real_visits_drive_character_and_public_history(self):
        snapshot=self.server._snapshot(self.alice)
        expected=f'CHARACTER_PLACE_OFFER field_researcher 1 highland_trip 1 2 {self.place} {self.revision} '+b'Research Highlands'.hex()
        self.assertIn(expected,snapshot);self.assertNotIn('CHARACTER_OFFER field_researcher',snapshot)
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_expeditions').fetchone()[0],0)
        self.assertIn('PRIVATE',self.accept());self.assertEqual(self.f.events(),[])
        self.f.command('chronicle on')
        self.assertIn('LEADER',self.accept(self.bob));self.assertIn('STARTED',self.accept())
        self.assertEqual(self.server.db.execute('SELECT place_id,revision FROM guild_expedition_places').fetchone(),(self.place,self.revision))
        self.assertEqual(self.f.stats(),(0,0,0));self.assertIn('ALREADY',self.accept())
        self.enter(self.alice);self.tick();self.assertEqual(self.server.module_state['world_characters']['field_researcher']['version'],1)
        self.enter(self.bob);event=self.f.events()[0]
        self.assertEqual((event['place_id'],event['region_revision']),(self.place,self.revision))
        self.assertEqual(event['character_offer_id'],'highland_trip');self.assertEqual(self.f.stats(),(10,1,0))
        self.tick();character=self.server.module_state['world_characters']['field_researcher']
        self.assertEqual(character['evidence'],[event['seq']]);self.assertEqual(character['team'],[dict(species=278,level=18)])
        self.assertNotIn('offer',character)
        self.state(self.alice,*self.server.wilds_map,70,70);self.state(self.bob,*self.server.wilds_map,70,70)
        self.assertEqual(len(self.f.events()),1);self.assertEqual(self.f.stats(),(10,1,0))

    def test_missing_capability_or_inactive_destination_never_advertises_or_starts(self):
        self.f.command('chronicle on')
        old=self.peer('Alice',capable=False)
        self.assertNotIn('CHARACTER_PLACE_OFFER',self.server._snapshot(old));self.assertIn('UNAVAILABLE',self.accept(old))
        noxl=self.peer('Alice',xl=False)
        self.assertNotIn('CHARACTER_PLACE_OFFER',self.server._snapshot(noxl));self.assertIn('UNAVAILABLE',self.accept(noxl))
        self.alice=self.peer('Alice')
        other=bytearray(self.blob);other[8+10*127+10]=ord('#');self.server._replace_cave(bytes(other))
        self.assertNotIn('CHARACTER_PLACE_OFFER',self.server._snapshot(self.alice));self.assertIn('UNAVAILABLE',self.accept())
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_expeditions').fetchone()[0],0)

    def test_destination_binding_failure_rolls_back_goal_and_receipt(self):
        self.f.command('chronicle on')
        self.server.db.execute("CREATE TEMP TRIGGER refuse_place BEFORE INSERT ON guild_expedition_places BEGIN SELECT RAISE(ABORT,'fixture rejects destination'); END")
        self.assertIn('REFUSED',self.accept())
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_expeditions').fetchone()[0],0)
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_character_offer_receipts').fetchone()[0],0)
        self.assertEqual(self.f.events(),[])
        from world.generated_goals import validate_offer_places
        from world.guilds import GuildError
        invalid=deepcopy(self.server.module_state)
        invalid['world_characters']['field_researcher']['offer']['region_revision']='0'*64
        with self.assertRaises(GuildError):validate_offer_places(self.server,invalid)

    def test_private_completion_stays_private_and_invalid_revision_refuses(self):
        self.f.command('chronicle on');self.assertIn('STARTED',self.accept());self.f.command('chronicle off')
        self.enter(self.alice);self.enter(self.bob);self.assertEqual(self.f.events(),[]);self.tick()
        self.assertEqual(self.server.module_state['world_characters']['field_researcher']['version'],1)
        self.assertEqual(self.f.stats(),(10,1,0))
        invalid=deepcopy(self.plan['chapters'][0]['offer']);invalid.pop('region_revision')
        with self.assertRaises(ValueError):validate_offer(invalid)
        invalid=dict(invalid,place_id='native:LittlerootTown',region_revision=self.revision)
        with self.assertRaises(ValueError):validate_offer(invalid)


if __name__=='__main__':unittest.main()
