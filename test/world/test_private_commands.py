"""Reserved prefixes never become room messages, including old client sessions."""
import json
import test_opportunities as base


class PrivateCommandTests(base.OpportunityTests):
    def legacy(self,name):
        who=self.s.create_identity(name)
        conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.s._line(conn,f"HELLO 1 {who['id']} {who['token']} SOCIALCHAT".encode())
        self.assertIn(b'WELCOME',conn['out']);conn['out'].clear()
        self.s._line(conn,('STATE 1 0 0 1 1 1 7 1 '+'a'*16+' '+'b'*16).encode())
        return conn

    def test_case_whitespace_unknown_and_whisper_do_not_publish(self):
        for value in ('/STORY','   /StOrY river','/mYsTeRy join privatecode','/future secret','/story/secret'):
            self.chat(self.a,value)
            self.assertEqual(self.b['chat_history'],[])
        self.a['chat_credit']=4
        self.s._line(self.a,f"CHAT {self.a['seq']+1} Bob {'/story secret'.encode().hex()}".encode())
        self.assertEqual(self.b['chat_history'],[])
        self.assertTrue(any('Commands are private' in bytes.fromhex(m[3]).decode() for m in self.a['chat_history']))
        self.chat(self.a,'ordinary hello')
        self.assertTrue(any(bytes.fromhex(m[3]).decode()=='ordinary hello' for m in self.b['chat_history']))

    def test_legacy_capability_is_absent_and_story_is_refused(self):
        old=self.legacy('Legacy')
        self.assertNotIn('COMMANDS ',self.s._snapshot(old))
        self.assertIn('COMMANDS 1 5',self.s._snapshot(self.a))
        for value in ('/story','/STORY pick river bank cut 0 secret','/mystery join secret'):
            self.assertTrue(any('unavailable' in line for line in self.chat(old,value)))
        self.assertEqual(self.b['chat_history'],[])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_receipts').fetchone()[0],0)

    def test_forged_chat_reply_does_not_negotiate_and_reconnect_resets(self):
        old=self.legacy('Legacy')
        old['chat_credit']=4
        fake='Legacy > Legacy: COMMANDS 1 7'
        self.s._line(old,f"CHAT {old['seq']+1} Legacy {fake.encode().hex()}".encode())
        self.assertFalse(old['private_commands'])
        self.assertTrue(any('unavailable' in line for line in self.chat(old,'/story river')))
        self.s.close();self.s=base.MemoryAuthority(self.root/'sock',self.root/'world')
        replacement=self.legacy('Alice')
        self.assertFalse(replacement['private_commands'])
        self.assertNotIn('COMMANDS ',self.s._snapshot(replacement))

    def test_owner_publication_cannot_be_smuggled_through_chat(self):
        before=self.s.db.execute('SELECT document FROM story_packs').fetchall()
        self.chat(self.a,'/STORY publish a_private_definition')
        self.assertEqual(self.s.db.execute('SELECT document FROM story_packs').fetchall(),before)
        self.assertEqual(self.b['chat_history'],[])
