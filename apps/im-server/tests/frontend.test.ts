import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, it } from "vitest";
import { createServer } from "../src/server.js";

it("never caches the frontend entrypoint on direct or SPA routes", async () => {
  const dir = mkdtempSync(join(tmpdir(), "nano-frontend-"));
  writeFileSync(join(dir, "index.html"), '<html><script src="/app.js"></script></html>');
  writeFileSync(join(dir, "app.js"), "console.log('app')");
  const app = await createServer({ dbPath: join(dir, "im.sqlite3"), publicUrl: "https://nano.example", frontendDistDir: dir });
  try {
    for (const url of ["/", "/index.html", "/settings/agents/personal-agent", "/chat"]) {
      const response = await app.inject(url);
      expect(response.statusCode).toBe(200);
      expect(response.headers["cache-control"]).toBe("no-store");
      expect(response.body).toContain('/app.js');
    }
    const asset = await app.inject("/app.js");
    expect(asset.statusCode).toBe(200);
    expect(asset.headers["cache-control"]).toBeUndefined();
  } finally {
    await app.close();
    rmSync(dir, { recursive: true, force: true });
  }
});
