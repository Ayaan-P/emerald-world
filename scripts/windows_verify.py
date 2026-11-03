"""Bound a verification subprocess and emit only non-secret status JSON.

Raw stdout/stderr is retained beside the report as .private.log, never uploaded.
On Windows the complete process tree is terminated on timeout, including game
processes launched by the smoke driver. CI also imposes per-step/job deadlines.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


# These are metadata grammars, not a log sanitizer. Unknown formats stay private.
_EXCEPTION_TYPES = frozenset({
    'Exception', 'RuntimeError', 'AssertionError', 'ValueError', 'TypeError',
    'AttributeError', 'KeyError', 'IndexError', 'ImportError', 'ModuleNotFoundError',
    'OSError', 'FileNotFoundError', 'PermissionError', 'TimeoutError',
    'NotImplementedError', 'NameError', 'UnboundLocalError', 'ZeroDivisionError',
    'OverflowError', 'MemoryError', 'RecursionError', 'UnicodeError',
    'UnicodeDecodeError', 'UnicodeEncodeError', 'SystemError',
})
_FRAME = re.compile(r'  File "([^"\r\n]{1,512})", line ([1-9][0-9]{0,6}), in [^\r\n]{1,120}')
_SOURCE = re.compile(r'(?:world/[A-Za-z_][A-Za-z0-9_/]*|scripts/windows[A-Za-z0-9_]*|test/[A-Za-z_][A-Za-z0-9_/]*)\.py')


def failure_diagnostics(log_path):
    """Read only a bounded tail and export known source locations/types."""
    root = Path(__file__).resolve().parents[1]
    try:
        with log_path.open('rb') as log:
            log.seek(0, os.SEEK_END)
            offset = max(0, log.tell() - 65536)
            log.seek(offset)
            tail = log.read(65536)
        if offset:
            tail = tail.partition(b'\n')[2]
        text = tail.decode('utf-8', errors='replace')
    except OSError:
        return []
    diagnostics = []
    frames = None
    for line in text.splitlines():
        test = re.fullmatch(r'(ERROR|FAIL): (test_[A-Za-z0-9_]{1,64}) \(([A-Za-z_][A-Za-z0-9_.]{1,119})\)', line)
        if (test and test[3].split('.')[-1] == test[2]
                and all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', part)
                        for part in test[3].split('.'))
                and not re.search(r'[0-9a-fA-F]{16,}', test[3])
                and 'DO_NOT_PUBLISH' not in test[3]):
            diagnostics.append({'test_id': test[3], 'outcome': test[1]})
            if len(diagnostics) == 32:
                return diagnostics
            frames = None
            continue
        if line == 'Traceback (most recent call last):':
            frames = []
            continue
        if frames is None:
            continue
        match = _FRAME.fullmatch(line)
        if match:
            source = match[1].replace('\\', '/')
            prefix = root.as_posix() + '/'
            if source.startswith(prefix):
                source = source[len(prefix):]
            if (len(source) <= 160 and _SOURCE.fullmatch(source)
                    and not re.search(r'[0-9a-fA-F]{16,}', source)
                    and 'DO_NOT_PUBLISH' not in source
                    and all(part not in ('', '.', '..') for part in source.split('/'))
                    and (root / source).is_file()):
                if len(frames) < 32:
                    frames.append({'file': source, 'line': int(match[2])})
            continue
        exception_type = line.partition(':')[0]
        if exception_type in _EXCEPTION_TYPES:
            entries = frames or [{}]
            for frame in entries:
                if len(diagnostics) == 32:
                    return diagnostics
                diagnostics.append(dict(frame, exception_type=exception_type))
            frames = None
        elif line and not line.startswith(' '):
            frames = None
    return diagnostics


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
    report = {'label': args.label, 'passed': code == 0 and not timed_out,
              'timed_out': timed_out, 'exit_code': code,
              'seconds': round(time.monotonic() - started, 2)}
    if not report['passed']:
        diagnostics = failure_diagnostics(args.report.with_suffix('.private.log'))
        if diagnostics:
            report['diagnostics'] = diagnostics
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'{args.label}: ' + ('PASS' if code == 0 and not timed_out else 'FAIL (see runner-local private log)'))
    return 0 if code == 0 and not timed_out else 1


if __name__ == '__main__':
    raise SystemExit(main())
