"""Run two Expansion processes with an in-memory/file presence relay.

This does not use the world server or any sockets and is not a network test.
It checks that independent engines can consume each other's real position
telemetry and instantiate both remote objects. Saves are disposable.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from world.expansion import serialize_peers

binary = Path(sys.argv[1]).resolve(strict=True)
donor = Path(sys.argv[2]).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='expansion-dual-') as temp:
    root = Path(temp)
    script = root / 'two-clients.replay'
    script.write_text((donor / 'tests/smoke/opening_start.replay').read_text() + '\nwait 4000\n')
    processes = []
    profiles = []
    logs = []
    try:
        for name in ('Alice', 'Bob'):
            path = root / name
            path.mkdir()
            out = path / 'out'
            out.mkdir()
            peerfile, presence = path / 'peers.txt', path / 'presence.json'
            peerfile.write_text('EWPEERS 1\n')
            env = dict(os.environ, EW_EXPANSION_PEERS=str(peerfile),
                       EW_EXPANSION_PRESENCE=str(presence), EW_EXPERIMENTAL_EXPANSION_PEERS='1')
            log = (path / 'stderr.log').open('w')
            logs.append(log)
            p = subprocess.Popen([str(binary), '--headless', '--silent', '--unthrottled',
                '--replay', str(script), '--out', str(out), '--save', str(path/'save.sav'),
                '--rtc-offset', str(path/'clock.rtc'), '--rtc-fixed', '1700000000'],
                stdout=subprocess.DEVNULL, stderr=log, env=env)
            profiles.append((name, peerfile, presence))
            processes.append(p)
        seen = [False, False]
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and not all(seen):
            states = []
            for _, _, presence in profiles:
                try:
                    state = json.loads(presence.read_text())
                except (FileNotFoundError, ValueError):
                    state = None
                states.append(state)
            for i in (0, 1):
                state, other = states[i], states[1-i]
                if state and state.get('field') and state.get('peers', 0) >= 1:
                    seen[i] = True
                if other and other.get('field'):
                    name, peerfile, _ = profiles[i]
                    other_name = profiles[1-i][0]
                    peer = {k: other[k] for k in ('group','num','x','y','facing','gfx')}
                    peer['ready'] = 0
                    temporary = peerfile.with_suffix('.tmp')
                    temporary.write_text(serialize_peers({'peers': {other_name: peer}}))
                    temporary.replace(peerfile)
            if any(p.poll() is not None and not seen[i] for i,p in enumerate(processes)):
                break
            time.sleep(.01)
        if not all(seen):
            for log in logs: log.flush()
            details = '\n'.join((root/name/'stderr.log').read_text()[-2000:] for name in ('Alice','Bob'))
            raise AssertionError(f'Dual-engine projection not observed by both clients: {seen}; states={states}\n{details}')
        print('Both independent native engines projected a peer from the other engine telemetry.')
    finally:
        for p in processes:
            if p.poll() is None: p.terminate()
        for p in processes:
            try: p.wait(timeout=5)
            except subprocess.TimeoutExpired: p.kill(); p.wait()
        for log in logs: log.close()
