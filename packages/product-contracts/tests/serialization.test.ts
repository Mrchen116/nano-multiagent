import { expect, it } from 'vitest';
import { sortedJsonAscii, sortedJsonUtf8 } from '@nano/product-contracts/serialization';

// Fixed outputs captured from a34af8473 before moving either implementation.
it('preserves distinct Unicode bytes, nested ordering and numeric keys', () => {
  const input = {"z":"\u4e2d\u6587\ud83d\ude00\u007f\u0080\u2028\ud800","a":{"b":2,"a":1},"arr":[{"z":"e\u0301","a":null},false,0],"keys":{"2":2,"10":10,"\u00e9":1,"e":2,"\u4e2d":3,"\ud83d\ude00":4,"\ue000":5}};
  expect(sortedJsonUtf8(input)).toBe("{\"a\":{\"a\":1,\"b\":2},\"arr\":[{\"a\":null,\"z\":\"e\u0301\"},false,0],\"keys\":{\"2\":2,\"10\":10,\"e\":2,\"\u00e9\":1,\"\u4e2d\":3,\"\ud83d\ude00\":4,\"\ue000\":5},\"z\":\"\u4e2d\u6587\ud83d\ude00\u007f\u0080\u2028\\ud800\"}");
  expect(sortedJsonAscii(input)).toBe("{\"a\":{\"a\":1,\"b\":2},\"arr\":[{\"a\":null,\"z\":\"e\\u0301\"},false,0],\"keys\":{\"2\":2,\"10\":10,\"e\":2,\"\\u00e9\":1,\"\\u4e2d\":3,\"\\ud83d\\ude00\":4,\"\\ue000\":5},\"z\":\"\\u4e2d\\u6587\\ud83d\\ude00\u007f\\u0080\\u2028\\ud800\"}");
});

it('preserves missing JSON fields, array slots and each encoder traversal', () => {
  const input = {z: undefined, a: [undefined, null, {z: undefined, b: 2, a: 1}]};
  for (const encode of [sortedJsonUtf8, sortedJsonAscii]) {
    expect(encode(input)).toBe('{"a":[null,null,{"a":1,"b":2}]}');
  }
  // The two legacy encoders differ before stringify, not just in escaping.
  const dated = {z: new Date('2026-01-02T00:00:00Z'), a: '中文'};
  expect(sortedJsonUtf8(dated)).toBe('{"a":"中文","z":"2026-01-02T00:00:00.000Z"}');
  expect(sortedJsonAscii(dated)).toBe('{"a":"\\u4e2d\\u6587","z":{}}');
});
