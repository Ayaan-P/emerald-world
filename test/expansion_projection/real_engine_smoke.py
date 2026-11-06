"""Run the donor's real opening replay with one file-fed experimental peer.

No network is used. The simulated peer remains fresh while the unthrottled
replay runs. This checks actual object allocation, not real multiplayer or
save safety. Use only disposable output and save files.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

binary = Path(sys.argv[1]).resolve(strict=True)
donor = Path(sys.argv[2]).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='expansion-peer-smoke-') as directory:
    root = Path(directory)
    peers = root / 'peers.txt'
    presence = root / 'presence.json'
    out = root / 'out'
    out.mkdir()
    peers.write_text('EWPEERS 1\nTestPeer 0 9 10 11 2 0\n', encoding='ascii')
    stop = threading.Event()
    def keep_fresh():
        while not stop.wait(1):
            os.utime(peers, None)
    thread = threading.Thread(target=keep_fresh, daemon=True)
    thread.start()
    env = dict(os.environ, EW_EXPANSION_PEERS=str(peers),
               EW_EXPANSION_PRESENCE=str(presence), EW_EXPERIMENTAL_EXPANSION_PEERS='1')
    try:
        result = subprocess.run([str(binary), '--headless', '--silent', '--unthrottled',
            '--replay', str(donor / 'tests/smoke/opening_start.replay'), '--out', str(out),
            '--save', str(root / 'save.sav'), '--rtc-offset', str(root / 'clock.rtc'),
            '--rtc-fixed', '1700000000'], env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=180)
    finally:
        stop.set()
        thread.join()
    if result.returncode:
        raise RuntimeError('opening replay failed:\n' + result.stderr[-4000:])
    state = json.loads(presence.read_text())
    if (state.get('field') is not True or state.get('group') != 0 or state.get('num') != 9
            or state.get('peers') != 1):
        raise AssertionError('expected one actual peer object in Littleroot: ' + repr(state))
    print('Actual donor replay projected one peer object in Littleroot.')
