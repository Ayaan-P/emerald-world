#!/usr/bin/env python3
"""Explicit opt-in native fresh-player acceptance using ordinary player controls.

Requires private v1 invitations created through the hosted management API.
No save fixture, party patch, flag edit, warp injection or battle injection.
The existing stock campaign scenarios supply buttons, not headless execution.
This runner starts real-time networked native clients and verifies real disk saves.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'test/headless')]
import driver
import headless
import savecheck
from world.launcher import ProfileLock, game_command, player_endpoint
from world.player import PlayerClient, PlayerError
from world.session import DesktopSession
from world.transport import read_invitation

ROLES = ('alice', 'bob', 'carol', 'dave')


def check(value, label):
    if not value:
        raise AssertionError(label)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def public_state(state):
    keys = ('frame', 'map', 'pos', 'overworld', 'locked', 'script', 'battle',
            'fade', 'moving', 'party', 'activity')
    return {k: state[k] for k in keys if k in state}


class NativeGame:
    """driver-compatible adapter, but every input executes via real player SDK."""
    def __init__(self, run, role, client):
        self.run, self.role, self.client = run, role, client
        self.frames = 0
        self.state = driver.State(client.observe()['state'])

    def press(self, buttons='-', frames=1):
        self.run.bounded()
        held = [] if buttons == '-' else buttons.split('+')
        remaining = frames
        while remaining:
            self.run.bounded()
            amount = min(120, remaining)
            self.state = driver.State(self.client.press(held, amount)['state'])
            self.frames += amount
            remaining -= amount
        self.run.trace(self.role, self.state.__dict__)
        return self.state

    def wait(self, frames):
        return self.press('-', frames)

    def tap(self, button, times=1, hold=2, gap=20):
        for _ in range(times):
            self.press(button, hold)
            self.press('-', gap)
        return self.state


class FreshRun:
    def __init__(self, args):
        self.args = args
        self.roles = ROLES[:args.players]
        self.out = args.output.absolute()
        check(self.out.resolve() == self.out, 'output cannot contain symlinks')
        self.out.mkdir(parents=True, mode=0o700, exist_ok=False)
        self.report = {'ok': False, 'fixture_used': False, 'native_executed': False,
                       'stage': 'preflight', 'players': args.players, 'milestones': []}
        self.sessions, self.paths, self.locks = {}, {}, {}
        self.actor_ids = {}
        self.procs, self.all_procs, self.clients, self.games = {}, [], {}, {}
        self.pool = ThreadPoolExecutor(max_workers=args.players)
        self.guard = threading.Lock()
        self.stopping = threading.Event()
        self.start = time.monotonic()
        self.deadline = self.start + args.timeout
        self.binary_sha = digest(args.binary)
        marker = json.loads(args.ready_file.read_text())
        check(marker.get('ok') is True and marker.get('binary_sha256') == self.binary_sha,
              'binary must match explicit ready marker')
        self.report['binary_sha256'] = self.binary_sha
        self.profile_root = self.out
        if args.continue_from is not None:
            prior = args.continue_from.absolute()
            check(prior.resolve()==prior and prior.parent==self.out.parent, 'continuation must be a disposable sibling run')
            proof = json.loads((prior/'acceptance.json').read_text())
            check(proof.get('fixture_used') is False and proof.get('native_executed') is True
                  and proof.get('binary_sha256')==self.binary_sha
                  and proof.get('processes_reaped') is True and proof.get('players')==args.players,
                  'continuation requires the same completed disposable native process set')
            check({'new_game','continue_game'} <= {m['label']for m in proof['milestones']},
                  'continuation requires actual new-game and Continue evidence')
            self.profile_root = prior
            self.report['continued_from'] = str(prior)
            self.report['prior_report_sha256'] = digest(prior/'acceptance.json')
        self.persist()

    def persist(self):
        with self.guard:
            (self.out/'acceptance.json').write_text(json.dumps(self.report, indent=2)+'\n')

    def stage(self, value):
        self.report['stage'] = value
        self.persist()

    def bounded(self):
        if self.stopping.is_set():
            raise RuntimeError('fresh-player run cancelled')
        if time.monotonic() >= self.deadline:
            raise TimeoutError('fresh-player journey deadline')
        check(all(p.poll() is None for p in self.procs.values()), 'owned native process exited')

    def trace(self, role, state):
        with self.guard:
            with (self.out/'trace.jsonl').open('a') as f:
                f.write(json.dumps({'elapsed': time.monotonic()-self.start,
                                    'stage': self.report['stage'], 'role': role,
                                    'state': public_state(state)})+'\n')

    def connect(self):
        self.stage('connect private invitations into '+('owned genuine campaign checkpoints' if self.args.continue_from else 'empty local profiles'))
        identities = {}
        for role in self.roles:
            path = self.args.invitation_dir/(role+'.json')
            identity = read_invitation(path)
            check(identity.get('version') == 1, 'pinned v1 native invitation required')
            check(identity['trainer'] not in ('ayaan', 'friend'), 'disposable identities required')
            identities[role] = identity
            self.actor_ids[role] = identity['trainer']
        check(len({v['trainer'] for v in identities.values()}) == len(self.roles),
              'independent trainer identities required')
        check(len({(v['endpoint']['host'], v['endpoint']['port'], v['pin'])
                   for v in identities.values()}) == 1, 'one hosted world required')
        for role, identity in identities.items():
            session = DesktopSession(self.profile_root)
            self.sessions[role] = session
            ep = identity['endpoint']
            paths = session.connect_remote(role[0], self.args.invitation_dir/(role+'.json'),
                                           (ep['host'], ep['port']), identity['pin'])
            self.paths[role] = paths
            self.locks[role] = ProfileLock(session.state, identity['trainer'])
            if self.args.continue_from is None:
                check(not paths['save'].exists(), 'fresh player must start without any save')
            else:
                saved = savecheck.Save(paths['save'])
                check(saved.counter>0 and saved.party_count==0, 'continuation must use the genuine pre-starter save')
            check(len(os.fsencode(player_endpoint(paths))) < 108, 'shorten output directory')

    def spawn(self, roles=None):
        roles = tuple(roles or self.roles)
        self.stage('launch ordinary native clients')
        check(digest(self.args.binary) == self.binary_sha, 'binary changed')
        for role in roles:
            p = subprocess.Popen(game_command(self.args.binary, self.sessions[role].state,
                                              self.paths[role], None, agent_control=True),
                                 cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
            self.procs[role] = p
            self.all_procs.append(p)
        self.report['native_executed'] = True
        end = min(self.deadline, time.monotonic()+25)
        for role in roles:
            while time.monotonic() < end:
                self.bounded()
                client = PlayerClient(player_endpoint(self.paths[role]), timeout=5)
                try:
                    client.observe()
                except PlayerError:
                    client.close()
                    time.sleep(.1)
                    continue
                self.clients[role] = client
                self.games[role] = NativeGame(self, role, client)
                break
            else:
                raise TimeoutError('ordinary native startup')
        self.persist()

    def stop_games(self):
        for client in self.clients.values():
            client.close()
        self.clients.clear()
        self.games.clear()
        for p in self.procs.values():
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                p.wait(timeout=5)
        self.procs.clear()

    def scenario(self, name):
        self.stage('ordinary campaign '+name)
        variables = headless.scenario_variables(name)
        def play(role):
            game = self.games[role]
            if name=='first_battle':
                for frames,buttons in variables['steps']:
                    game.press(buttons,frames)
                    if game.state.battle:
                        break
                check(game.state.battle,'ordinary starter battle not reached')
                driver.fight_battle(game,limit=1800)
                driver.finish_dialog(game)
                game.wait(60)
                driver.finish_dialog(game)
                check(game.state.map_name=='LittlerootTown_ProfessorBirchsLab', 'starter story did not return to Birch lab')
                driver.save_game(game,3)
            elif 'play' in variables:
                variables['play'](game)
            else:
                for frames, buttons in variables['steps']:
                    game.press(buttons, frames)
            return public_state(game.state.__dict__)
        futures = {role: self.pool.submit(play, role) for role in self.roles}
        states = {role: future.result() for role, future in futures.items()}
        disks = {}
        for role in self.roles:
            path = self.paths[role]['save']
            check(path.is_file(), 'ordinary campaign did not create save')
            saved = savecheck.Save(path)
            check(saved.counter > 0, 'invalid ordinary save counter')
            disks[role] = {'sha256': digest(path), 'counter': saved.counter,
                           'name': saved.name, 'party_count': saved.saveblock1[0x234]}
        if name in ('first_battle', 'rival_battle'):
            check(all(v['party_count'] >= 1 for v in disks.values()), 'starter not obtained naturally')
            check(all(states[n]['party'] for n in self.roles), 'native party missing after starter')
        self.report['milestones'].append({'label': name, 'states': states, 'disk': disks})
        self.persist()
        return states, disks

    def run(self):
        self.connect()
        previous_counters = {role: (savecheck.Save(self.paths[role]['save']).counter if self.args.continue_from else 0)for role in self.roles}
        phases = ['first_battle'] if self.args.continue_from else ['new_game', 'continue_game', 'first_battle']
        if self.args.through_dex:
            phases.append('rival_battle')
        states = {}
        for phase in phases:
            self.spawn()
            states, disks = self.scenario(phase)
            check(all(disks[n]['counter'] > previous_counters[n] for n in self.roles),
                  'ordinary save did not advance independently')
            previous_counters = {n: disks[n]['counter'] for n in self.roles}
            self.stop_games()
        self.spawn()
        self.stage('ordinary final Continue and private save readback')
        fs = {n: self.pool.submit(driver.continue_game, self.games[n]) for n in self.roles}
        for f in fs.values():
            f.result()
        self.report['reloaded_parties'] = {n: self.games[n].state.party for n in self.roles}
        check(all(self.games[n].state.party == states[n]['party'] for n in self.roles),
              'private party changed on ordinary Continue')
        check(all(self.games[n].state.world.get('connected') for n in self.roles),
              'world did not reconnect after ordinary Continue')
        self.social_and_return()
        self.report['ok'] = True

    def states(self):
        return {n: self.clients[n].observe()['state'] for n in self.clients}

    def wait(self, label, predicate, seconds=30):
        self.stage(label)
        end = min(self.deadline, time.monotonic()+seconds)
        while time.monotonic()<end:
            self.bounded()
            states = self.states()
            if predicate(states):
                self.report['milestones'].append({'label':label})
                self.persist()
                return states
            time.sleep(.1)
        raise TimeoutError(label)

    def visible(self, states):
        if set(states)!=set(self.roles):
            return False
        for role, s in states.items():
            if not s.get('world',{}).get('connected'):
                return False
            for other in set(self.roles)-{role}:
                if not any(p.get('trainer')==self.actor_ids[other] and p.get('visible')
                           and p.get('pos')==states[other]['pos']
                           for p in s['world'].get('peers',[])):
                    return False
        return True

    def social_and_return(self):
        self.stage('fresh players meet by normal walking')
        coords = ((10,10),(11,10),(10,11),(11,11)) if self.args.through_dex else ((5,5),(6,5),(5,7),(6,7))
        targets = dict(zip(self.roles,coords))
        for n in self.roles:
            driver.walk_to(self.games[n],*targets[n])
        self.wait('all fresh players see every other player',self.visible)
        for host,guest in zip(self.roles[::2],self.roles[1::2]):
            self.games[host].tap('RIGHT')
            self.games[host].tap('A')
            self.wait('fresh ordinary peer menu '+host,lambda s,h=host:s[h]['activity']['phase']=='menu')
            self.games[host].tap('DOWN',4)
            self.games[host].tap('A')
            self.wait('fresh bilateral invitation '+guest,lambda s,g=guest:s[g]['activity']['phase']=='invitation')
            self.games[guest].tap('UP')
            self.games[guest].tap('A')
            self.wait('fresh bilateral Tag accepted '+host,lambda s,h=host,g=guest:s[h]['activity'].get('tag_peer')==self.actor_ids[g] and s[g]['activity'].get('tag_peer')==self.actor_ids[h])
        self.stage('ordinary save before leaving hosted world')
        fs=[self.pool.submit(driver.save_game,self.games[n],4 if self.args.through_dex else 3)for n in self.roles]
        for f in fs:f.result()
        owner=self.roles[0]
        before=self.clients[owner].observe()['state']['party']
        self.clients.pop(owner).close()
        self.games.pop(owner)
        p=self.procs.pop(owner)
        os.killpg(p.pid,signal.SIGTERM)
        p.wait(timeout=5)
        self.wait('owner left but friends remain connected',lambda s:len(s)==len(self.roles)-1 and all(v['world'].get('connected') for v in s.values()))
        guest=self.roles[1]
        self.games[guest].tap('DOWN')
        self.games[guest].tap('UP')
        self.spawn([owner])
        driver.continue_game(self.games[owner])
        check(self.games[owner].state.party==before,'owner private state changed on return')
        driver.walk_to(self.games[owner],*targets[owner])
        self.wait('owner returned and all fresh peers visible',self.visible)

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
        self.stop_games()
        for lock in self.locks.values():
            lock.close()
        for session in self.sessions.values():
            session.close()
        self.report['processes_reaped'] = all(p.poll() is not None for p in self.all_procs)
        self.report['binary_unchanged'] = digest(self.args.binary) == self.binary_sha
        self.report['elapsed_seconds'] = time.monotonic()-self.start
        self.report['ok'] = bool(self.report['ok'] and self.report['processes_reaped']
                                 and self.report['binary_unchanged'])
        self.persist()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--ready-file', type=Path, required=True)
    parser.add_argument('--invitation-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--players', type=int, choices=(2, 4), default=4)
    parser.add_argument('--through-dex', action='store_true')
    parser.add_argument('--continue-from',type=Path,help='resume only this harness-owned genuine pre-starter checkpoint, never a seed/fixture')
    parser.add_argument('--timeout', type=int, default=2400)
    parser.add_argument('--allow-launch', action='store_true')
    args = parser.parse_args(argv)
    check(args.allow_launch, 'native launch requires explicit --allow-launch')
    os.umask(0o077)
    run = FreshRun(args)
    try:
        run.run()
    except Exception as exc:
        run.stopping.set()
        run.pool.shutdown(wait=True, cancel_futures=True)
        run.report['error_type'] = type(exc).__name__
        if type(exc) in (AssertionError,TimeoutError,driver.GameError):
            run.report['error_label'] = str(exc)[:500]
        run.report['ok'] = False
        for role, client in run.clients.items():
            try:
                shot = client.screenshot()['screenshot']
                (run.out/(role+'-blocker.ppm')).write_bytes(Path(shot).read_bytes())
            except Exception:
                pass
    finally:
        run.close()
    print(json.dumps({'ok': run.report['ok'], 'stage': run.report['stage'],
                      'report': str(run.out/'acceptance.json')}))
    return 0 if run.report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
