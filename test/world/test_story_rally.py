"""Coordinator regressions. Native acceptance stays at the integrated checkpoint."""
import unittest
from world.rally import (RallyCoordinator, GYM, SLOTS, GATHER, TRAVEL, ACTIVE, RETURN,
                         INVITED, READY, NOT_YET, MOVING, ARRIVED, RETURNING, STAY,
                         LEFT, REPORT, OFFER, ACCEPT, LATER, CANCEL, GO, LAND,
                         FINISH, BACK, KEEP, HOME)


class StoryRallyTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.peers = {}
        self.rally = RallyCoordinator(self.peers, clock=lambda: self.now)
        self.owner = self.peer('owner', *GYM, 5, 3)
        self.guest = self.peer('guest', 0, 3, 20, 20)

    def peer(self, name, group=11, num=3, x=4, y=4) -> dict:
        conn: dict = dict(id=name, seq=0, state=[group,num,x,y,1,7,1], state_time=self.now,
                    closing=False, social=True)
        self.peers[name] = conn
        self.send(conn, REPORT, 0, 1)
        return conn

    def send(self, conn, action, identifier=0, arg=0):
        self.rally.process(conn, ['RALLY', str(conn['seq']+1), str(action), str(identifier), str(arg)])

    def offer(self, scope=1):
        self.send(self.owner, OFFER, 0, scope)
        rally = self.rally.current(self.owner)
        assert rally is not None
        return rally

    def member(self, rally, conn):
        return next(m for m in rally['members'] if m['conn'] is conn)

    def travel(self):
        rally = self.offer()
        self.send(self.guest, ACCEPT, rally['id'])
        self.send(self.owner, GO, rally['id'])
        return rally

    def test_ask_does_not_fabricate_readiness_or_arrival(self):
        rally = self.offer()
        self.assertEqual(rally['phase'], GATHER)
        self.assertEqual(self.member(rally, self.guest)['state'], INVITED)
        self.send(self.owner, GO, rally['id'])
        self.assertEqual(self.member(rally, self.guest)['state'], LEFT)
        self.assertEqual(self.member(rally, self.owner)['state'], ARRIVED)

    def test_not_yet_can_ready_then_go_requires_fresh_field(self):
        rally = self.offer()
        self.send(self.guest, LATER, rally['id'])
        self.assertEqual(self.member(rally, self.guest)['state'], NOT_YET)
        self.send(self.guest, ACCEPT, rally['id'])
        self.assertEqual(self.member(rally, self.guest)['state'], READY)
        self.guest['state'][6] = 0
        self.send(self.owner, GO, rally['id'])
        self.assertEqual(self.member(rally, self.guest)['state'], LEFT)

    def test_nearby_scope_and_world_scope_are_distinct(self):
        rally = self.offer(scope=0)
        self.assertEqual(len(rally['members']), 1)
        self.send(self.owner, CANCEL, rally['id'])
        rally = self.offer(scope=1)
        self.assertEqual(len(rally['members']), 2)

    def test_roster_is_four_not_four_combatants_and_busy_is_not_invited(self):
        for i in range(8):
            self.peer('extra'+str(i))
        self.guest['state'][6] = 0
        rally = self.offer()
        self.assertEqual(len(rally['members']), 4)
        self.assertNotIn(self.guest, [m['conn'] for m in rally['members']])
        self.assertEqual(len({m['slot'] for m in rally['members']}), 4)

    def test_replaced_connection_cannot_accept_or_inherit_invitation(self):
        rally = self.offer()
        old = self.guest
        replacement = self.peer('guest', 0, 3, 20, 20)
        self.send(old, ACCEPT, rally['id'])
        self.assertEqual(self.member(rally, old)['state'], INVITED)
        self.send(replacement, ACCEPT, rally['id'])
        self.assertIsNone(self.rally.current(replacement))
        self.assertEqual(self.member(rally, old)['state'], INVITED)

    def test_unrelated_actor_cannot_go_finish_or_cancel_owner_rally(self):
        rally = self.offer()
        self.send(self.guest, GO, rally['id'])
        self.send(self.guest, FINISH, rally['id'])
        self.assertEqual(rally['phase'], GATHER)
        self.send(self.guest, CANCEL, rally['id'])
        self.assertEqual(self.member(rally, self.guest)['state'], LEFT)
        self.assertEqual(rally['phase'], GATHER)

    def test_local_eligibility_and_owner_position_are_rechecked(self):
        rally = self.offer()
        self.send(self.guest, REPORT, 0, 0)
        self.send(self.guest, ACCEPT, rally['id'])
        self.assertEqual(self.member(rally, self.guest)['state'], INVITED)
        self.owner['state'][2] += 1
        self.send(self.owner, GO, rally['id'])
        self.assertIsNone(self.rally.current(self.owner))

    def test_arrival_requires_real_slot_and_fresh_state_not_departure_eligibility(self):
        rally = self.travel()
        self.assertEqual(rally['phase'], TRAVEL)
        self.assertEqual(self.member(rally, self.guest)['state'], MOVING)
        self.send(self.guest, LAND, rally['id'])
        self.assertEqual(self.member(rally, self.guest)['state'], MOVING)
        slot = self.member(rally, self.guest)['slot']
        self.guest['state'][:4] = [*GYM, *SLOTS[slot]]
        self.send(self.guest, REPORT, 0, 0)  # Anchored guests cannot join a second trip.
        self.send(self.guest, LAND, rally['id'])
        self.assertEqual(self.member(rally, self.guest)['state'], ARRIVED)
        self.assertEqual(rally['phase'], ACTIVE)

    def test_arrival_timeout_is_bounded_and_does_not_fake_ready(self):
        rally = self.travel()
        self.now += 21
        self.rally.tick()
        self.assertEqual(self.member(rally, self.guest)['state'], RETURNING)
        self.assertEqual(rally['phase'], ACTIVE)
        self.now += 601
        self.rally.tick()
        self.assertEqual(rally['phase'], RETURN)
        self.now += 121
        self.rally.tick()
        self.assertEqual(self.rally.rallies, {})

    def test_return_and_stay_are_independent_choices(self):
        rally = self.travel()
        self.send(self.owner, FINISH, rally['id'])
        self.assertEqual(self.member(rally, self.guest)['state'], RETURNING)
        self.send(self.guest, KEEP, rally['id'])
        self.assertEqual(self.member(rally, self.guest)['state'], STAY)
        self.assertIsNone(self.rally.current(self.guest))
        self.send(self.owner, HOME, rally['id'])
        self.assertFalse(self.rally.rallies)

    def test_host_loss_returns_survivors_and_new_presence_never_inherits(self):
        rally = self.travel()
        self.rally.disconnect(self.owner)
        del self.peers['owner']
        self.assertEqual(self.member(rally, self.guest)['state'], RETURNING)
        replacement = self.peer('owner', *GYM, 5, 3)
        self.assertIsNone(self.rally.current(replacement))
        self.send(self.guest, HOME, rally['id'])
        self.assertFalse(self.rally.rallies)

    def test_gather_timeout_and_stale_ids_cannot_launch_new_trip(self):
        old = self.offer()
        self.now += 61
        self.rally.tick()
        self.assertFalse(self.rally.rallies)
        for peer in self.peers.values():
            peer['state_time'] = self.now
            self.send(peer, REPORT, 0, 1)
        new = self.offer()
        self.send(self.guest, ACCEPT, old['id'])
        self.assertEqual(self.member(new, self.guest)['state'], INVITED)

    def test_sequence_invalid_actor_role_and_shapes_fail_closed(self):
        with self.assertRaises(ValueError):
            self.rally.process(self.owner, ['RALLY', str(self.owner['seq']), '1', '0', '1'])
        with self.assertRaises(ValueError):
            self.rally.process(self.owner, ['RALLY', '99', '1', '0', '1', 'guest'])
        service = dict(self.owner, id='service', social=False)
        with self.assertRaises(ValueError):
            self.send(service, OFFER, 0, 1)

    def test_snapshot_is_private_to_members_and_legacy_has_no_new_lines(self):
        rally = self.offer()
        outsider = self.peer('outsider')
        self.assertEqual(self.rally.snapshot(outsider), ['RALLY 0 0 0 0 - 0'])
        self.assertIn('RALLYMEM owner 2 0', self.rally.snapshot(self.guest))
        self.assertIn('RALLYMEM guest 1 1', self.rally.snapshot(self.guest))
        self.assertEqual(self.rally.snapshot(dict(id='legacy')), [])
        self.send(self.guest, BACK, rally['id'])
        self.assertIsNone(self.rally.current(self.guest))
