import { readFileSync, realpathSync } from 'node:fs';
import { resolve, relative, isAbsolute, dirname, basename, join } from 'node:path';
import type { ToolExecution, ToolExecutionResult } from '@deepseek-ai/dsh-tools';

interface Reading { text: string; lines: Set<number>; complete: boolean }
/** Per-review evidence from actual read results; Skill bodies cannot authorize raw-file edits. */
export class ReviewFiles {
  private readonly readings = new Map<string, Reading>();
  private readonly memory = new Map<string, boolean>();
  private memoryAttempted = false;
  private recordRevision?: number;
  constructor(private readonly cwd: string, readonly memoryPaths: string[], private readonly skillRoots: string[], private readonly structuredMemory = false) {
    this.memoryPaths = memoryPaths.map(path => this.key(path));
  }
  private key(path: string): string {
    const absolute = resolve(path);
    try { return realpathSync(absolute); } catch {
      const parent = dirname(absolute);
      return parent === absolute ? absolute : join(this.key(parent), basename(absolute));
    }
  }
  private managed(path: string) {
    return this.memoryPaths.includes(path) || this.skillRoots.some(root => {
      const rel = relative(this.key(root), path); return rel !== '' && !rel.startsWith('..') && !isAbsolute(rel);
    });
  }
  /** Record the canonical read window only when its returned lines match the current file.
   * Args:
   *   exec: Actual tool execution, including the caller's path.
   *   result: Settled canonical value and model-facing result.
   */
  observe(exec: Readonly<ToolExecution>, result: Readonly<ToolExecutionResult>): void {
    if (exec.name !== 'read') return;
    const args = exec.arguments as { file_path?: unknown };
    if (typeof args.file_path !== 'string') return;
    const requested = this.key(resolve(this.cwd, args.file_path));
    const isMemory = this.memoryPaths.includes(requested);
    if (!this.managed(requested)) return;
    if (isMemory) { this.memoryAttempted = true; this.memory.set(requested, false); }
    const value = result.value as { path?: unknown; totalLines?: unknown; lines?: { number: number; text: string }[] } | undefined;
    let text: string;
    try { text = readFileSync(requested, 'utf8'); }
    catch (error) {
      this.readings.delete(requested);
      // A tool failure plus confirmed absence is distinct from permission/read errors.
      if (isMemory && result.isError && result.error.info?.code === 'FS_NOT_FOUND' && (error as NodeJS.ErrnoException).code === 'ENOENT') this.memory.set(requested, true);
      return;
    }
    if (result.isError || typeof value?.path !== 'string' || this.key(resolve(this.cwd, value.path)) !== requested || !Array.isArray(value.lines)) {
      this.readings.delete(requested); return;
    }
    const lines = text ? text.replace(/\r\n/g, '\n').replace(/\n$/, '').split('\n') : [];
    if (value.totalLines !== lines.length || value.lines.some(line => !Number.isInteger(line.number) || line.number < 1 || line.text !== lines[line.number - 1])) {
      this.readings.delete(requested); return;
    }
    // Do not accept content withheld by a final output transform.
    const rendered = result.content.filter(block => block.type === 'text').map(block => block.text).join('\n');
    if (value.lines.some(line => !rendered.includes(line.text))) { this.readings.delete(requested); return; }
    let reading = this.readings.get(requested);
    if (!reading || reading.text !== text) reading = { text, lines: new Set(), complete: false };
    for (const line of value.lines) reading.lines.add(line.number);
    reading.complete = reading.lines.size === lines.length;
    this.readings.set(requested, reading);
    if (isMemory) this.memory.set(requested, reading.complete);
  }
  /** Count a Memory write attempt even if the model omitted its required reads. */
  memoryWrite(): void { this.memoryAttempted = true; }
  /** A structured tool read carries the authority revision used by the write transaction. */
  memoryRecordsRead(revision: number): void { this.recordRevision = revision; }
  get memoryRevision(): number | undefined { return this.recordRevision; }
  get memoryIncomplete(): boolean { return this.memoryAttempted && (this.structuredMemory ? this.recordRevision === undefined : this.memoryPaths.some(path => !this.memory.get(path))); }
  /** Check the raw target while its existing write lock is held. */
  require(path: string, current: string): void {
    const reading = this.readings.get(this.key(path));
    if (!reading?.complete) throw new Error('Read the complete original file with read in this review before changing it.');
    if (reading.text !== current) throw new Error('The file changed after reading. Read the complete current file again.');
  }
  /** Advance the in-memory baseline only from a confirmed write. */
  committed(path: string, text: string | undefined): void {
    const key = this.key(path);
    if (text === undefined) this.readings.delete(key);
    else this.readings.set(key, { text, lines: new Set(), complete: true });
  }
}
