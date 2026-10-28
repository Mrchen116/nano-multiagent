/** Serialize sorted JSON while preserving Unicode for existing UTF-8 protocols.
 *
 * Args:
 *   value: JSON-serializable data. Objects are sorted recursively by UTF-16 key
 *     order; arrays keep their order. Native JSON toJSON handling is preserved.
 * Returns:
 *   Compact JSON without extra Unicode escaping. Numeric index keys retain
 *   JavaScript enumeration order. This is not RFC 8785 canonical JSON.
 * Throws:
 *   TypeError: Native JSON serialization rejects a cycle or BigInt.
 */
export function sortedJsonUtf8(value: unknown): string {
  return JSON.stringify(value, (_key, item) =>
    item && typeof item === 'object' && !Array.isArray(item)
      ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]]))
      : item,
  );
}

/** Preserve the sorted, non-ASCII-escaped JSON used by fingerprints and identities.
 *
 * Args:
 *   value: JSON data, recursively traversed before stringification. Unlike
 *     sortedJsonUtf8, this does not preserve native toJSON handling on objects.
 * Returns:
 *   Compact JSON with U+0080..FFFF escaped as lowercase UTF-16 units, including
 *   surrogate pairs. DEL (U+007F) is left intact. Arrays and numeric index keys
 *   keep JavaScript ordering; other keys use UTF-16 order, not locale collation.
 * Throws:
 *   TypeError: JSON serialization rejects BigInt or a non-serializable root.
 *   RangeError: The pre-traversal encounters a cyclic object.
 */
export function sortedJsonAscii(value: unknown): string {
  const sort = (value: unknown): unknown => Array.isArray(value) ? value.map(sort)
    : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, entry]) => [key, sort(entry)])) : value;
  return JSON.stringify(sort(value)).replace(/[\u0080-\uffff]/g, char => `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`);
}
