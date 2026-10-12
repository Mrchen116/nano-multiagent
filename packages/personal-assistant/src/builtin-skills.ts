import {
  cp,
  mkdir,
  mkdtemp,
  readdir,
  rename,
  rm,
  access,
} from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import lockfile from "proper-lockfile";

export const builtinSkillsRoot = fileURLToPath(
  new URL("../assets/skills/", import.meta.url),
);
/** Refresh only packaged names; user-created Skills and original workspaces stay untouched. */
export async function installBuiltinSkills(
  destination: string,
  source = builtinSkillsRoot,
): Promise<string[]> {
  await mkdir(destination, { recursive: true });
  const release = await lockfile.lock(destination, {
    retries: { retries: 10, minTimeout: 100, maxTimeout: 500 },
  });
  try {
    const installed: string[] = [];
    for (const entry of await readdir(source, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const origin = join(source, entry.name);
      await access(join(origin, "SKILL.md"));
      const staging = await mkdtemp(join(destination, ".builtin-staging-"));
      const target = join(destination, entry.name);
      const backup = join(staging, "previous");
      let previous = false;
      try {
        await cp(origin, join(staging, "current"), { recursive: true });
        try {
          await rename(target, backup);
          previous = true;
        } catch (error) {
          if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
        }
        try {
          await rename(join(staging, "current"), target);
        } catch (error) {
          if (previous) {
            await rename(backup, target);
            previous = false;
          }
          throw error;
        }
        previous = false;
        installed.push(entry.name);
      } finally {
        if (!previous) await rm(staging, { recursive: true, force: true });
      }
    }
    return installed;
  } finally {
    await release();
  }
}
