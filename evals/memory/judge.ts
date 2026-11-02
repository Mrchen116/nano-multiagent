import { readFileSync } from 'node:fs';
import type { EvaluationLimits, EvaluationUsage } from '@nano/product-contracts';
import { digest, QUESTION_TYPES, type GoldRecord } from './dataset.js';

const official = JSON.parse(readFileSync(new URL('./judge-prompts.json', import.meta.url), 'utf8')) as {
  source: string; gitBlob: string; templates: Record<string, string>;
};
export const judgeIdentity = { source: official.source, gitBlob: official.gitBlob, promptHash: digest(official.templates), implementationHash: digest(readFileSync(new URL('./judge.ts', import.meta.url), 'utf8')) };
export type ScoreResult = { status: 'completed'; correct: boolean; raw: string; usage: EvaluationUsage }
  | { status: 'failed'; reason: string; raw?: string; usage?: EvaluationUsage };
export type Judge = (gold: GoldRecord, answer: string, limits: EvaluationLimits) => Promise<ScoreResult>;
export interface JudgeConfiguration { baseURL: string; apiKeyEnv: string; model: string }

/** Apply the frozen official template without modifying question, gold or hypothesis. */
export function judgePrompt(gold: GoldRecord, answer: string): string {
  if (!QUESTION_TYPES.some(type => type === gold.type)) throw new Error(`Unsupported question type: ${gold.type}`);
  const key = gold.abstention ? 'abstention' : Object.hasOwn(official.templates, gold.type) ? gold.type : 'default';
  const values = [gold.question, gold.answer, answer];
  return official.templates[key].replace(/\{\}/g, () => values.shift()!);
}

/** Construct the live judge only after the CLI has received explicit execution permission. */
export function createJudge(config: JudgeConfiguration, allowModelCalls = false, signal?: AbortSignal): Judge {
  if (!allowModelCalls) throw new Error('Judge model calls require --allow-model-calls');
  return async (gold, answer, limits) => {
    const started = Date.now();
    const key = process.env[config.apiKeyEnv];
    if (!key) return { status: 'failed', reason: `Missing judge credential environment variable: ${config.apiKeyEnv}` };
    const usage: EvaluationUsage = { modelCalls: 0, inputTokens: null, outputTokens: null, costUsd: null, elapsedMs: 0 };
    try {
      usage.modelCalls++;
      const response = await fetch(`${config.baseURL.replace(/\/$/, '')}/chat/completions`, {
        method: 'POST', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(limits.timeoutMs)]) : AbortSignal.timeout(limits.timeoutMs),
        headers: { 'content-type': 'application/json', authorization: `Bearer ${key}` },
        body: JSON.stringify({ model: config.model, messages: [{ role: 'user', content: judgePrompt(gold, answer) }],
          n: 1, temperature: 0, max_tokens: Math.min(10, limits.maxOutputTokens) }),
      });
      if (!response.ok) throw new Error(`Judge HTTP ${response.status}`);
      const body = await response.json() as { choices?: { message?: { content?: string } }[]; usage?: { prompt_tokens?: number; completion_tokens?: number } };
      const raw = body.choices?.[0]?.message?.content;
      if (typeof raw !== 'string' || !raw.trim()) throw new Error('Judge returned no text');
      usage.inputTokens = body.usage?.prompt_tokens ?? null;
      usage.outputTokens = body.usage?.completion_tokens ?? null;
      usage.elapsedMs = Date.now() - started;
      // Keep the official evaluator's yes-substring rule; preserve raw text for audit.
      return { status: 'completed', correct: raw.trim().toLowerCase().includes('yes'), raw, usage };
    } catch (error) {
      usage.elapsedMs = Date.now() - started;
      return { status: 'failed', reason: String(error), usage };
    }
  };
}
