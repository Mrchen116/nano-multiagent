import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { expect, it } from "vitest";
import { installBuiltinSkills } from "../src/builtin-skills.js";

it("refreshes packaged Skills and support files without touching user-created names", async () => {
  const root = await mkdtemp(join(tmpdir(), "nano-builtin-"));
  const source = join(root, "source");
  const target = join(root, "target");
  try {
    await mkdir(join(source, "builtin/references"), { recursive: true });
    await writeFile(join(source, "builtin/SKILL.md"), "new instructions");
    await writeFile(
      join(source, "builtin/references/new.md"),
      "new supporting facts",
    );
    for (const name of ["builtin", "user-created"]) {
      await mkdir(join(target, name), { recursive: true });
      await writeFile(join(target, name, "SKILL.md"), "original");
    }
    expect(await installBuiltinSkills(target, source)).toEqual(["builtin"]);
    expect(await readFile(join(target, "builtin/SKILL.md"), "utf8")).toBe(
      "new instructions",
    );
    expect(
      await readFile(join(target, "builtin/references/new.md"), "utf8"),
    ).toBe("new supporting facts");
    expect(await readFile(join(target, "user-created/SKILL.md"), "utf8")).toBe(
      "original",
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
