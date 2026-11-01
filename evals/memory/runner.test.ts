import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it, vi } from 'vitest';
import type { MemoryCandidate, EvaluationHistory } from '@nano/product-contracts';
import { loadCases, digest } from './dataset.js';
import { runEvaluation, summarize } from './runner.js';

const cases=loadCases([{question_id:'one',question_type:'single-session-user',question:'FUTURE',question_date:'2024/02/01',answer:'GOLD',haystack_session_ids:['a'],haystack_dates:['2024/01/01'],haystack_sessions:[[{role:'user',content:'EXPERIENCE'}]],answer_session_ids:['a']}]);
const limits={timeoutMs:1000,maxModelCalls:5,maxOutputTokens:100};
const usage={modelCalls:0,inputTokens:null,outputTokens:null,costUsd:null,elapsedMs:0};
const plan={protocolId:'protocol',candidateId:'candidate',datasetHash:'dataset',selectedIds:['one']};

it.each(['during-ingestion','after-ingestion'])('runs unchanged against opaque %s memory and separates judge input', async strategy=>{
  const dir=await mkdtemp(join(tmpdir(),'memory-runner-')); let prepared:EvaluationHistory|undefined;
  const privateStates=new Map<string,unknown>();const close=vi.fn();
  const candidate:MemoryCandidate={id:'candidate',async prepare(history){
    prepared=structuredClone(history); const ref=strategy==='during-ingestion'?'store://record/42':'snapshot://another-format';
    privateStates.set(ref,strategy==='during-ingestion'?new Set(['remembered']):{summary:'remembered'});
    return {status:'ready',preparedRef:ref,receipt:{candidateId:'candidate',historyDigest:digest(history),importedSessions:1,importedMessages:1,evidenceRef:'audit',usage}};
  },async answer(ref,question){expect(privateStates.has(ref)).toBe(true);expect(question.text).toBe('FUTURE');return {status:'completed',text:'original answer',evidenceRef:'reply',usage};},close};
  const judge=vi.fn(async(gold,answer)=>{expect(gold.answer).toBe('GOLD');expect(answer).toBe('original answer');return {status:'completed' as const,correct:true,raw:'yes',usage};});
  try {
    const report=await runEvaluation({cases,plan,output:dir,candidate,judge,limits:{prepare:limits,answer:limits,score:limits}});
    expect(JSON.stringify(prepared)).not.toContain('FUTURE');expect(JSON.stringify(prepared)).not.toContain('GOLD');
    expect(report.summary).toMatchObject({planned:1,scored:1,correct:1,accuracy:1});
    expect(close).toHaveBeenCalled();expect(judge).toHaveBeenCalledOnce();
    expect(await readFile(join(dir,'answers.jsonl'),'utf8')).toContain('original answer');
  } finally {await rm(dir,{recursive:true,force:true});}
});

it('keeps incomplete and failed attempts in the denominator and closes even after a thrown preparation', async()=>{
  const dir=await mkdtemp(join(tmpdir(),'memory-failure-'));const answer=vi.fn();const close=vi.fn();const judge=vi.fn();
  const candidate:MemoryCandidate={id:'candidate',prepare:async()=>{throw new Error('preparation unavailable');},answer,close};
  try {
    const report=await runEvaluation({cases,plan,output:dir,candidate,judge,limits:{prepare:limits,answer:limits,score:limits}});
    expect(report.summary).toMatchObject({planned:1,scored:0,correct:0,accuracy:null,correctPerPlanned:0});
    expect(report.results[0].prepare.status).toBe('failed');expect(answer).not.toHaveBeenCalled();expect(judge).not.toHaveBeenCalled();expect(close).toHaveBeenCalled();
    expect(summarize([...report.results,{...report.results[0],questionId:'two',prepare:{status:'incomplete',reason:'budget'}}])).toMatchObject({planned:2,scored:0});
  } finally {await rm(dir,{recursive:true,force:true});}
});

it('retains the original failed judgment when rescoring the same saved answer', async () => {
  const { scoreSavedAnswers } = await import('./runner.js');
  const dir = await mkdtemp(join(tmpdir(), 'memory-rescore-'));
  const candidate: MemoryCandidate = { id: 'candidate', async prepare(history) {
    return { status: 'ready', preparedRef: 'opaque', receipt: { candidateId: 'candidate', historyDigest: digest(history), importedSessions: 1, importedMessages: 1, evidenceRef: 'audit', usage } };
  }, async answer() { return { status: 'completed', text: 'Frozen original', evidenceRef: 'answer', usage }; }, async close() {} };
  try {
    await runEvaluation({ cases, plan, output: dir, candidate, limits: { prepare: limits, answer: limits, score: limits },
      judge: async () => ({ status: 'failed', reason: 'HTTP 503', usage: { ...usage, modelCalls: 1 } }) });
    const report = await scoreSavedAnswers(dir, async (_gold, answer) => {
      expect(answer).toBe('Frozen original'); return { status: 'completed', correct: true, raw: 'yes', usage };
    }, limits);
    expect(report.results[0].scoreAttempts).toHaveLength(2);
    expect(report.results[0].scoreAttempts?.[0]).toMatchObject({ status: 'failed', reason: 'HTTP 503' });
    expect(report.summary).toMatchObject({ planned: 1, scored: 1, correct: 1 });
  } finally { await rm(dir, { recursive: true, force: true }); }
});
