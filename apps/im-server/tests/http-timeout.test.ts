import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { expect, it } from "vitest";
import { createServer } from "../src/server.js";

it("returns configuration confirmation over HTTP after a slow node response", async () => {
  const directory = await mkdtemp(join(tmpdir(), "nano-config-http-"));
  const app = await createServer({ dbPath: join(directory, "im.sqlite3"), uploadDir: join(directory, "uploads"),
    publicUrl: "http://127.0.0.1:8011", jwtSecret: "isolated-http-timeout-regression" });
  try {
    const ctx = app.im, now = new Date().toISOString();
    ctx.db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status,is_company_admin) VALUES('owner','owner','Owner','owner',?,'active',1)").run(now);
    ctx.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('node','owner','Node','online')").run();
    ctx.db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,workspace_root,created_at,updated_at) VALUES('assistant','owner','node','Assistant','/assistant',?,?)").run(now, now);
    ctx.identity.authenticateRequest = () => ctx.identity.user("owner")!;
    ctx.gateway.request = async () => {
      // Full requests can wait through configuration receipt recovery. Receiving
      // the request has finished; the response must survive that business wait.
      await delay(16_000);
      return { agent: { agent_id: "assistant" } };
    };
    const base = await app.listen({ host: "127.0.0.1", port: 0 });
    const response = await fetch(`${base}/im/v1/agents/assistant/config`, { headers: { authorization: "Bearer test" } });
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ agent_id: "assistant" });
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
}, 25_000);
