// The selected engine advertises its opaque-file copy bound. Compatibility is
// still checked by the native loader; this must never trim or reinterpret bytes.
export function saveImportLimit(state) {
  const limit = state?.save_import_max_bytes;
  return Number.isSafeInteger(limit) && limit > 0 && limit <= 1048576 ? limit : 131072;
}
