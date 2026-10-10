import { mkdtemp, mkdir, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, it } from "vitest";
import { WorkflowCatalog } from "../src/workflow/catalog.js";
it("uses nearest project definitions, preserves structured args source, and enforces save symlink boundaries", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-workflow-catalog-"));
  try {
    const project = join(home, "project"),
      nested = join(project, "nested"),
      owner = join(home, "owner");
    await mkdir(join(project, ".git"), { recursive: true });
    await mkdir(nested);
    const meta = { name: "reusable", description: "test" };
    await new WorkflowCatalog(project, owner).save(
      meta,
      "return args;",
      "personal",
    );
    await new WorkflowCatalog(project, owner).save(
      meta,
      "return {root:args};",
      "project",
    );
    await mkdir(join(nested, ".nanoassistant", "workflows"), {
      recursive: true,
    });
    const catalog = new WorkflowCatalog(nested, owner);
    await catalog.save(meta, "return {nearest:args};", "project");
    expect((await catalog.resolve("reusable")).script).toContain("nearest");
    expect((await catalog.resolve("deep-research")).scope).toBe("builtin");
    const namespaced = new WorkflowCatalog(nested, owner, [
      { name: "plugin", path: join(project, ".nanoassistant", "workflows") },
    ]);
    expect((await namespaced.resolve("plugin:reusable")).script).toContain(
      "root:args",
    );
    const target = join(nested, ".nanoassistant", "workflows", "reusable.js");
    await rm(target);
    await symlink(
      join(project, ".nanoassistant", "workflows", "reusable.js"),
      target,
    );
    await expect(catalog.save(meta, "return 1;", "project")).rejects.toThrow(
      "symlink",
    );
    const shared = join(home, "shared");
    await mkdir(shared);
    await rm(owner, { recursive: true });
    await symlink(shared, owner);
    expect(
      (await catalog.save(meta, "return 2;", "personal")).script,
    ).toContain("return 2");
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});
