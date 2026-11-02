import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { makePlan, readConfiguration } from './plan.js';
import { createJudge, judgeIdentity, type JudgeConfiguration } from './judge.js';
import { createNanoCandidate } from './nano.js';
import { runEvaluation, scoreSavedAnswers } from './runner.js';
import type { EvaluationLimits } from '@nano/product-contracts';

/** Run plan by default; model calls require an explicit run or score command and opt-in. */
export async function main(argv: string[]): Promise<void> {
  const { values, positionals } = parseArgs({ args: argv, allowPositionals: true, strict: true, options: {
    config: { type: 'string' }, ids: { type: 'string' }, output: { type: 'string' },
    'allow-model-calls': { type: 'boolean', default: false }, help: { type: 'boolean' },
  } });
  if (values.help) {
    process.stdout.write('memory-eval [plan|run] --config CONFIG.json --ids IDS.json [--output RUN_DIR]\n'
      + 'memory-eval score --output RUN_DIR --allow-model-calls\n'
      + 'Default: plan (zero model calls). run also requires --allow-model-calls and --output.\n'); return;
  }
  const command = positionals[0] ?? 'plan';
  if (positionals.length > 1 || !['plan', 'run', 'score'].includes(command)) throw new Error('Expected plan, run or score');
  if (command !== 'plan' && !values['allow-model-calls']) throw new Error('Model execution is disabled; pass --allow-model-calls explicitly');
  if (command === 'score') {
    if (!values.output) throw new Error('score requires --output with an existing run');
    const output = resolve(values.output);
    const manifest = JSON.parse(await readFile(join(output, 'manifest.json'), 'utf8')) as { judge: JudgeConfiguration; scoreLimits: EvaluationLimits; protocol: { judge: typeof judgeIdentity } };
    if (manifest.protocol.judge.promptHash !== judgeIdentity.promptHash || manifest.protocol.judge.implementationHash !== judgeIdentity.implementationHash) throw new Error('Frozen judge differs from this checkout; use the original judge version to rescore');
    const report = await scoreSavedAnswers(output, createJudge(manifest.judge, true), manifest.scoreLimits);
    process.stdout.write(JSON.stringify(report.summary, null, 2) + '\n'); return;
  }
  if (!values.config || !values.ids) throw new Error('An explicit --config and nonempty --ids file are required');
  const config = await readConfiguration(resolve(values.config));
  const { plan, cases } = await makePlan(config, resolve(values.ids));
  if (command === 'plan') {
    if (values.output) {
      await mkdir(resolve(values.output), { recursive: true });
      await writeFile(join(resolve(values.output), 'plan.json'), JSON.stringify(plan, null, 2) + '\n');
    }
    process.stdout.write(JSON.stringify(plan, null, 2) + '\n'); return;
  }
  if (!values.output) throw new Error('run requires --output (a new run directory)');
  for (const route of [config.candidate, config.judge]) if (!process.env[route.apiKeyEnv]) throw new Error(`Missing credential environment variable: ${route.apiKeyEnv}`);
  const output = resolve(values.output);
  const candidate = await createNanoCandidate(config.candidate, plan.candidateId, join(output, 'candidate-data'), true);
  const abort = new AbortController();
  const stop = () => { abort.abort(); void candidate.close(); };
  process.once('SIGINT', stop); process.once('SIGTERM', stop);
  try {
    const report = await runEvaluation({ cases, plan, output, candidate, judge: createJudge(config.judge, true, abort.signal), limits: config.limits, signal: abort.signal });
    process.stdout.write(JSON.stringify({ output, ...report.summary }, null, 2) + '\n');
  } finally { process.off('SIGINT', stop); process.off('SIGTERM', stop); await candidate.close(); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main(process.argv.slice(2)).catch(error => { process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`); process.exitCode = 1; });
}
