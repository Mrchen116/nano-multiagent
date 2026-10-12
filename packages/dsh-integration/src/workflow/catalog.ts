import {
  lstat,
  mkdir,
  readFile,
  readdir,
  rename,
  writeFile,
} from "node:fs/promises";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { homedir } from "node:os";
import { randomUUID } from "node:crypto";
import type { WorkflowMeta } from "@deepseek-ai/dsh-workflow";

export interface WorkflowDefinition {
  name: string;
  meta: WorkflowMeta;
  script: string;
  path?: string;
  scope: string;
}
const marker = "// nano-workflow: ";
const exists = async (path: string) => {
  try {
    return await lstat(path);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return;
    throw error;
  }
};

/** Discovers one JavaScript catalog, with nearest project definitions taking precedence. */
export class WorkflowCatalog {
  private readonly personal: string;
  constructor(
    private readonly cwd: string,
    ownerRoot = join(homedir(), ".nanoassistant"),
    private readonly namespaces: { name: string; path: string }[] = [],
  ) {
    this.personal = join(ownerRoot, "workflows");
  }
  private async roots() {
    const ancestors: string[] = [];
    let current = resolve(this.cwd);
    while (true) {
      ancestors.push(current);
      if (await exists(join(current, ".git"))) break;
      const parent = dirname(current);
      if (parent === current) {
        ancestors.splice(1);
        break;
      }
      current = parent;
    }
    return ancestors.map((path) => join(path, ".nanoassistant", "workflows"));
  }
  async read(path: string, scope = "path"): Promise<WorkflowDefinition> {
    const source = await readFile(path, "utf8");
    const end = source.indexOf("\n");
    const line = end < 0 ? source : source.slice(0, end);
    if (!line.startsWith(marker))
      throw new Error(
        "JavaScript Workflow needs a // nano-workflow: JSON metadata header",
      );
    const meta = JSON.parse(line.slice(marker.length)) as WorkflowMeta;
    if (!meta.name || !meta.description)
      throw new Error("Workflow metadata needs name and description");
    return {
      name: meta.name,
      meta,
      script: source.slice(end + 1),
      path,
      scope,
    };
  }
  async list() {
    const found = new Map<string, WorkflowDefinition>();
    const roots = [
      {
        path: new URL("../../assets/workflows/", import.meta.url).pathname,
        scope: "builtin",
      },
      { path: this.personal, scope: "personal" },
      ...(await this.roots())
        .reverse()
        .map((path) => ({ path, scope: "project" })),
      ...this.namespaces.map((item) => ({ path: item.path, scope: item.name })),
    ];
    for (const root of roots) {
      if (!(await exists(root.path))) continue;
      for (const file of (await readdir(root.path)).sort())
        if (file.endsWith(".js")) {
          const definition = await this.read(join(root.path, file), root.scope);
          if (this.namespaces.some((item) => item.name === root.scope))
            definition.name = `${root.scope}:${definition.name}`;
          found.set(definition.name, definition);
        }
    }
    return [...found.values()].sort((a, b) => a.name.localeCompare(b.name));
  }
  async resolve(reference: string) {
    if (
      isAbsolute(reference) ||
      reference.startsWith(".") ||
      reference.endsWith(".js")
    )
      return this.read(resolve(this.cwd, reference));
    const definition = (await this.list()).find(
      (item) => item.name === reference,
    );
    if (!definition) throw new Error(`Unknown Workflow: ${reference}`);
    return definition;
  }
  async save(
    meta: WorkflowMeta,
    script: string,
    scope: "project" | "personal",
  ) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(meta.name) || !meta.description)
      throw new Error("Workflow save needs a kebab-case name and description");
    const roots = await this.roots();
    let root = this.personal;
    if (scope === "project") {
      root = roots.at(-1)!;
      for (const candidate of roots)
        if (await exists(candidate)) {
          root = candidate;
          break;
        }
      for (const path of [dirname(root), root])
        if ((await exists(path))?.isSymbolicLink())
          throw new Error(
            "Project Workflow destination must not contain a symlink",
          );
    } else if (scope !== "personal")
      throw new Error("Unknown Workflow save scope");
    const path = join(root, `${meta.name}.js`);
    if ((await exists(path))?.isSymbolicLink())
      throw new Error("Workflow target must not be a symlink");
    await mkdir(root, { recursive: true });
    const temporary = `${path}.${randomUUID()}.tmp`;
    await writeFile(
      temporary,
      marker + JSON.stringify(meta) + "\n" + script + "\n",
      { flag: "wx" },
    );
    await rename(temporary, path);
    return this.read(path, scope);
  }
}
