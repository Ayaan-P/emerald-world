"""Bound a verification subprocess and emit only non-secret status JSON.

Raw stdout/stderr is retained beside the report as .private.log, never uploaded.
On Windows the complete process tree is terminated on timeout, including game
processes launched by the smoke driver. CI also imposes per-step/job deadlines.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', choices=['unit', 'smoke', 'bridge', 'source-self-test', 'frozen-self-test', 'freeze', 'package'], required=True)
    parser.add_argument('--timeout', type=int, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or not 0 < args.timeout <= 1800:
        parser.error('A command and timeout of 1..1800 seconds are required')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    timed_out = False
    started = time.monotonic()
    code = -1
    with args.report.with_suffix('.private.log').open('wb') as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=os.name != 'nt')
        try:
            code = proc.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            else:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.kill()
            proc.wait(timeout=15)
    args.report.write_text(json.dumps({'label': args.label, 'passed': code == 0 and not timed_out,
        'timed_out': timed_out, 'exit_code': code, 'seconds': round(time.monotonic() - started, 2)}, indent=2) + '\n', encoding='utf-8')
    print(f'{args.label}: ' + ('PASS' if code == 0 and not timed_out else 'FAIL (see runner-local private log)'))
    return 0 if code == 0 and not timed_out else 1


if __name__ == '__main__':
    raise SystemExit(main())
