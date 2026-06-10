// @ts-expect-error node builtins are available in vitest runtime even without @types/node
import { readFileSync, readdirSync, statSync } from "node:fs";
// @ts-expect-error see above
import { dirname, join, resolve } from "node:path";
// @ts-expect-error see above
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Regression guard for M4 R6: the v2 chat surface must never reach into the
// legacy `/im/v1/users` endpoint or the legacy chat-api adapters. If any new
// code under `features/chat/v2/` quietly imports `im-chat-api` or hits
// `/im/v1/users`, this test fails fast so it never lands undetected.
//
// bugfix-402-M5: extended to enforce the same contract on all of
// `features/chat/` — im-chat-api.ts itself must not call /im/v1/users.

const HERE = dirname(fileURLToPath(import.meta.url));
const CHAT_DIR = resolve(HERE, "..");

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const s = statSync(full);
    if (s.isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(name) && !name.endsWith(".test.ts") && !name.endsWith(".test.tsx")) out.push(full);
  }
  return out;
}

// Strip block comments and line comments from source so we don't flag mentions
// in comment text (e.g. "was /im/v1/users before this change").
function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\/\/[^\n]*/g, "");
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

describe("im-chat-api /im/v1/users contract", () => {
  // bugfix-402-M5: im-chat-api.ts must not call /im/v1/users (the endpoint was
  // removed in feat-340; calling it causes a 404 that breaks bootstrap,
  // listConversations, and group-chat creation). This test scans the
  // implementation sources under features/chat/ (excluding test files) and
  // enforces the endpoint is absent from non-comment code.
  it("features/chat implementation sources do not call /im/v1/users", () => {
    const files = walk(CHAT_DIR);
    const offenders = files.filter((f) => {
      const src = stripComments(readFileSync(f, "utf8"));
      return src.includes("/im/v1/users");
    });
    expect(offenders).toEqual([]);
  });
});
