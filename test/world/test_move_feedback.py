import json,unittest
import test_field_move_ui
from world import field_move_ui,overworld_moves,move_feedback
class Feedback(test_field_move_ui.UI):
 def test_committed_shared_visual_once_and_no_replay(self):
  self.assertEqual(field_move_ui.handle(self.s,self.c,b'FM WATCH 1'),'FM WATCH 1\n')
  token=self.get();field_move_ui.handle(self.s,self.c,('FM USE 1 '+token+' turn').encode())
  self.assertNotIn(b'FM FX ',self.c['out']);self.f.admit(1)
  self.assertEqual(bytes(self.c['out']).count(b'FM FX '),1)
  self.assertIn(b' 72 70 52\n',self.c['out'])
  row=self.s.db.execute('SELECT id,seq FROM world_move_intents').fetchone();overworld_moves.admitted(self.s,row[0]);self.assertEqual(bytes(self.c['out']).count(b'FM FX '),1)
  self.s.close();base=self.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_move_visuals').fetchone()[0],1)
  # Re-admission cannot emit old cosmetics, even with no live channel present.
  overworld_moves.admitted(self.s,row[0])
 def test_opt_in_revision_distance_and_freshness(self):
  self.f.act('turn',52);self.f.admit(1);self.assertNotIn(b'FM FX ',self.c['out'])
  row=self.s.db.execute('SELECT id,seq FROM world_move_intents').fetchone()
  field_move_ui.handle(self.s,self.c,b'FM WATCH 1')
  original=self.p['cave_ack'];self.p['cave_ack']='wrong'
  move_feedback.committed(self.s,row[0],row[1],52);self.assertNotIn(b'FM FX ',self.c['out']);self.p['cave_ack']=original
  old=self.p['state'][2];self.p['state'][2]=1
  move_feedback.committed(self.s,row[0],row[1],52);self.assertNotIn(b'FM FX ',self.c['out']);self.p['state'][2]=old
  stamp=self.p['state_time'];self.p['state_time']=0
  move_feedback.committed(self.s,row[0],row[1],52);self.assertNotIn(b'FM FX ',self.c['out']);self.p['state_time']=stamp
  move_feedback.committed(self.s,row[0],row[1],52);self.assertIn(b'FM FX ',self.c['out'])
 def test_failed_admission_no_visual(self):
  field_move_ui.handle(self.s,self.c,b'FM WATCH 1');self.f.act('turn',52)
  self.s.deployment=None
  from world import actor_objects
  actor_objects.poll_player(self.s);self.assertNotIn(b'FM FX ',self.c['out'])
 def test_second_player_observes_same_commit_not_remote_map(self):
  import socket
  p=self.f.f.f.connect('Observer',True)
  self.f.f.f.f.f.send(p,'CAVE GET');self.f.f.f.f.f.send(p,'CAVE ACK '+self.s.shared_cave.identity)
  self.f.f.f.f.f.state(p,*self.s.wilds_map,73,69)
  left,right=socket.socketpair();self.addCleanup(left.close);self.addCleanup(right.close)
  c=dict(id=p['id'],presence=p,sock=left,out=bytearray(),link=True)
  self.s.connections[left]=c;self.s.link_channels[p['id']]=c
  self.assertEqual(field_move_ui.handle(self.s,c,b'FM WATCH 1'),'FM WATCH 1\n')
  self.f.act('turn',52);self.f.admit(1)
  self.assertEqual(bytes(c['out']).count(b'FM FX '),1);self.assertNotIn(b'FM FX ',self.c['out'])
 def test_npc_reaction_uses_same_shared_committed_feedback(self):
  field_move_ui.handle(self.s,self.c,b'FM WATCH 1')
  self.f.test_npc_actual_receipt_required_then_shared_effect()
  lines=[line for line in bytes(self.c['out']).splitlines() if line.startswith(b'FM FX ')]
  self.assertEqual(len(lines),2);self.assertTrue(lines[0].endswith(b' 52'));self.assertTrue(lines[1].endswith(b' 55'))
