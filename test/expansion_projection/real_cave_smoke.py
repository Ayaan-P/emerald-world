"""Disposable donor replay of offline generated-cave entry and exit.

No sockets are created. Uses an inert EWGMAP01 template and a local file.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

binary = Path(sys.argv[1]).resolve(strict=True)
donor = Path(sys.argv[2]).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='expansion-cave-smoke-') as directory:
    root = Path(directory)
    cells = bytearray(b'#' * (31 * 31))
    for y in range(1, 30): cells[y * 31 + 1] = ord('.')
    for x in range(1, 30): cells[28 * 31 + x] = ord('.')
    cells[29 * 31 + 29] = ord('.')
    template = root / 'cave.bin'
    template.write_bytes(b'EWGMAP01' + cells)
    script = root / 'cave.replay'
    script.write_text((donor / 'tests/smoke/opening_start.replay').read_text() + '''\nwait 30
press SELECT,R
wait-until map=75.0 max 900
wait-until callback2=CB2_Overworld max 900
wait 30
press SELECT,R
wait-until map=0.9 max 900
wait-until callback2=CB2_Overworld max 900
wait 30
''')
    out = root / 'out'
    out.mkdir()
    env = dict(os.environ, EW_EXPERIMENTAL_EXPANSION_CAVE='1', EW_EXPANSION_OFFLINE='1',
               EW_EXPANSION_CAVE_TEMPLATE=str(template))
    p = subprocess.run([str(binary), '--headless', '--silent', '--unthrottled',
        '--replay', str(script), '--out', str(out), '--save', str(root / 'game.sav'),
        '--rtc-offset', str(root / 'clock.rtc'), '--rtc-fixed', '1700000000'],
        env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240)
    if p.returncode:
        raise AssertionError('Donor cave replay failed: ' + p.stderr[-5000:])
    print('Entered and left an inert generated cave in the Expansion donor.')
