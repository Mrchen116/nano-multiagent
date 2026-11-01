import { mkdir, readFile, writeFile, rename } from 'node:fs/promises';
import { join } from 'node:path';
import type { EvaluationAnswer, EvaluationLimits, MemoryCandidate, PreparationResult } from '@nano/product-contracts';
import { digest, type EvaluationCase, type GoldRecord } from './dataset.js';
import type { Judge, ScoreResult } from './judge.js';

export interface EvaluationPlan {
  protocolId: string; candidateId: string; datasetHash: string; selectedIds: string[];
  [key: string]: unknown;
}
export interface PhaseLimits { prepare: EvaluationLimits; answer: EvaluationLimits; score: EvaluationLimits }
export interface CaseResult {
  questionId: string; questionType: string; abstention: boolean; caseKey: string;
  prepare: PreparationResult | { status: 'not_run'; reason?: string };
  answer: EvaluationAnswer | { status: 'not_run' };
  score: ScoreResult | { status: 'not_run' };
  cleanupError?: string;
  scoreAttempts?: ScoreResult[];
}

class DeadlineError extends Error {}

/** Bound awaited adapter work; close remains a separate mandatory cleanup barrier. */
async function deadline<T>(work: Promise<T>, timeoutMs: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([work, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new DeadlineError(`Evaluation deadline exceeded (${timeoutMs}ms)`)), timeoutMs);
    })]);
  } finally { clearTimeout(timer); }
}

/** Stop at the deadline, then collect the adapter's cancellation receipt when available. */
async function candidatePhase<T>(work: Promise<T>, timeoutMs: number, candidate: MemoryCandidate): Promise<T> {
  try { return await deadline(work, timeoutMs); }
  catch (error) {
    if (!(error instanceof DeadlineError)) throw error;
    await deadline(candidate.close(), 5000);
    try { return await deadline(work, 100); } catch { throw error; }
  }
}

/** Preserve the planned denominator and separately report the scored subset. */
export function summarize(results: readonly CaseResult[]) {
  const count = (rows: readonly CaseResult[]) => {
    const scored = rows.filter(row => row.score.status === 'completed');
    const correct = scored.filter(row => row.score.status === 'completed' && row.score.correct).length;
    return { planned: rows.length, scored: scored.length, correct, accuracy: scored.length ? correct / scored.length : null,
      correctPerPlanned: rows.length ? correct / rows.length : null };
  };
  return { ...count(results),
    byType: Object.fromEntries([...new Set(results.map(row => row.questionType))].map(type => [type, count(results.filter(row => row.questionType === type))])),
    abstention: count(results.filter(row => row.abstention)),
    incomplete: results.filter(row => row.prepare.status === 'incomplete').length,
    preparationFailed: results.filter(row => row.prepare.status === 'failed').length,
    answerFailed: results.filter(row => row.answer.status === 'failed').length,
    judgeFailed: results.filter(row => row.score.status === 'failed').length,
    notScored: results.filter(row => row.score.status === 'not_run').length,
  };
}

async function save(output: string, plan: EvaluationPlan, results: CaseResult[]) {
  const report = { plan, summary: summarize(results), results };
  await writeFile(join(output, 'report.json.tmp'), JSON.stringify(report, null, 2) + '\n');
  await rename(join(output, 'report.json.tmp'), join(output, 'report.json'));
  const answers = results.flatMap(row => row.answer.status === 'completed' ? [{ question_id: row.questionId, hypothesis: row.answer.text }] : []);
  await writeFile(join(output, 'answers.jsonl'), answers.map(row => JSON.stringify(row) + '\n').join(''));
  return report;
}

/** Run selected cases sequentially without exposing questions or gold to preparation.
 *
 * Args:
 *   options: Frozen plan, complete cases, candidate, independent judge, limits and empty output directory.
 * Returns:
 *   The persisted report including failed and incomplete cases.
 */
export async function runEvaluation(options: {
  cases: EvaluationCase[]; plan: EvaluationPlan; output: string; candidate: MemoryCandidate; judge: Judge; limits: PhaseLimits; signal?: AbortSignal;
}) {
  const { cases, plan, output, candidate, judge, limits } = options;
  if (candidate.id !== plan.candidateId) throw new Error('Candidate identity does not match frozen plan');
  if (!cases.length) throw new Error('An explicit nonempty question selection is required');
  await mkdir(output, { recursive: true });
  await writeFile(join(output, 'manifest.json'), JSON.stringify(plan, null, 2) + '\n', { flag: 'wx' });
  await writeFile(join(output, 'gold.json'), JSON.stringify(cases.map(item => item.gold), null, 2) + '\n', { flag: 'wx' });
  const results: CaseResult[] = cases.map(item => ({ questionId: item.gold.questionId, questionType: item.gold.type, abstention: item.gold.abstention,
      caseKey: item.history.caseKey, prepare: { status: 'not_run' }, answer: { status: 'not_run' }, score: { status: 'not_run' } }));
  await save(output, plan, results);
  for (const [index, item] of cases.entries()) {
    if (options.signal?.aborted) break;
    const result = results[index]!;
    let preparedRef: string | undefined;
    try {
      result.prepare = await candidatePhase(candidate.prepare(structuredClone(item.history), limits.prepare), limits.prepare.timeoutMs, candidate);
      preparedRef = result.prepare.preparedRef;
      if (result.prepare.status === 'ready') {
        const receipt = result.prepare.receipt;
        if (receipt.candidateId !== candidate.id || receipt.historyDigest !== digest(item.history) || receipt.importedSessions !== item.history.sessions.length
          || receipt.importedMessages !== item.history.sessions.reduce((sum, session) => sum + session.turns.length, 0)) {
          result.prepare = { status: 'failed', preparedRef, reason: 'Import receipt does not cover the complete supplied history', receipt };
        } else if (!options.signal?.aborted) {
          try { result.answer = await candidatePhase(candidate.answer(preparedRef!, structuredClone(item.question), limits.answer), limits.answer.timeoutMs, candidate); }
          catch (error) { result.answer = { status: 'failed', reason: String(error) }; }
        }
      }
    } catch (error) { result.prepare = { status: 'failed', reason: String(error) }; }
    finally {
      try { await deadline(candidate.close(preparedRef), 5000); }
      catch (error) { result.cleanupError = String(error); }
    }
    if (result.answer.status === 'completed' && !options.signal?.aborted) {
      try { result.score = await deadline(judge(item.gold, result.answer.text, limits.score), limits.score.timeoutMs); }
      catch (error) { result.score = { status: 'failed', reason: String(error) }; }
    }
    if (result.score.status !== 'not_run') result.scoreAttempts = [result.score];
    await save(output, plan, results);
    // Do not start another candidate while cleanup of the previous one is unconfirmed.
    if (result.cleanupError) {
      for (const remaining of results.slice(index + 1)) remaining.prepare = { status: 'not_run', reason: 'Prior candidate cleanup failed' };
      break;
    }
  }
  return save(output, plan, results);
}

/** Retry only missing/failed judgments against frozen answers, never rerunning the candidate. */
export async function scoreSavedAnswers(output: string, judge: Judge, limits: EvaluationLimits) {
  const report = JSON.parse(await readFile(join(output, 'report.json'), 'utf8')) as { plan: EvaluationPlan; results: CaseResult[] };
  const gold = new Map((JSON.parse(await readFile(join(output, 'gold.json'), 'utf8')) as GoldRecord[]).map(item => [item.questionId, item]));
  for (const row of report.results) {
    if (row.answer.status !== 'completed' || row.score.status === 'completed') continue;
    const reference = gold.get(row.questionId);
    if (!reference) throw new Error(`Missing scoring reference: ${row.questionId}`);
    const prior = row.score;
    if (!row.scoreAttempts) row.scoreAttempts = prior.status === 'not_run' ? [] : [prior];
    try { row.score = await deadline(judge(reference, row.answer.text, limits), limits.timeoutMs); }
    catch (error) { row.score = { status: 'failed', reason: String(error) }; }
    row.scoreAttempts.push(row.score);
    await save(output, report.plan, report.results);
  }
  return save(output, report.plan, report.results);
}
