import { expect, it } from 'vitest';
import { encodeTrajectoryValue, TrajectoryValueDecoder, TRAJECTORY_MAX_BYTES } from '../src/index.js';

it('keeps physical JSON messages bounded and restores interleaved Unicode responses losslessly', () => {
  const values = ['one', 'two'].map(requestId => ({ type: 'result', observerId: 'reader', requestId,
    value: { records: [{ text: '中文😀"\\\n'.repeat(140_000) }] } }));
  const fragments = values.map(value => [...encodeTrajectoryValue(value)]), decoder = new TrajectoryValueDecoder();
  const restored: unknown[] = [];
  expect(fragments[0].length).toBeGreaterThan(2);
  for (let i = 0; i < fragments[0].length; i++) {
    for (const parts of fragments) {
      const part = parts[i];
      expect(Buffer.byteLength(JSON.stringify(part))).toBeLessThan(TRAJECTORY_MAX_BYTES - 1024);
      const value = decoder.push(JSON.parse(JSON.stringify(part)));
      if (value !== undefined) restored.push(value);
    }
  }
  decoder.finish();
  expect(restored).toEqual(values);
  expect([...encodeTrajectoryValue({ small: true })]).toEqual([{ small: true }]);
});

it('rejects incomplete transfers, gaps, and changes of observer identity', () => {
  const parts = [...encodeTrajectoryValue({ observerId: 'a', value: 'x'.repeat(2_000_000) })] as any[];
  const decoder = new TrajectoryValueDecoder();
  expect(() => decoder.push(parts[1])).toThrow('out_of_order');
  decoder.push(parts[0]);
  expect(() => decoder.push(parts[0])).toThrow('out_of_order');
  expect(() => decoder.push({ ...parts[1], observerId: 'b' })).toThrow('out_of_order');
  expect(() => decoder.finish()).toThrow('incomplete');
  decoder.clear();
  decoder.finish();
});
