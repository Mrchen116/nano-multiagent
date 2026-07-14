// @ts-expect-error node builtins are available in vitest runtime even without @types/node
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
// @ts-expect-error see above
import { dirname, join, resolve } from "node:path";
// @ts-expect-error see above
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const CHAT_DIR = HERE;
const LEGACY_FILES = [
  "im-chat-api.ts",
  "im-chat-api.test.ts",
  "mock-chat-api.ts",
  "types.ts",
  "components/conversation-list.tsx"
];

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

describe("canonical Chat architecture", () => {
  it("has one unversioned current surface and no legacy cluster", () => {
    expect(existsSync(join(CHAT_DIR, "v2"))).toBe(false);
    expect(LEGACY_FILES.filter((path) => existsSync(join(CHAT_DIR, path)))).toEqual([]);
    expect(existsSync(join(CHAT_DIR, "chat-workspace-page.tsx"))).toBe(true);
    expect(existsSync(join(CHAT_DIR, "chat-types.ts"))).toBe(true);
  });

  it("production sources do not retain version or legacy runtime markers", () => {
    const files = walk(CHAT_DIR);
    const forbidden = ["/im/v1/users", "VITE_CHAT_API_MODE", '"chat-v2"', "'chat-v2'"];
    const offenders = files.flatMap((file) => {
      const source = stripComments(readFileSync(file, "utf8"));
      return forbidden
        .filter((marker) => source.includes(marker))
        .map((marker) => ({ file: file.slice(CHAT_DIR.length + 1), marker }));
    });
    expect(offenders).toEqual([]);
  });

  it("keeps mention derivation and authenticated JSON errors on their canonical owners", () => {
    const apiSource = stripComments(readFileSync(join(CHAT_DIR, "chat-api.ts"), "utf8"));
    expect(
      ["listMentionCandidates", "initialsFrom", "jsonOrThrow"].filter((marker) =>
        apiSource.includes(marker)
      )
    ).toEqual([]);
  });
});
