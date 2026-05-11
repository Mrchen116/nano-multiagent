// @ts-expect-error node builtins are available in vitest runtime even without @types/node
import { readFileSync, readdirSync, statSync } from "node:fs";
// @ts-expect-error see above
import { dirname, join } from "node:path";
// @ts-expect-error see above
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Regression guard for M4 R6: the v2 chat surface must never reach into the
// legacy `/im/v1/users` endpoint or the legacy chat-api adapters. If any new
// code under `features/chat/v2/` quietly imports `im-chat-api` or hits
// `/im/v1/users`, this test fails fast so it never lands undetected.

const HERE = dirname(fileURLToPath(import.meta.url));

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const s = statSync(full);
    if (s.isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(name) && !name.endsWith(".test.ts") && !name.endsWith(".test.tsx")) out.push(full);
  }
  return out;
}

describe("v2 chat surface legacy isolation", () => {
  it("does not reference /im/v1/users", () => {
    const files = walk(HERE);
    const offenders = files.filter((f) => readFileSync(f, "utf8").includes("/im/v1/users"));
    expect(offenders).toEqual([]);
  });

  it("does not import the legacy im-chat-api / chat-api / mock-chat-api modules", () => {
    const files = walk(HERE);
    const offenders = files.filter((f) => {
      const src = readFileSync(f, "utf8");
      return /from\s+["'](\.\.\/)+(im-chat-api|chat-api|mock-chat-api)["']/.test(src);
    });
    expect(offenders).toEqual([]);
  });
});
