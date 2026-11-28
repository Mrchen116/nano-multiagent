import { describe, expect, it } from 'vitest';
import { canonicalAgentConfiguration, DEFAULT_DREAMING_SCHEDULE, normalizeKnowledge } from '../src/index.js';

describe('KnowledgeConfiguration dreaming volume and deferral defaults', () => {
  it('exposes minSourceTokens=600 and maxDeferDays=3 in DEFAULT_DREAMING_SCHEDULE without mutating unset configs', () => {
    expect(DEFAULT_DREAMING_SCHEDULE).toEqual({
      nightlyHour: 3,
      intervalMs: 86400000,
      quietMs: 1800000,
      minSourceTokens: 600,
      maxDeferDays: 3,
    });
    const normalized = normalizeKnowledge({});
    expect(normalized.dreaming).toBeUndefined();
    const base = {
      agentId: 'pa_1',
      revision: '1',
      mode: 'global' as const,
      provider: 'openai',
      model: 'gpt-5',
      knowledge: normalized,
    };
    expect(canonicalAgentConfiguration(base)).toStrictEqual(canonicalAgentConfiguration({ ...base, knowledge: undefined }));
  });

  it('accepts minSourceTokens=0 and positive integer maxDeferDays while rejecting invalid bounds', () => {
    expect(normalizeKnowledge({ dreaming: { minSourceTokens: 0, maxDeferDays: 1, nightlyHour: 0, quietMs: 0 } }).dreaming).toEqual({
      minSourceTokens: 0,
      maxDeferDays: 1,
      nightlyHour: 0,
      quietMs: 0,
    });
    expect(() => normalizeKnowledge({ dreaming: { minSourceTokens: -1 } })).toThrow('Invalid knowledge.dreaming.minSourceTokens');
    expect(() => normalizeKnowledge({ dreaming: { maxDeferDays: 0 } })).toThrow('Invalid knowledge.dreaming.maxDeferDays');
    expect(() => normalizeKnowledge({ dreaming: { maxDeferDays: 1.5 } })).toThrow('Invalid knowledge.dreaming.maxDeferDays');
  });
});
