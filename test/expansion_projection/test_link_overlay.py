"""The pinned-donor link overlay must fail closed when its seam changes."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'scripts'/'patch_expansion_link.py'
spec = importlib.util.spec_from_file_location('patch_expansion_link', SCRIPT)
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)

class OverlayTests(unittest.TestCase):
    def source(self):
        donor = ROOT/'engines'/'expansion-native'/'src'/'link.c'
        if not donor.exists():
            self.skipTest('donor submodule is not checked out')
        return donor.read_text(), (ROOT/'src'/'link.c').read_text()
    def test_hooks_and_validation_are_present(self):
        donor, vanilla = self.source()
        result = patcher.generate(donor, vanilla)
        self.assertIn('NativeLink_Main1(shouldAdvanceLinkState, sendCmd, recvCmds)', result)
        self.assertIn('sNativePlayerExchangeRequested', result)
        self.assertIn('NativeLink_SetCommandSource(gSendCmd)', result)
        self.assertIn('gRecvCmds[i][1] >= ARRAY_COUNT(sBlockRequests)', result)
        self.assertNotIn('gDecompressionBuffer', result)
    def test_changed_donor_fails_closed(self):
        donor, vanilla = self.source()
        changed = donor.replace('        ResetSerial();\n        InitLink();\n        gLinkCallback = LinkCB_RequestPlayerDataExchange;', '', 1)
        self.assertNotEqual(changed, donor)
        with self.assertRaises(ValueError): patcher.generate(changed, vanilla)

if __name__ == '__main__': unittest.main()
