"""Run Windows contracts with credential-free machine-readable outcomes."""
import argparse
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(ROOT/'test/world'), pattern='test_windows*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    outcomes = []
    for outcome, entries in [('failure', result.failures), ('error', result.errors)]:
        for test, _private_trace in entries:
            identifier = getattr(test, 'test_case', test).id()
            setup = re.fullmatch(r'(setUpClass|tearDownClass|setUpModule|tearDownModule) \(([A-Za-z_][A-Za-z0-9_.]{0,220})\)', identifier)
            if setup:
                identifier = setup[2] + '.' + setup[1]
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]{0,255}', identifier):
                outcomes.append({'test_id': identifier, 'outcome': outcome})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'passed': result.wasSuccessful(), 'run': result.testsRun,
        'skipped': len(result.skipped), 'outcomes': outcomes}, indent=2), encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
