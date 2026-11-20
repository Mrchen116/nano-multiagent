/** Local CLI adapters covered by the shared worker conformance tests. */
export const cliWorkerRuntimes = ['codex', 'claude'] as const;
export const workerRuntimes = ['dsh', ...cliWorkerRuntimes] as const;
export type WorkerRuntime = (typeof workerRuntimes)[number];
