import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, it } from "vitest";
import { createServer } from "../src/server.js";

it("never caches the frontend entrypoint on direct or SPA routes", async () => {
  const dir = mkdtempSync(join(tmpdir(), "nano-frontend-"));
  writeFileSync(join(dir, "index.html"), '<html><script src="/app.js"></script></html>');
  writeFileSync(join(dir, "app.js"), "console.log('app')");
  mkdirSync(join(dir,'assets'));
  writeFileSync(join(dir,'assets','index-abcdefgh.js'),'hashed bundle');
  const app = await createServer({ dbPath: join(dir, "im.sqlite3"), publicUrl: "https://nano.example", frontendDistDir: dir });
  try {
    for (const url of ["/", "/index.html", "/settings/agents/personal-agent", "/chat"]) {
      const response = await app.inject(url);
      expect(response.statusCode).toBe(200);
      expect(response.headers["cache-control"]).toContain("no-store");
      expect(response.body).toContain('/app.js');
    }
    const asset = await app.inject("/app.js");
    expect(asset.statusCode).toBe(200);
    expect(asset.headers["cache-control"]).toBeUndefined();
    expect((await app.inject('/assets/index-abcdefgh.js')).headers['cache-control']).toContain('immutable');
  } finally {
    await app.close();
    rmSync(dir, { recursive: true, force: true });
  }
});

it('bootstraps agent HTML with a current cookie session without rotating it or exposing refresh credentials',async()=>{
  const dir=mkdtempSync(join(tmpdir(),'nano-page-bootstrap-'));
  writeFileSync(join(dir,'index.html'),'<html><body><div id="root"></div></body></html>');
  const app=await createServer({dbPath:join(dir,'im.sqlite3'),publicUrl:'https://nano.example',frontendDistDir:dir});
  const headers={'x-im-session':'browser',origin:'https://nano.example'};
  try {
    const registered=await app.inject({method:'POST',url:'/im/v1/auth/register',headers,payload:{username:'bootstrap-user',password:'password-123',display_name:'</script><img src=x>'}});
    expect(registered.statusCode).toBe(201);
    const cookie=String(registered.headers['set-cookie']).split(';')[0]!;
    const page=await app.inject({url:'/settings/agents/missing?view=work',headers:{cookie}});
    expect(page.headers['cache-control']).toContain('no-store');
    expect(page.headers.vary).toBe('Cookie');
    expect(page.headers['set-cookie']).toBeUndefined();
    const raw=page.body.match(/<script id="nano-page-bootstrap" type="application\/json">(.*?)<\/script>/)![1]!;
    const bootstrap=JSON.parse(raw);
    expect(raw).not.toContain('<img');
    expect(raw).not.toContain('refresh_token');
    expect(bootstrap.session.user.id).toBe(registered.json().user.id);
    expect(bootstrap.data).not.toHaveProperty('/im/v1/agents/missing/settings?view=saved');
    expect((await app.inject({url:'/im/v1/auth/me',headers:{authorization:`Bearer ${bootstrap.session.access_token}`}})).statusCode).toBe(200);
    expect((await app.inject({url:'/settings/agents/missing'})).body).not.toContain('nano-page-bootstrap');
    const refreshed=await app.inject({method:'POST',url:'/im/v1/auth/refresh',headers:{...headers,cookie},payload:{}});
    expect(refreshed.statusCode).toBe(200);
    expect((await app.inject({url:'/settings/agents/missing',headers:{cookie}})).body).not.toContain('nano-page-bootstrap');
  } finally {await app.close();rmSync(dir,{recursive:true,force:true});}
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
