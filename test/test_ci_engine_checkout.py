"""Exercise the private checkout contract without reading any credentials."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/main-baseline.yml'


def focused_steps():
    text = WORKFLOW.read_text().split('  linux-build:', 1)[0]
    return [part for part in text.split('      - name: ')[1:]]


def run_script(step):
    if '        run: |\n' not in step:
        return step.split('        run: ', 1)[1].strip()
    return '\n'.join(
        line[10:] for line in step.split('        run: |\n', 1)[1].splitlines())


class EngineCheckout(unittest.TestCase):
    def test_prerequisite_fails_closed_without_disclosing_input(self):
        step = next(s for s in focused_steps() if s.startswith('Require explicitly'))
        self.assertIn('EW_ENGINE_READ_KEY: ${{ secrets.EW_ENGINE_READ_KEY }}', step)
        for value, expected in (('', 1), ('non-secret-presence-probe', 0)):
            result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', run_script(step)],
                                    env={**os.environ, 'EW_ENGINE_READ_KEY': value},
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, expected)
            self.assertNotIn('non-secret-presence-probe', result.stdout + result.stderr)
            if not value:
                self.assertIn('::error::Configure EW_ENGINE_READ_KEY', result.stdout)
                self.assertIn('Fork pull requests', result.stdout)

    def test_pin_step_accepts_only_a_committed_gitlink(self):
        step = next(s for s in focused_steps() if s.startswith('Read the committed engine pin'))
        script = run_script(step)
        expected = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD:engines/expansion-native'], cwd=ROOT, text=True).strip()
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            output = temporary / 'output'
            env = {**os.environ, 'GITHUB_OUTPUT': str(output)}
            valid = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script],
                                   cwd=ROOT, env=env, text=True, capture_output=True)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertEqual(output.read_text(), f'sha={expected}\n')
            for kind in ('missing', 'blob'):
                repo = temporary / kind
                repo.mkdir()
                subprocess.run(['git', 'init', '-q', str(repo)], check=True)
                if kind == 'blob':
                    path = repo / 'engines/expansion-native'
                    path.parent.mkdir()
                    path.write_text('not a submodule\n')
                    subprocess.run(['git', 'add', '.'], cwd=repo, check=True)
                subprocess.run(['git', '-c', 'user.name=CI test', '-c',
                                'user.email=ci@example.invalid', 'commit', '-qm',
                                'metadata fixture', '--allow-empty'], cwd=repo, check=True)
                output.unlink(missing_ok=True)
                result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script],
                                        cwd=repo, env=env, text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0, kind)
                self.assertFalse(output.exists(), kind)
                self.assertIn('::error::', result.stdout + result.stderr)

    def test_scoped_key_only_used_for_exact_private_checkout(self):
        steps = focused_steps()
        root = steps[0]
        self.assertIn('submodules: false', root)
        self.assertIn('persist-credentials: false', root)
        self.assertNotIn('ssh-key:', root)
        private = next(s for s in steps if 'repository: Ayaan-P/pokeemerald-expansion-native' in s)
        self.assertIn('ssh-key: ${{ secrets.EW_ENGINE_READ_KEY }}', private)
        self.assertNotIn('token:', private)
        self.assertIn('ref: ${{ steps.engine-pin.outputs.sha }}', private)
        self.assertIn('path: engines/expansion-native', private)
        self.assertIn('persist-credentials: false', private)
        self.assertIn('ssh-strict: true', private)
        self.assertNotIn('ENGINE_SOURCE_READ_TOKEN', WORKFLOW.read_text())
        self.assertNotIn('pull_request_target', WORKFLOW.read_text())
        for step in steps[:4]:
            self.assertNotIn('if:', step)
            self.assertNotIn('continue-on-error:', step)


if __name__ == '__main__':
    unittest.main(verbosity=2)
