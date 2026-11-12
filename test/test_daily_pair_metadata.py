"""All active paired metadata must identify the actual selected native cohort."""
import json,subprocess,unittest
from pathlib import Path
from scripts import build_expansion
ROOT=Path(__file__).resolve().parents[1]
class PairedMetadataTests(unittest.TestCase):
    def test_all_active_native_metadata_matches_selected_gitlink(self):
        selected=subprocess.check_output(['git','-C',str(ROOT/'engines/expansion-native'),'rev-parse','HEAD'],text=True).strip()
        self.assertEqual(build_expansion.PIN,selected)
        for name,field in [('engines/living-cast-candidate.json','native_revision'),('world/encounter_traits.json','engine_commit'),('world/native_resident_sites.json','engine_commit'),('world/safari_feeders.json','native_commit')]:
            with self.subTest(resource=name):
                self.assertEqual(json.loads((ROOT/name).read_text())[field],selected)
