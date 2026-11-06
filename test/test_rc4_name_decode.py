"""Save evidence must preserve native punctuation in imported species names."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'test/headless'))
from savecheck import decode_text


class NativeNameDecodeTests(unittest.TestCase):
    def test_type_null_colon_is_not_reported_as_question_mark(self):
        # charmap.txt defines ':' as F0. Name remains native encoded bytes.
        encoded = bytes(0xBB + ord(c) - ord('A') if 'A' <= c <= 'Z'
                        else 0 if c == ' ' else 0xF0 for c in 'TYPE: NULL')
        self.assertEqual(decode_text(encoded + b'\xff'), 'TYPE: NULL')


if __name__ == '__main__':
    unittest.main()
