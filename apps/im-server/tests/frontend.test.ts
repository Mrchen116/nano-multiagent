import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
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

it("only caches native vendor assets under their actual revision", async () => {
  const dir = mkdtempSync(join(tmpdir(), "nano-trajectory-assets-"));
  const vendor = join(dir, 'plugins/@deepseek-ai/example');
  mkdirSync(vendor, {recursive: true});
  writeFileSync(join(dir, 'manifest.json'), JSON.stringify({rev: 'current'}));
  writeFileSync(join(dir, 'index.html'), 'viewer');
  writeFileSync(join(vendor, 'client.js'), 'current');
  const app = await createServer({dbPath: join(dir, 'im.sqlite3'), publicUrl: 'https://nano.example', trajectoryDistDir: dir});
  try {
    const current = await app.inject('/trajectory/plugins/@deepseek-ai/example/client.js?rev=current');
    expect(current.statusCode).toBe(200);
    expect(current.headers['cache-control']).toContain('immutable');
    expect((await app.inject('/trajectory/plugins/@deepseek-ai/example/client.js?rev=old')).statusCode).toBe(404);
    expect((await app.inject('/trajectory/')).headers['cache-control']).toBe('no-cache');
  } finally { await app.close(); rmSync(dir, {recursive: true, force: true}); }
});
