import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from world.contest_admission import ContestAdmission
class Admission(unittest.TestCase):
 def setUp(self):self.now=0;self.a=ContestAdmission(clock=lambda:self.now,ticket_id=lambda:42)
 def enroll(self,owner,category=0,revision=1):
  return self.a.enroll(owner=owner,connection=owner+'-connection',visit=1,category=category,selection_revision=revision,tag=8,members=('a','b'),counter=True,local_ready=True)
 def ready(self,owner,connection=None):
  return self.a.ready(tag=8,ticket=42,owner=owner,connection=connection or owner+'-connection',visit=1,selection_revision=1)
 def test_both_native_confirmations_and_one_shot(self):
  self.assertEqual(self.enroll('a')['state'],'waiting');self.assertEqual(self.enroll('b')['state'],'prepared')
  self.assertEqual(self.ready('a')['state'],'prepared')
  with self.assertRaises(ValueError):self.a.consume(tag=8,ticket=42)
  self.assertEqual(self.ready('b')['state'],'admitted');self.a.consume(tag=8,ticket=42)
  with self.assertRaises(ValueError):self.a.consume(tag=8,ticket=42)
 def test_category_choice_is_not_overridden(self):
  self.enroll('a',0);self.assertEqual(self.enroll('b',1)['state'],'different_categories');self.assertFalse(self.a.active)
 def test_changed_connection_and_revision_rejected(self):
  self.enroll('a',revision=2)
  with self.assertRaises(ValueError):self.enroll('a',revision=1)
  self.enroll('a',revision=2);self.enroll('b')
  with self.assertRaises(ValueError):self.ready('b','new-connection')
 def test_cancel_and_timeout_never_start(self):
  self.enroll('a');self.enroll('b');self.ready('a');self.now=16
  self.assertEqual(self.a.expire()[0]['state'],'cancelled')
  with self.assertRaises(ValueError):self.ready('b')
  self.now=20;self.enroll('a');self.enroll('b')
  self.a.cancel(tag=8,owner='a',connection='a-connection')
  with self.assertRaises(ValueError):self.ready('b')
if __name__=='__main__':unittest.main()
