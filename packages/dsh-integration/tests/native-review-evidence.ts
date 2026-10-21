import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

interface EvidenceFiles {
  mkdir(path: string, options: { recursive: true }): Promise<unknown>;
  readFile(path: string, encoding: 'utf8'): Promise<string>;
  writeFile(path: string, content: string): Promise<unknown>;
  rm(path: string, options: { recursive: true; force: true }): Promise<unknown>;
}
interface ReviewCleanup {
  home: string;
  evidence?: string;
  observe?: () => Promise<unknown>;
  shutdown?: () => Promise<void>;
  failure?: { error: unknown };
}

/** Finish a native test without letting optional evidence bypass owned cleanup. */
export async function finishNativeReview(options: ReviewCleanup, io: EvidenceFiles = { mkdir, readFile, rm, writeFile }): Promise<void> {
  const { home, evidence, observe, shutdown, failure } = options;
  const diagnostics: Error[] = [];
  const attempt = async (phase: string, work: () => Promise<unknown>) => {
    try { await work(); }
    catch (error) { diagnostics.push(new Error(`Native review ${phase} failed`, { cause: error })); }
  };
  try {
    await attempt('observation export', async () => {
      if (!evidence || !observe) return;
      await io.mkdir(evidence, { recursive: true });
      const observed = await observe().catch(error => ({ observationError: String(error) }));
      await io.writeFile(join(evidence, 'observation.json'), JSON.stringify(observed, null, 2));
    });
  } finally {
    try {
      await attempt('shutdown', async () => { await shutdown?.(); });
    } finally {
      try {
        await attempt('fixture export', async () => {
          if (!evidence) return;
          await io.mkdir(evidence, { recursive: true });
          for (const file of ['reviews.jsonl', 'agents.jsonl', 'disposed.jsonl', 'effects.jsonl', 'parallel.jsonl']) {
            const text = await io.readFile(join(home, file), 'utf8').catch(error => {
              if (error?.code === 'ENOENT') return undefined;
              throw error;
            });
            if (text !== undefined) await io.writeFile(join(evidence, file), text);
          }
        });
      } finally {
        // home is the caller's freshly created mkdtemp root, never the output path.
        await attempt('home cleanup', () => io.rm(home, { recursive: true, force: true }));
      }
    }
  }
  if (diagnostics.length) {
    const primary = failure ? [failure.error] : [];
    throw new AggregateError([...primary, ...diagnostics], 'Native review failure with cleanup diagnostics', { cause: failure ? failure.error : diagnostics[0] });
  }
  if (failure) throw failure.error;
}
