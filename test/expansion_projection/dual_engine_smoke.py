"""Run two Expansion processes with an in-memory/file presence relay.

This does not use the world server or any sockets and is not a network test.
It uses the production world authority and client parser in memory, checks
independent engines consume each other's positions and instantiate peers. Saves are disposable.
"""
import json
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from world.expansion import serialize_peers
from world.server import WorldServer
from world.client import WorldClient

binary = Path(sys.argv[1]).resolve(strict=True)
donor = Path(sys.argv[2]).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='expansion-dual-') as temp:
    root = Path(temp)
    script = root / 'two-clients.replay'
    script.write_text((donor / 'tests/smoke/opening_start.replay').read_text() + '\nwait 4000\n')
    server = WorldServer(str(root/'unused.sock'), root/'world')
    conns = []
    for name in ('Alice', 'Bob'):
        token = server.create_identity(name)['token']
        conn = dict(sock=object(), id=None, seq=-1, state=None, incoming=bytearray(),
                    out=bytearray(), closing=False, born=time.monotonic(), admin=False)
        server._line(conn, f'HELLO 1 {name} {token} SOCIAL'.encode())
        if conn.get('id') != name or conn.get('closing'):
            raise AssertionError('in-memory social authentication failed')
        conn['out'].clear()
        conns.append(conn)
    sequences = [0, 0]
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
                if state and state.get('field'):
                    sequences[i] += 1
                    values = [sequences[i], *(state[k] for k in ('group','num','x','y','facing','gfx')), 0]
                    message = 'FIELD ' + ' '.join(map(str, values)) + ' ' + '0'*16 + ' ' + '0'*16
                    server._line(conns[i], message.encode('ascii'))
                    if conns[i].get('closing'):
                        raise AssertionError('world authority rejected Expansion presence')
                # Use the actual authority snapshot and production client parser;
                # the test substitutes only an in-memory wire for network I/O.
                client = WorldClient.__new__(WorldClient)
                client.stream = io.BytesIO(server._snapshot(conns[i]).encode('ascii'))
                client.control = False
                client.social = True
                client.trainer_id = profiles[i][0]
                snapshot = client.snapshot()
                peerfile = profiles[i][1]
                temporary = peerfile.with_suffix('.tmp')
                temporary.write_text(serialize_peers(snapshot))
                temporary.replace(peerfile)
                conns[i]['out'].clear()
            if any(p.poll() is not None and not seen[i] for i,p in enumerate(processes)):
                break
            time.sleep(.01)
        if not all(seen):
            for log in logs: log.flush()
            details = '\n'.join((root/name/'stderr.log').read_text()[-2000:] for name in ('Alice','Bob'))
            raise AssertionError(f'Dual-engine projection not observed by both clients: {seen}; states={states}\n{details}')
        print('Both native engines exchanged presence through the real in-memory world authority.')
    finally:
        for p in processes:
            if p.poll() is None: p.terminate()
        for p in processes:
            try: p.wait(timeout=5)
            except subprocess.TimeoutExpired: p.kill(); p.wait()
        for log in logs: log.close()
        server.close()
