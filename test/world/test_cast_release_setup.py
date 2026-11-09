"""Paired draft pins and fail-before-claim author startup."""
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from world import runtime_gm as runtime,private_cast_worker
from scripts import build_expansion

class SetupTests(unittest.TestCase):
 def test_unreviewed_cli_does_not_open_or_claim_world_queue(self):
  with tempfile.TemporaryDirectory() as tmp:
   with patch('subprocess.check_output',return_value='codex-cli unreviewed'),patch.object(runtime,'RuntimeGM') as worker,contextlib.redirect_stdout(io.StringIO()) as out:
    self.assertEqual(runtime.main(['run','--state-dir',tmp,'--socket','unused','--model',runtime.MODEL,'--once']),1)
   worker.assert_not_called();self.assertEqual(list(Path(tmp).iterdir()),[])
   self.assertIn(runtime.CODEX_VERSION,json.loads(out.getvalue())['detail'])
 def test_private_worker_checks_before_claim_and_check_author_is_read_only(self):
  with patch('subprocess.check_output',return_value='codex-cli unreviewed'),patch.object(private_cast_worker,'step') as step,contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(private_cast_worker.main(['--socket','unused','--model',runtime.MODEL]),1)
  step.assert_not_called()
  with patch('subprocess.check_output',side_effect=[runtime.CODEX_VERSION,json.dumps(dict(models=[dict(slug='gpt-6-luna')]))]),contextlib.redirect_stdout(io.StringIO()) as out:
   self.assertEqual(runtime.main(['check-author']),0)
  self.assertFalse(json.loads(out.getvalue())['live_model_verified'])
 def test_missing_cli_error_does_not_reveal_external_details(self):
  with patch('subprocess.check_output',side_effect=OSError('SECRET diagnostic')):
   with self.assertRaises(runtime.AuthorPrerequisitesError) as error:runtime.preflight_author()
  self.assertNotIn('SECRET',str(error.exception))
 def test_builder_pin_matches_candidate_manifest(self):
  manifest=json.loads((Path(__file__).resolve().parents[2]/'engines/living-cast-candidate.json').read_text())
  self.assertEqual(build_expansion.PIN,manifest['native_revision'])
  self.assertFalse(manifest['linked_native_verified'])
