/** Node-file authority for the selected memory implementation and maintenance budgets. */
export interface KnowledgeConfiguration {
  enabled?: boolean;
  globalSkillRoot?: string;
  memoryMode?: 'document' | 'legacy';
  legacyMemory?: {enabled?: boolean; interval?: number};
  /** maxInputTokens optionally caps materials inside the model-derived full input budget. */
  dreaming?: {
    nightlyHour?: number;
    intervalMs?: number;
    quietMs?: number;
    maxInputTokens?: number;
    minSourceTokens?: number;
    maxDeferDays?: number;
  };
  skillInterval?: number;
}

/** Default automatic maintenance timing, anchored at 03:00 local time after 30 minutes of quiet. */
export const DEFAULT_DREAMING_SCHEDULE = {
  nightlyHour: 3,
  intervalMs: 86400000,
  quietMs: 1800000,
  minSourceTokens: 600,
  maxDeferDays: 3,
} as const;

/** Normalize retired configuration keys at the file boundary, without granting tools.
 * Args:
 *   value: Agent-local knowledge settings, including old memoryInterval if present.
 *   features: Previous Feature selection before retired keys are removed.
 *   evolution: Historical workspace self_evolution settings.
 * Returns:
 *   File-owned settings with one explicit memory mode and legacy maintenance owner.
 */
export function normalizeKnowledge(value: unknown, features: Record<string, boolean> = {}, evolution: Record<string, unknown> = {}): KnowledgeConfiguration {
  const raw = value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
  const knowledge = raw as KnowledgeConfiguration;
  const mode = knowledge.memoryMode ?? 'document';
  if (mode !== 'document' && mode !== 'legacy') throw new Error('Invalid knowledge.memoryMode');
  for (const [key, settings] of [['legacyMemory', knowledge.legacyMemory], ['dreaming', knowledge.dreaming]] as const) {
    if (settings !== undefined && (!settings || typeof settings !== 'object' || Array.isArray(settings))) throw new Error(`Invalid knowledge.${key}`);
  }
  const interval = knowledge.legacyMemory?.interval ?? Number(raw.memoryInterval ?? evolution.memory_nudge_interval ?? 10);
  if (!Number.isFinite(interval) || interval < 0) throw new Error('Invalid knowledge.legacyMemory.interval');
  const dreaming = knowledge.dreaming === undefined ? undefined : Object.fromEntries(Object.entries(knowledge.dreaming).filter(([key]) => key !== 'maxSteps' && key !== 'maxRunMs'));
  for (const [key, number] of Object.entries(dreaming ?? {})) {
    const allowsZero = key === 'quietMs' || key === 'nightlyHour' || key === 'minSourceTokens';
    if (typeof number !== 'number' || !Number.isFinite(number) || number < 0 || (!allowsZero && number === 0)
      || (key === 'nightlyHour' && (!Number.isInteger(number) || number > 23))
      || (key === 'maxDeferDays' && (!Number.isInteger(number) || number < 1))) throw new Error(`Invalid knowledge.dreaming.${key}`);
  }
  return {
    ...(knowledge.globalSkillRoot === undefined ? {} : {globalSkillRoot:knowledge.globalSkillRoot}),
    enabled: knowledge.enabled ?? evolution.enabled !== false,
    memoryMode: mode,
    legacyMemory: {enabled: knowledge.legacyMemory?.enabled ?? features.memory_curation ?? evolution.memory_curation !== false, interval},
    ...(dreaming === undefined ? {} : {dreaming}),
    ...(knowledge.skillInterval === undefined ? {} : {skillInterval:knowledge.skillInterval}),
  };
}
