const restoreKey = 'NANO_WORKER_ENV_ORIGINALS';
const runtimeOnly = /^(NANO_|DSH_)/;

/** Capture only the native environment entries a DSH launch is about to shadow. */
export function cliEnvironmentRestoration(overrides: NodeJS.ProcessEnv = {}): NodeJS.ProcessEnv {
  const originals = Object.fromEntries(
    Object.entries(overrides)
      .filter(([key, value]) => !runtimeOnly.test(key) && value !== process.env[key])
      .map(([key]) => [key, process.env[key] ?? null]),
  );
  return { [restoreKey]: JSON.stringify(originals) };
}

/** Recover the CLI's native environment, including node-configured CLI settings. */
export function nativeCliEnvironment(): NodeJS.ProcessEnv {
  const env = { ...process.env };
  const originals: Record<string, string | null> = JSON.parse(env[restoreKey] ?? '{}');
  for (const [key, value] of Object.entries(originals)) {
    if (value === null) delete env[key];
    else env[key] = value;
  }
  for (const key of Object.keys(env)) if (runtimeOnly.test(key)) delete env[key];
  return env;
}
