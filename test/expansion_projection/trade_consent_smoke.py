"""Run existing trade-consent regression against the generated donor overlay.

This compiles the actual generated functions in a stub harness. It does not
run a network session or claim that a complete trade is safe.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('patch_expansion_trade', ROOT/'scripts'/'patch_expansion_trade.py')
patcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(patcher)
spec = importlib.util.spec_from_file_location('existing_trade_tests', ROOT/'test'/'world'/'test_link_trade_payloads.py')
existing = importlib.util.module_from_spec(spec); spec.loader.exec_module(existing)
donor = (ROOT/'engines'/'expansion-native'/'src'/'trade.c').read_text()
vanilla = (ROOT/'src'/'trade.c').read_text()
source = patcher.generate(donor, vanilla)
# The reused harness defines PORTABLE and provides this stub under its old name.
source = source.replace('#if defined(PLATFORM_NATIVE)', '#ifdef PORTABLE')
source = source.replace('ExpansionLink_GetBlockReceivedSize(', 'GetBlockReceivedSize(')
with tempfile.TemporaryDirectory(prefix='expansion-trade-consent-') as tmp:
    root = Path(tmp); (root/'src').mkdir(); (root/'src'/'trade.c').write_text(source)
    existing.ROOT = root
    suite = unittest.TestSuite(existing.TradePayloads(name) for name in
        ('test_remote_cursor_rejected_before_assignment', 'test_native_confirm_cancel_wins_over_simultaneous_yes'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
