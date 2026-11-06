"""Trade overlay preserves explicit pair consent and fails closed on source drift."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('patch_expansion_trade', ROOT/'scripts'/'patch_expansion_trade.py')
patcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(patcher)

class TradeOverlayTests(unittest.TestCase):
    def sources(self):
        donor=ROOT/'engines'/'expansion-native'/'src'/'trade.c'
        if not donor.exists(): self.skipTest('donor submodule not present')
        return donor.read_text(), (ROOT/'src'/'trade.c').read_text()
    def test_payload_and_exact_pair_consent_guards(self):
        donor, vanilla = self.sources(); result=patcher.generate(donor, vanilla)
        self.assertEqual(result.count('!NativeTradePartyBlockValid(id ^ 1)'),3)
        self.assertIn('ExpansionTrade_PairValid(gBlockRecvBuffer[peer], 200)',result)
        self.assertIn('sTradeMenu->nativeConfirmedPlayer != sTradeMenu->cursorPosition',result)
        self.assertIn('sTradeMenu->nativeConfirmedPartner != sTradeMenu->partnerCursorPosition',result)
        self.assertIn('playerPartyIdx >= gPartiesCount[B_TRAINER_PLAYER]',result)
        self.assertIn('partnerPartyIdx >= gPartiesCount[B_TRAINER_OPPONENT_A]',result)
        self.assertEqual(result.count('if (LinkFullSave_SetLastSectorSignature()) break;'),2)
    def test_changed_donor_is_rejected(self):
        donor, vanilla = self.sources()
        changed=donor.replace('    u8 partnerConfirmStatus;\n    u8 filler_7C[2];','',1)
        self.assertNotEqual(changed,donor)
        with self.assertRaises(ValueError): patcher.generate(changed,vanilla)

if __name__ == '__main__': unittest.main()
