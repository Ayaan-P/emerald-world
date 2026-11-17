import json,time,unittest
from copy import deepcopy
import test_procedural_adventures as fixture
from world import returning_places as guide
from world.guilds import GuildError

class ReturningPlacesTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AdventureTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
        entry=self.f.build();self.place=entry['places'][0]['place_id']
        self.a=self.f.p.f.connect('One').sock.conn;self.b=self.f.p.f.connect('Two').sock.conn
    def call(self,peer,*words):return guide.command(self.s,peer,list(words))
    def token(self,peer):return peer['place_guide']['token']
    def last(self,peer):
        while (peer['place_guide']['page']+1)*5<len(peer['place_guide']['rows']):self.call(peer,'next',self.token(peer))
    def test_explicit_private_checkpoints_and_current_actions(self):
        seq=self.s.db.execute('SELECT max(seq) FROM events').fetchone()[0]
        self.call(self.a,'watch',self.place)
        self.assertIn('No private checkpoints',self.call(self.b,'list')[0])
        self.assertEqual(self.s.db.execute('SELECT max(seq) FROM events').fetchone()[0],seq)
        self.call(self.a,'read',self.place);self.assertTrue(any('Optional activity' in r for r in self.a['place_guide']['rows']))
        old=self.s.db.execute('SELECT snapshot FROM player_place_checkpoints').fetchone()[0]
        self.call(self.a,'go',self.token(self.a))
        self.assertEqual(self.a['region_place'],self.place);self.assertEqual(self.s.db.execute('SELECT snapshot FROM player_place_checkpoints').fetchone()[0],old)
        self.assertNotIn('campaign_run',self.a)
    def test_real_catalog_change_and_explicit_review_survive_restart(self):
        self.call(self.a,'watch',self.place)
        from world.actor_shops import configure
        with self.s.db:configure(self.s,'visitor_0',{},dict(items='[28,114]'))
        self.call(self.a,'read',self.place)
        self.assertTrue(any('changed the available shop catalog' in r for r in self.a['place_guide']['rows']))
        self.last(self.a);self.call(self.a,'save',self.token(self.a))
        old=self.s.db.execute('SELECT snapshot FROM player_place_checkpoints').fetchone()[0]
        self.s.close();base=self.f.p.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
        self.assertEqual(self.s.db.execute('SELECT snapshot FROM player_place_checkpoints').fetchone()[0],old)
    def test_stale_tokens_other_player_revocation_and_ordinary_map(self):
        self.call(self.a,'watch',self.place);self.call(self.a,'read',self.place);token=self.token(self.a)
        with self.assertRaises(GuildError):self.call(self.b,'go',token)
        obj=next(o for o in self.s.objects if o['id']=='visitor_0');obj['text']='A new greeting.'
        with self.assertRaises(GuildError):self.call(self.a,'go',token)
        self.call(self.a,'read',self.place);token=self.token(self.a);self.call(self.a,'forget',self.place)
        with self.assertRaises(GuildError):self.call(self.a,'save',token)
        self.call(self.a,'watch','native:LittlerootTown');self.call(self.a,'read','native:LittlerootTown')
        with self.assertRaises(GuildError):self.call(self.a,'go',self.token(self.a))
    def test_pages_stable_and_no_implicit_mark_read(self):
        self.call(self.a,'watch',self.place)
        for o in self.s.objects:
            if o.get('region_revision')==guide.places(self.s)[self.place]['revision']:o['text']='Changed appearance.'
        self.call(self.a,'read',self.place);p=self.a['place_guide'];old=p['before'];token=p['token']
        if len(p['rows'])>5:
            with self.assertRaises(GuildError):self.call(self.a,'save',token)
        self.assertEqual(self.s.db.execute('SELECT snapshot FROM player_place_checkpoints').fetchone()[0],old)
        self.last(self.a);self.call(self.a,'save',token)
        self.call(self.a,'read',self.place);self.assertTrue(any('No tracked content differences' in r for r in self.a['place_guide']['rows']))
    def test_chat_transport_remains_bounded_and_no_public_event(self):
        self.assertTrue(self.s.guild_chat.handle(self.a,'/guild return'))
        self.assertTrue(self.s.guild_chat.handle(self.a,'/guild return places 1'))
        self.assertTrue(all(len(bytes.fromhex(m[3]))<=120 for m in self.a['chat_history']))
        with self.assertRaises(GuildError):self.call(self.a,'watch','not-a-place')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM player_place_checkpoints').fetchone()[0],0)
    def test_existing_native_selection_guards_are_retained(self):
        self.call(self.a,'watch',self.place);self.call(self.a,'read',self.place)
        self.a['in_generated_cave']=True
        with self.assertRaises(GuildError):self.call(self.a,'go',self.token(self.a))
        self.assertIsNone(self.a.get('region_place'))
        self.a['in_generated_cave']=False;self.a['place_guide']['until']=0
        with self.assertRaises(GuildError):self.call(self.a,'go',self.token(self.a))
    def test_capacity_removal_and_stale_checkpoint_fail_closed(self):
        names=list(guide.places(self.s))[:8]
        for place in names:self.call(self.a,'watch',place)
        with self.assertRaises(GuildError):self.call(self.a,'watch',self.place)
        self.call(self.a,'forget',names[0]);self.call(self.a,'watch',self.place);self.call(self.a,'read',self.place)
        token=self.token(self.a)
        with self.s.db:self.s.db.execute('DELETE FROM world_region_revisions WHERE place_id=?',(self.place,))
        with self.assertRaises(GuildError):self.call(self.a,'go',token)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM player_place_checkpoints WHERE trainer=?',(self.a['id'],)).fetchone()[0],8)
        self.call(self.a,'forget',self.place)
    def test_intermediate_reversal_is_not_invented_history(self):
        self.call(self.a,'watch',self.place)
        obj=next(o for o in self.s.objects if o['id']=='visitor_0');old=obj['text'];obj['text']='Temporary';obj['text']=old
        self.call(self.a,'read',self.place)
        self.assertTrue(any('Intermediate changes may have happened' in r for r in self.a['place_guide']['rows']))
    def test_actual_chat_command_keeps_checkpoint_reply_off_other_peer(self):
        for peer in (self.a,self.b):peer.update(chat=True,chat_credit=4,chat_status='ready',social=True)
        other=list(self.b['chat_history']);text='/guild return watch '+self.place
        before=self.s.db.execute('SELECT max(seq) FROM events').fetchone()[0]
        self.s._line(self.a,f"CHAT {self.a['seq']+1} * {text.encode().hex()}".encode())
        self.assertTrue(any('Saved a private checkpoint' in bytes.fromhex(m[3]).decode() for m in self.a['chat_history']))
        self.assertEqual(self.b['chat_history'],other)
        self.assertEqual(self.s.db.execute('SELECT max(seq) FROM events').fetchone()[0],before)
