import { onTestFinished } from 'vitest';

/** Record elapsed wall time per integration phase, including the phase at timeout. */
export function trackTestPhases(firstPhase: string) {
  const phases = [{ name: firstPhase, start: performance.now() }];
  onTestFinished(() => {
    const end = performance.now();
    const timings = phases.map(({ name, start }, index) => ({
      phase: name,
      elapsedMs: Math.round((phases[index + 1]?.start ?? end) - start),
    }));
    console.info('[test-phases]', JSON.stringify(timings));
  });
  return (name: string) => {
    phases.push({ name, start: performance.now() });
  };
}
