import assert from 'node:assert/strict';
import test from 'node:test';
import { saveImportLimit } from './save-import.js';
test('uses native header and regional extension capacity advertised by the bridge', () => {
  assert.equal(saveImportLimit({ save_import_max_bytes: 147524 }), 147524);
  assert.equal(saveImportLimit({ save_import_max_bytes: 131072 }), 131072);
});
test('uses a bounded legacy fallback for missing or malformed state', () => {
  for (const value of [undefined, null, -1, 0, 1.5, Infinity, '147524', 1048577])
    assert.equal(saveImportLimit({ save_import_max_bytes: value }), 131072);
  assert.equal(saveImportLimit(), 131072);
});
