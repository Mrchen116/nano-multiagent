import { expect, it } from 'vitest';
import type { ModelRun } from '../src/model-fallback.js';
import { ModelRunIndex } from '../src/model-run-index.js';

it('preserves restored insertion order when an earlier ModelRun later acquires the same input', () => {
  const run = (turn: number, inputs: string[]): ModelRun => ({
    id: `root:${turn}`, sessionId: 'root', revision: '1', turn, inputs,
    attempts: [{turn, route: {provider: 'test', model: 'test'}}], state: 'running',
  });
  const earlier = run(3, []), later = run(1, ['shared']);
  // Sidecar iteration order is independent of native turn order.
  const restored = [earlier, later];
  const index = new ModelRunIndex();
  for (const item of restored) index.update(item);
  earlier.inputs.push('shared', 'unique');
  earlier.state = 'completed';
  index.update(earlier);
  for (const id of ['shared', 'unique', 'unknown'])
    expect(index.forInput(id)).toBe(restored.findLast(item => item.inputs.includes(id)));
  expect(index.latestActive(() => true)).toBe(later);
  expect(index.forAttempt(3)).toBe(earlier);
});
