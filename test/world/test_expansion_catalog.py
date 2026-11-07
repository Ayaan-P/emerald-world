"""Species labels must come from the selected engine, never a second roster."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class ExpansionCatalogTests(unittest.TestCase):
    def test_labels_preserve_engine_enum_identity_without_recalculating_ids(self):
        script = ROOT / 'scripts/export_expansion_species_names.py'
        self.assertTrue(script.is_file(), 'engine species-name exporter is missing')
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            source = p / 'species.h'
            source.write_text('enum Species {\n SPECIES_NONE = 0,\n SPECIES_BULBASAUR = 1,\n SPECIES_FUTURE_FORM = SPECIES_BULBASAUR + 1200,\n};\n')
            output = p / 'names.h'
            subprocess.run([sys.executable, str(script), str(source), str(output)], check=True)
            text = output.read_text()
            self.assertIn('[SPECIES_FUTURE_FORM] = "FUTURE_FORM"', text)
            self.assertNotIn('1201', text)
            self.assertIn('[SPECIES_BULBASAUR] = "BULBASAUR"', text)

if __name__ == '__main__':
    unittest.main()
