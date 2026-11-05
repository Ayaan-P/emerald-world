"""Actual link coordinator negotiation, not native battle acceptance."""
import unittest
from world.link_protocol import LinkProtocol

class SplitProtocolTests(unittest.TestCase):
    def setUp(self):
        self.p=LinkProtocol(clock=lambda:0,id_factory=lambda:123)
        self.pos={'alice':[1,4,5,5,4,7,1],'bob':[1,4,6,5,3,7,1]}
    def message(self,actor,line):return self.p.process(actor,line.encode(),self.pos)
    def admit(self,mode=1):
        self.message('alice',f'L OFFER {mode} bob');self.message('bob','L ACCEPT 123')
    def open(self,actor,slot,wiretype,mode=1):
        return self.message(actor,f'L EVENT 1 123 {mode} {slot} 1 0 {wiretype} '+('0'*32))
    def test_matching_modern_rule_pairs(self):
        self.admit();self.assertEqual(self.open('alice',0,0xA233),[])
        result=self.open('bob',1,0xA233)
        self.assertEqual(len(result),2);self.assertTrue(all('L COMMIT 1 ' in line for _,line in result))
    def test_mismatch_aborts_before_pair(self):
        self.admit();self.open('alice',0,0xA233)
        result=self.open('bob',1,0x2233)
        self.assertIn(('bob','L ERROR LINK_TYPE_MISMATCH\n'),result)
        self.assertTrue(any(actor=='alice' and 'L ABORT' in line for actor,line in result))
        self.assertFalse(any('L COMMIT 1 ' in line for _,line in result))
    def test_vanilla_still_pairs(self):
        self.admit();self.open('alice',0,0x2233)
        self.assertEqual(len(self.open('bob',1,0x2233)),2)
    def test_rules_cannot_change_between_link_generations(self):
        self.admit();self.open('alice',0,0xA233);self.open('bob',1,0xA233)
        self.message('alice','L EVENT 2 123 1 0 1 0 0 '+('0'*32))
        self.message('bob','L EVENT 2 123 1 1 1 0 0 '+('0'*32))
        result=self.message('alice','L EVENT 1 123 1 0 2 0 8755 '+('0'*32))
        self.assertIn(('alice','L ERROR LINK_TYPE_MISMATCH\n'),result)
        self.assertTrue(any(actor=='bob' and 'L ABORT' in line for actor,line in result))

    def test_trade_does_not_accept_battle_rule_tag(self):
        self.admit(3);result=self.open('alice',0,0x9111,mode=3)
        self.assertIn(('alice','L ERROR MALFORMED\n'),result)
    def test_coop_pair_requires_matching_rules(self):
        self.message('alice','T OFFER bob');self.message('bob','T ACCEPT 123')
        # Public IDs are monotonic after the tag ID.
        self.message('alice','L OFFER 4 bob');sid=124
        def send(actor,slot,t):return self.message(actor,f'L EVENT 1 {sid} 4 {slot} 1 0 {t} '+('0'*32))
        self.assertEqual(send('alice',0,0xA255),[])
        result=send('bob',1,0x2255)
        self.assertIn(('bob','L ERROR LINK_TYPE_MISMATCH\n'),result)
        self.assertFalse(any('L COMMIT 1 ' in line for _,line in result))

if __name__=='__main__':unittest.main()
