#!/usr/bin/env python3
"""Two real native clients and a genuine event-triggered model player.

Disposable fixtures only. The initiating trainer is driven with ordinary native
buttons by this test, not a human playtest. No administrator event injection.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent/'emerald-world-research'
sys.path[:0] = [str(ROOT),str(ROOT/'test/world'),str(ROOT/'test/headless')]
from native_acceptance import fixture
from world.launcher import ProfileLock, game_command, player_endpoint
from world.player import PlayerClient
from world.player_runtime import CodexPolicy, RuntimePlayer
from world.session import DesktopSession


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--model', required=True)
    parser.add_argument('--contact-frames', type=int, choices=range(1,121), default=16)
    parser.add_argument('--contact-only', action='store_true', help='Native greeting repro, no provider calls')
    parser.add_argument('--contact-delay', type=float, default=0, help='Bounded precontact backpressure probe (0..25 seconds)')
    parser.add_argument('--debug-native', action='store_true', help='Trace Alice contact gates under gdb inside its sandbox')
    parser.add_argument('--idle-boundary-repro', action='store_true', help='With contact-only: intentionally cross the known 30-second SDK idle lease')
    parser.add_argument('--binary', type=Path, default=ROOT/'build/pokeemerald64')
    args = parser.parse_args(argv)
    if not 0 <= args.contact_delay <= 25:
        parser.error('contact-delay must be in 0..25 seconds')
    if args.idle_boundary_repro and not args.contact_only:
        parser.error('idle-boundary-repro requires contact-only; no provider budget')
    out = args.out.absolute()
    if out.resolve() != out or not out.is_relative_to(RESEARCH.resolve()):
        raise ValueError('out must be a new non-symlink research directory')
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    seed = RESEARCH/'baseline/fixture-firstbattle.sav'
    seed_hash = hashlib.sha256(seed.read_bytes()).hexdigest()
    report = {'ok':False,'scope':'real native meeting -> genuine model -> ordinary native buttons; initiating trainer test-driven',
              'model':args.model,'binary_sha256':hashlib.sha256(args.binary.read_bytes()).hexdigest(),
              'decisions':[],'native_replies':[], 'provider_attempts':0,
              'contact_frames':args.contact_frames,'contact_only':args.contact_only,
              'contact_delay':args.contact_delay,'debug_native':args.debug_native}
    if args.contact_only:
        report['scope'] = 'native contact only; no model requested'
    if args.idle_boundary_repro:
        report['scope'] = 'native socket idle-boundary repro; no contact or provider requested'
    host = DesktopSession(out)
    procs, logs, locks = [], [], []
    runtime = None
    thread = None
    alice = None
    paths = {}
    stop = threading.Event()

    def save():
        (out/'acceptance.json').write_text(json.dumps(report,indent=2))

    def telemetry(name):
        try:
            return json.loads(paths[name]['telemetry'].read_text())
        except (OSError,ValueError):
            return {}

    started = time.monotonic()
    def trace(label, **fields):
        entry = {'label':label, 'elapsed':time.monotonic()-started,
                 'telemetry':{n:telemetry(n) for n in paths}, **fields}
        with (out/'trace.jsonl').open('a') as stream:
            stream.write(json.dumps(entry)+'\n')

    class TracedClient(PlayerClient):
        def _request(self, op, **fields):
            trace('sdk.start', endpoint=self.endpoint, op=op, fields=fields)
            try:
                response = super()._request(op, **fields)
            except BaseException:
                trace('sdk.error', endpoint=self.endpoint, op=op, error=traceback.format_exc())
                raise
            trace('sdk.end', endpoint=self.endpoint, op=op, response=response)
            return response

    def await_(label, condition, seconds=45):
        trace('await.start', boundary=label)
        deadline = time.monotonic()+seconds
        while time.monotonic()<deadline:
            if any(proc.poll() is not None for proc in procs):
                raise AssertionError('owned native process exited during '+label)
            value = condition()
            if value:
                trace('await.end', boundary=label)
                return value
            time.sleep(.05)
        raise AssertionError('deadline: '+label)

    try:
        state = host.create_world('w')
        host.host('w')
        server = host.server
        assert server is not None
        original_line = server._line
        def measured_line(conn, raw):
            t = time.monotonic()
            sql_boundaries = []
            # Operation names only: never record SQL or authentication values.
            server.db.set_trace_callback(lambda sql: sql_boundaries.append(
                (sql.split(None,1)[0].upper(), time.monotonic())))
            try:
                return original_line(conn, raw)
            finally:
                end = time.monotonic()
                server.db.set_trace_callback(None)
                op = raw.split(b' ',1)[0].decode('ascii',errors='replace')
                if op in ('STATE','MEET'):
                    with (out/'server-timing.jsonl').open('a') as stream:
                        stream.write(json.dumps({'elapsed':end-started,
                            'duration':end-t,'op':op,'trainer':conn.get('id'),
                            'sql_timings':[{'op':operation,'duration':(
                                sql_boundaries[i+1][1] if i+1<len(sql_boundaries) else end)-at}
                                for i,(operation,at) in enumerate(sql_boundaries)],
                            'seq':conn.get('seq'),'state':conn.get('state'),
                            'revision':server.revision})+'\n')
        server._line = measured_line
        for name,direction in (('alice','LEFT'),('bob','RIGHT')):
            paths[name] = host.local_profile(name,seed)
            fixture(seed,paths[name]['save'],name)
            startup = paths[name]['profile']/'bootstrap.txt'
            startup.write_text('300 -\n2 START\n140 -\n2 START\n220 -\n2 A\n220 -\n2 A\n240 -\n16 '+direction+'\n24 -\n1 DOWN\n24 -\n')
            command = game_command(args.binary.resolve(),state,paths[name],None,agent_control=True)
            command += ['--world-input',str(startup)]
            if args.debug_native and name == 'alice':
                debugger = paths[name]['profile']/'contact.gdb'
                debugger.write_text('set pagination off\nset confirm off\nstart\n'
                    'watch -l sWorld.pendingObject[0]\ncommands\nsilent\n'
                    'printf "DEBUG-contact pending=%d output=%lu sent=%lu seq=%u interaction=%u facing=%u transition=%u\\n", sWorld.pendingObject[0], sWorld.outputSize, sWorld.outputSent, sWorld.seq, sWorld.interactionSeq, gObjectEvents[gPlayerAvatar.objectEventId].facingDirection, gPlayerAvatar.tileTransitionState\n'
                    'continue\nend\ncontinue\n')
                index = command.index('--')+1
                command[index:index] = ['/usr/bin/gdb','-q','-batch','-x',str(debugger),'--args']
            locks.append(ProfileLock(state,name))
            log = (out/(name+'.log')).open('wb')
            logs.append(log)
            procs.append(subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,
                stderr=subprocess.STDOUT,start_new_session=True))
        await_('both native fixtures bootstrapped',lambda:all(
            telemetry(n).get('frame',0)>1250 and telemetry(n).get('connected')
            and telemetry(n).get('ready') and player_endpoint(paths[n]).is_socket()
            for n in paths))
        alice = TracedClient(player_endpoint(paths['alice']))
        # Only move once both native clients have observed the current peer
        # coordinates. Bootstrap snapshots can otherwise leave a solid ghost
        # on Alice's intended destination.
        await_('current native peer positions converged', lambda: all(any(
            p['trainer'] == other and p['visible'] and p['pos'] == telemetry(other).get('pos')
            for p in telemetry(name).get('peers', []))
            for name, other in (('alice', 'bob'), ('bob', 'alice'))))
        alice.press(['RIGHT'],16)
        alice.press([],16)
        await_('adjacent peer visible',lambda:any(p['trainer']=='bob' and p['visible']
            for p in telemetry('alice').get('peers',[])))
        before = {n:telemetry(n) for n in paths}
        if before['alice']['pos'] != [6,5] or before['bob']['pos'] != [7,5]:
            raise AssertionError('unexpected real native fixture positions')
        trace('policy.construct.start')
        genuine = CodexPolicy(args.model,timeout=120,stop=stop)
        trace('policy.construct.end')
        class RecordingPolicy:
            def __call__(self, context):
                if args.contact_only:
                    stop.wait(5)
                    return {'actions':[]}
                trace('policy.call.start', context=context)
                if (context['trigger'] != 'meeting' or context['meeting']['player'] != 'alice'
                        or context['meeting']['target'] != 'bob'):
                    raise AssertionError('provider requested before genuine native contact')
                if report['provider_attempts'] >= 2:
                    raise AssertionError('provider call budget exceeded')
                report['provider_attempts'] += 1
                save()
                value = genuine(context)
                trace('policy.call.end', response=value)
                report['decisions'].append({'trigger':context['trigger'],'meeting':context['meeting'],'response':value})
                save()
                return value
            def cancel(self):
                genuine.cancel()
        trace('runtime.construct.start')
        runtime = RuntimePlayer(player_endpoint(paths['bob']),RecordingPolicy(),interval=3600,
            min_model_interval=1,poll_interval=.1,stop=stop,model_timeout=125)
        trace('runtime.construct.end')
        class RecordingClient(TracedClient):
            def press(self, buttons, frames):
                response = super().press(buttons,frames)
                report['native_replies'].append(response)
                save()
                return response
        runtime.client.close()
        runtime.client = RecordingClient(player_endpoint(paths['bob']))
        thread = threading.Thread(target=runtime.run,name='acceptance-native-player')
        thread.start()
        await_('continuous runtime baseline',lambda:runtime.status['status'] in ('baseline','idle'))
        report['before'] = before
        if args.contact_delay:
            report['initiator_before_delay'] = alice.observe()
            trace('precontact.delay.start', seconds=args.contact_delay)
            time.sleep(args.contact_delay)
            trace('precontact.delay.end')
        report['initiator_before'] = alice.observe()
        if args.idle_boundary_repro:
            save()
            trace('idle.boundary.start', seconds=32, known_native_idle_seconds=30)
            time.sleep(32)
            trace('idle.boundary.end')
            # Idempotent observation only. Never submit a press on an expired lease.
            report['idle_boundary_observation'] = alice.observe()
            raise AssertionError('expected native idle lease to close the original socket')
        own = report['initiator_before']['state']
        trace('contact.preconditions', facing=own['facing'], moving=own['moving'],
              phase={key:own[key] for key in ('overworld','locked','script','battle','fade')})
        if (own['facing'] != 4 or own['moving'] or not own['overworld']
                or any(own[key] for key in ('locked','script','battle','fade'))
                or own['pos'] != [6,5] or not own['world']['ready']):
            raise AssertionError('initiating trainer is not stationary, ready and facing the adjacent peer')
        save()
        report['initiator_contact'] = alice.press(['A'],args.contact_frames)
        alice.press([],16)
        # Integrated clients open the real activity menu first. Talk is the
        # initial selection and emits the ordinary server-committed MEET only
        # after this separate deliberate confirmation.
        if 'activity' in report['initiator_contact']['state']:
            await_('native Talk menu', lambda: alice.observe()['state'].get('activity', {}).get('phase') == 'menu')
            report['initiator_talk'] = alice.press(['A'],1)
            alice.press([],16)
        save()
        meeting = await_('ordinary native contact',lambda:(telemetry('bob').get('meeting') or {}).get('player')=='alice'
            and (telemetry('bob').get('meeting') or {}).get('target')=='bob'
            and telemetry('bob')['meeting'])
        report['native_meeting'] = meeting
        if args.contact_only:
            report['scope'] = 'native contact only; no model requested'
        else:
            await_('genuine event-driven action acknowledged by native game',
                lambda:runtime.status.get('status')=='acted' and runtime.status.get('completed',0)>0,seconds=135)
        stop.set()
        thread.join(5)
        if thread.is_alive():
            raise AssertionError('runtime failed to stop')
        if not args.contact_only:
            if not report['decisions'] or report['decisions'][0]['trigger']!='meeting':
                raise AssertionError('model was not triggered by the native meeting')
            if not report['native_replies'] or not all(r.get('ok') is True and
                    r['state']['world']['trainer']=='bob' for r in report['native_replies']):
                raise AssertionError('missing real own-player acknowledgments')
        after = {n:telemetry(n) for n in paths}
        if before['alice']['pos'] != after['alice']['pos']:
            raise AssertionError('reacting player moved initiating trainer')
        report.update(before=before,after=after,runtime_status=runtime.status,ok=True)
    except BaseException:
        report['error'] = traceback.format_exc()
        report['last_telemetry'] = {n:telemetry(n) for n in paths}
        if runtime is not None:
            report['runtime_status'] = runtime.status
        print(report['error'],file=sys.stderr)
    finally:
        stop.set()
        if thread is not None:
            thread.join(5)
        if runtime is not None and (thread is None or not thread.is_alive()):
            runtime.close()
        if alice is not None:
            alice.close()
        for proc in procs:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=5)
        for log in logs:
            log.close()
        for lock in locks:
            lock.close()
        host.close()
        report['seed_unchanged'] = hashlib.sha256(seed.read_bytes()).hexdigest()==seed_hash
        report['processes_reaped'] = all(p.poll() is not None for p in procs)
        report['ok'] = bool(report['ok'] and report['seed_unchanged'] and report['processes_reaped'])
        save()
    print(json.dumps({'ok':report['ok'],'report':str(out/'acceptance.json')}))
    return 0 if report['ok'] else 1


if __name__=='__main__':
    raise SystemExit(main())
