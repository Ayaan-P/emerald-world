"""Ephemeral consent for one native Roxanne approach. Never reads/writes saves.

Eligibility is a coarse native attestation, not campaign data. The native client
rechecks its own flags, tasks, map geometry and return ledger before travelling.
A rally is at most four visitors, not four combatants (the link engine is two).
"""
import time

GYM = (11, 3)  # data/maps/map_groups.json: RustboroCity_Gym
# Separate safe-floor candidates beside the normal Roxanne approach.
SLOTS = ((5, 3), (4, 3), (6, 3), (5, 4))
GATHER, TRAVEL, ACTIVE, RETURN = range(1, 5)
INVITED, READY, NOT_YET, MOVING, ARRIVED, RETURNING, STAY, LEFT = range(1, 9)
REPORT, OFFER, ACCEPT, LATER, CANCEL, GO, LAND, FINISH, BACK, KEEP, HOME, FAIL = range(12)


class RallyCoordinator:
    def __init__(self, peers, clock=time.monotonic):
        self.peers = peers
        self.clock = clock
        self.serial = 0
        self.rallies = {}

    def current(self, conn):
        for rally in self.rallies.values():
            if any(member['conn'] is conn and member['state'] not in (STAY, LEFT)
                   for member in rally['members']):
                return rally
        return None

    def fresh(self, conn, eligible=True):
        state = conn.get('state')
        now = self.clock()
        return (self.peers.get(conn['id']) is conn and not conn.get('closing')
                and state is not None and state[6] == 1
                and now - conn.get('state_time', -100) <= 3
                and (not eligible or conn.get('rally_eligible', False))
                and now - conn.get('rally_report', -100) <= 3)

    def at_scene(self, conn):
        state = conn.get('state')
        return (state is not None and tuple(state[:2]) == GYM
                and tuple(state[2:4]) == SLOTS[0])

    def process(self, conn, fields):
        if len(fields) != 5 or not conn.get('social'):
            raise ValueError('invalid rally shape')
        if any(not s.isascii() or not s.isdecimal() or len(s) > 10 for s in fields[1:]):
            raise ValueError('invalid rally integer')
        if self.peers.get(conn['id']) is not conn or conn.get('closing'):
            return
        seq, action, identifier, arg = map(int, fields[1:])
        if seq <= conn['seq'] or seq > 2**32-1 or action > FAIL or arg > 3:
            raise ValueError('invalid rally sequence or action')
        conn['seq'] = seq
        if action == REPORT:
            if identifier:
                raise ValueError('invalid rally report')
            conn['rally_enabled'] = True
            conn['rally_eligible'] = bool(arg & 1)
            conn['rally_report'] = self.clock()
            return
        if not conn.get('rally_enabled'):
            raise ValueError('rally report required')
        self.tick()
        rally = self.current(conn)
        if action == OFFER:
            if identifier or arg > 1 or rally or not self.fresh(conn) or not self.at_scene(conn):
                return
            # One bounded roster per presence. No service/control actor can join.
            candidates = []
            for name, peer in sorted(self.peers.items()):
                if peer is conn or not peer.get('rally_enabled') or self.current(peer) or not self.fresh(peer):
                    continue
                state, origin = peer['state'], conn['state']
                if arg == 0 and (state[:2] != origin[:2]
                                 or abs(state[2]-origin[2])+abs(state[3]-origin[3]) > 12):
                    continue
                candidates.append(peer)
            if self.serial == 2**32-1:
                return
            self.serial += 1
            rally = dict(id=self.serial, phase=GATHER, scope=arg, owner=conn,
                         until=self.clock()+60,
                         members=[dict(conn=c, state=READY if c is conn else INVITED, slot=i)
                                  for i, c in enumerate([conn]+candidates[:3])])
            self.rallies[self.serial] = rally
            return
        if not rally or identifier != rally['id']:
            return
        member = next(m for m in rally['members'] if m['conn'] is conn)
        owner = rally['owner'] is conn
        if action in (ACCEPT, LATER) and rally['phase'] == GATHER:
            if action == LATER:
                member['state'] = NOT_YET
            elif self.fresh(conn):
                member['state'] = READY
        elif action == CANCEL:
            if owner:
                self._return(rally)
            elif member['state'] in (MOVING, ARRIVED):
                member['state'] = RETURNING
            else:
                member['state'] = LEFT
        elif action == GO and owner and rally['phase'] == GATHER:
            if not self.fresh(conn) or not self.at_scene(conn):
                self._return(rally)
                return
            # GO is the owner's explicit fresh consent too. It is not inferred
            # from a remote readiness indicator or a previous not-yet choice.
            member['state'] = READY
            # GO ON explicitly leaves invited/not-yet/busy participants behind.
            for m in rally['members']:
                if m['state'] == READY and self.fresh(m['conn']):
                    m['state'] = ARRIVED if m['conn'] is conn else MOVING
                else:
                    m['state'] = LEFT
            rally['phase'], rally['until'] = TRAVEL, self.clock()+20
        elif action == LAND and rally['phase'] in (TRAVEL, ACTIVE) and member['state'] == MOVING:
            state = conn.get('state')
            if (self.fresh(conn, eligible=False) and tuple(state[:2]) == GYM
                    and tuple(state[2:4]) == SLOTS[member['slot']]):
                member['state'] = ARRIVED
        elif action == FINISH and owner and rally['phase'] in (TRAVEL, ACTIVE):
            self._return(rally)
        elif action in (BACK, FAIL) and member['state'] not in (STAY, LEFT):
            member['state'] = RETURNING if member['state'] in (MOVING, ARRIVED, RETURNING) else LEFT
            if owner:
                self._return(rally)
        elif action == KEEP and member['state'] == RETURNING:
            member['state'] = STAY
        elif action == HOME and member['state'] == RETURNING:
            member['state'] = LEFT
        self.tick()

    def _return(self, rally):
        rally['phase'], rally['until'] = RETURN, self.clock()+120
        for member in rally['members']:
            if member['state'] in (MOVING, ARRIVED):
                member['state'] = RETURNING
            elif member['state'] in (INVITED, READY, NOT_YET):
                member['state'] = LEFT

    def disconnect(self, conn):
        rally = self.current(conn)
        if not rally:
            return
        if rally['owner'] is conn:
            self._return(rally)
        for member in rally['members']:
            if member['conn'] is conn:
                member['state'] = LEFT
        self.tick()

    def tick(self):
        now = self.clock()
        for identifier, rally in list(self.rallies.items()):
            if now >= rally['until']:
                if rally['phase'] == GATHER:
                    self._return(rally)
                elif rally['phase'] == TRAVEL:
                    for m in rally['members']:
                        if m['state'] == MOVING:
                            m['state'] = RETURNING
                    rally['phase'], rally['until'] = ACTIVE, now+600
                elif rally['phase'] == ACTIVE:
                    self._return(rally)
                else:
                    del self.rallies[identifier]
                    continue
            if rally['phase'] == TRAVEL and all(m['state'] != MOVING for m in rally['members']):
                rally['phase'], rally['until'] = ACTIVE, now+600
            if all(m['state'] in (STAY, LEFT) for m in rally['members']):
                del self.rallies[identifier]

    def snapshot(self, conn):
        if not conn.get('rally_enabled'):
            return []
        rally = self.current(conn)
        if not rally:
            return ['RALLY 0 0 0 0 - 0']
        lines = [f"RALLY {rally['id']} {rally['phase']} 1 {rally['scope']} {rally['owner']['id']} {len(rally['members'])}"]
        lines += [f"RALLYMEM {m['conn']['id']} {m['state']} {m['slot']}" for m in rally['members']]
        return lines
