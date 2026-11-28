import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { createServer as createHttpServer } from "node:http";
import { createServer as createHttpsServer } from "node:https";
import { connect } from "node:net";
import { WebSocketServer } from "ws";
import { execFile, spawn } from "node:child_process";
import { promisify } from "node:util";
import { expect, it } from "vitest";
const exec = promisify(execFile);
it("manages one real node, preserves its environment, and refuses a reused PID", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-lifecycle-"));
  const config = join(home, "config.yaml");
  const cli = (...args: string[]) =>
    exec(
      process.execPath,
      [resolve("apps/node/lib/cli.js"), ...args, "--config", config],
      { env: { ...process.env, NANO_OWNER_CONFIG_ROOT: home }, timeout: 70000 },
    );
  let unrelated: ReturnType<typeof spawn> | undefined;
  try {
    await writeFile(
      config,
      JSON.stringify({
        node: { node_id: "lifecycle", user_id: "owner" },
        im_service: { url: "http://127.0.0.1:9", token: "device-test" },
        agents: [],
        gateway: {
          autostart: false,
          environment: { NANO_TEST_ENV: "configured" },
        },
        llm: {
          default_model: "test",
          providers: [
            {
              name: "fixture",
              base_url: "http://127.0.0.1:9",
              models: [{ name: "test" }],
            },
          ],
        },
      }),
    );
    expect((await cli("start")).stdout).toContain("Gateway started");
    let state = JSON.parse(
      await readFile(join(home, ".gateway-state.json"), "utf8"),
    );
    expect(state.ready).toBe(true);
    expect(state.runtime_pid).toBeGreaterThan(0);
    const environment = await exec("/bin/ps", [
      "eww",
      "-p",
      String(state.runtime_pid),
      "-o",
      "command=",
    ]);
    expect(environment.stdout.includes("NANO_TEST_ENV=configured")).toBe(true);
    expect((await cli("status")).stdout).toContain("RUNNING");
    await expect(cli("start")).rejects.toThrow("already running");
    const oldRuntime = state.runtime_pid;
    process.kill(oldRuntime, "SIGKILL");
    await expect.poll(async () => JSON.parse(await readFile(join(home, ".gateway-state.json"), "utf8")).ready, {interval: 10, timeout: 3000}).toBe(false);
    await expect.poll(async () => {
      state = JSON.parse(await readFile(join(home, ".gateway-state.json"), "utf8"));
      return state.ready && state.runtime_pid !== oldRuntime;
    }, {timeout: 15000}).toBe(true);
    expect((await cli("status")).stdout).toContain(String(state.runtime_pid));
    expect((await cli("stop")).stdout).toContain("STOPPED");
    await expect
      .poll(
        () => {
          try {
            process.kill(state.runtime_pid, 0);
            return true;
          } catch {
            return false;
          }
        },
        { timeout: 10000 },
      )
      .toBe(false);
    unrelated = spawn(process.execPath, ["-e", "setInterval(()=>{},1000)"], {
      stdio: "ignore",
    });
    await new Promise((resolve) => unrelated!.once("spawn", resolve));
    await writeFile(
      join(home, ".gateway-state.json"),
      JSON.stringify({
        ...state,
        pid: unrelated.pid,
        process_start: "different birth",
      }),
    );
    await expect(cli("stop")).rejects.toThrow("identity changed");
    expect(() => process.kill(unrelated!.pid!, 0)).not.toThrow();
    expect(
      JSON.parse(await readFile(join(home, ".gateway-state.json"), "utf8")).pid,
    ).toBe(unrelated.pid);
  } finally {
    unrelated?.kill();
    await cli("stop").catch(() => {});
    await rm(home, { recursive: true, force: true });
  }
}, 90000);


it("applies configured proxy routing to initialized HTTP clients and inherited tool processes", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-proxy-"));
  const key = join(home, "key.pem"); const cert = join(home, "cert.pem");
  let origin: ReturnType<typeof createHttpsServer> | undefined;
  let proxy: ReturnType<typeof createHttpServer> | undefined;
  const sockets = new Set<import("node:stream").Duplex>();
  const connections: string[] = [];
  try {
    await exec("openssl", ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
      "-subj", "/CN=proxy-only.invalid", "-addext", "subjectAltName=DNS:proxy-only.invalid,IP:127.0.0.1",
      "-keyout", key, "-out", cert]);
    origin = createHttpsServer({ key: await readFile(key), cert: await readFile(cert) }, (request, response) => response.end(request.url));
    const web = new WebSocketServer({ server: origin });
    web.on("connection", socket => socket.on("message", data => {
      const frame=JSON.parse(data.toString()); socket.send(JSON.stringify({type:"ack",payload:{message_type:frame.type,probe:"websocket-through-proxy"}}));
    }));
    await new Promise<void>(resolve => origin!.listen(0, "127.0.0.1", resolve));
    const originPort = (origin.address() as import("node:net").AddressInfo).port;
    proxy = createHttpServer();
    proxy.on("connect", (request, downstream, head) => {
      connections.push(request.url!);
      const upstream = connect(originPort, "127.0.0.1", () => {
        downstream.write("HTTP/1.1 200 Connection Established\r\n\r\n");
        if (head.length) upstream.write(head);
        downstream.pipe(upstream); upstream.pipe(downstream);
      });
      sockets.add(downstream); sockets.add(upstream);
      downstream.on("error", () => upstream.destroy()); upstream.on("error", () => downstream.destroy());
    });
    await new Promise<void>(resolve => proxy!.listen(0, "127.0.0.1", resolve));
    const proxyPort = (proxy.address() as import("node:net").AddressInfo).port;
    const environment = { ...process.env, NODE_EXTRA_CA_CERTS: cert };
    for (const name of ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy", "NODE_USE_ENV_PROXY"])
      delete environment[name];
    const program = `
      import https from 'node:https'; import { promisify } from 'node:util'; import { execFile } from 'node:child_process';
      import { applyGatewayEnvironment } from ${JSON.stringify(pathToFileURL(resolve("apps/node/lib/lifecycle.js")).href)};
      import { WebRelayConnection } from ${JSON.stringify(pathToFileURL(resolve("packages/channels/lib/index.js")).href)};
      const direct='https://127.0.0.1:${originPort}'; const target='https://proxy-only.invalid:${originPort}';
      const get=url=>new Promise((resolve,reject)=>{const request=https.get(url,response=>{let body='';response.on('data',data=>body+=data);response.on('end',()=>resolve(body));});request.on('error',reject);});
      // Clients already exist when the foreground Gateway reads its config.
      await get(direct+'/warm-http'); await (await fetch(direct+'/warm-fetch')).text();
      applyGatewayEnvironment({gateway:{environment:{NODE_USE_ENV_PROXY:'1',HTTP_PROXY:'http://127.0.0.1:${proxyPort}',HTTPS_PROXY:'http://127.0.0.1:${proxyPort}',NO_PROXY:'127.0.0.1',no_proxy:'127.0.0.1'}}});
      const result={http:await get(target+'/http'),fetch:await(await fetch(target+'/fetch')).text()};
      const relay=new WebRelayConnection({url:target,credentials:()=>({accessToken:'fixture',registration:{node_id:'proxy-test'}}),onFrame(){},ackTimeoutMs:2000});result.websocket=(await relay.start()).probe;await relay.stop();
      result.tool=(await promisify(execFile)(process.execPath,['--input-type=module','-e',\`console.log(await(await fetch('https://proxy-only.invalid:${originPort}/tool')).text())\`],{env:process.env})).stdout.trim();
      result.bypass=await(await fetch(direct+'/no-proxy')).text();
      applyGatewayEnvironment({gateway:{environment:{HTTPS_PROXY:'http://127.0.0.1:9'}}});
      try{await fetch(target+'/must-not-fallback');throw Error('unexpected success')}catch(error){result.failure=error.cause?.code;}
      console.log(JSON.stringify(result));
    `;
    const result = await exec(process.execPath, ["--input-type=module", "-e", program], { env: environment, timeout: 20000 });
    expect(JSON.parse(result.stdout)).toEqual({ http: "/http", fetch: "/fetch", websocket: "websocket-through-proxy", tool: "/tool", bypass: "/no-proxy", failure: "ECONNREFUSED" });
    expect(connections.length).toBeGreaterThan(0);
    expect(connections.every(target => target === `proxy-only.invalid:${originPort}`)).toBe(true);
  } finally {
    for (const socket of sockets) socket.destroy();
    await Promise.all([origin, proxy].filter(Boolean).map(server => new Promise<void>(resolve => server!.close(() => resolve()))));
    await rm(home, {recursive:true,force:true});
  }
}, 30000);

it("fails fast within seconds and surfaces gateway.log reason when foreground process crashes on startup", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-fastfail-"));
  const config = join(home, "config.yaml");
  try {
    // Setting NODE_OPTIONS in gateway.environment leaves the parent CLI intact while making the spawned foreground child crash immediately.
    await writeFile(
      config,
      JSON.stringify({
        node: { node_id: "crash-node", user_id: "owner" },
        im_service: { url: "http://127.0.0.1:9", token: "device-test" },
        agents: [],
        gateway: {
          autostart: false,
          startup_timeout_seconds: 60,
          environment: { NODE_OPTIONS: "--require /nonexistent-fastfail-fixture.cjs" },
        },
        llm: { default_model: "", providers: [] },
      }),
    );
    const startedAt = Date.now();
    await expect(
      exec(
        process.execPath,
        [resolve("apps/node/lib/cli.js"), "start", "--config", config],
        { env: { ...process.env, NANO_OWNER_CONFIG_ROOT: home }, timeout: 15000 },
      ),
    ).rejects.toThrow(/Gateway exited before becoming ready.*nonexistent-fastfail-fixture/);
    expect(Date.now() - startedAt).toBeLessThan(8000);
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

it("recovers immediately when a .gateway-lifecycle.lock holder is force-killed while still serializing live holders", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-deadlock-"));
  const config = join(home, "config.yaml");
  const env = { ...process.env, NANO_OWNER_CONFIG_ROOT: home };
  let ignorer: ReturnType<typeof spawn> | undefined;
  let killerCli: ReturnType<typeof spawn> | undefined;
  let liveHolder: ReturnType<typeof spawn> | undefined;
  const cli = (timeoutMs: number, ...args: string[]) =>
    exec(
      process.execPath,
      [resolve("apps/node/lib/cli.js"), ...args, "--config", config],
      { env, timeout: timeoutMs },
    );
  try {
    await writeFile(
      config,
      JSON.stringify({
        node: { node_id: "deadlock-node", user_id: "owner" },
        im_service: { url: "http://127.0.0.1:9", token: "device-test" },
        agents: [],
        gateway: {
          autostart: false,
          shutdown_grace_seconds: 30,
        },
        llm: { default_model: "", providers: [] },
      }),
    );

    // 1. Start a dummy process that ignores SIGTERM so `cli stop` holds `.gateway-lifecycle.lock`.
    ignorer = spawn(
      process.execPath,
      ["-e", "process.on('SIGTERM', () => {}); setInterval(() => {}, 1000);"],
      { stdio: "ignore" },
    );
    await new Promise((r) => ignorer!.once("spawn", r));
    const { processBirth } = await import("../src/lifecycle.js");
    const birth = await processBirth(ignorer.pid!);
    expect(birth).toBeTruthy();
    await writeFile(
      join(home, ".gateway-state.json"),
      JSON.stringify({
        pid: ignorer.pid,
        config_path: await (await import("node:fs/promises")).realpath(config),
        process_start: birth,
        ready: true,
      }),
    );

    killerCli = spawn(
      process.execPath,
      [resolve("apps/node/lib/cli.js"), "stop", "--config", config],
      { env, stdio: "ignore" },
    );
    await expect.poll(
      async () =>
        (await import("node:fs")).existsSync(join(home, ".gateway-lifecycle.lock")),
      { interval: 25, timeout: 5000 },
    ).toBe(true);

    // 2. Force-kill both the lock-holding CLI and the dummy gateway, leaving `.gateway-lifecycle.lock` & `.gateway-state.json` behind.
    killerCli.kill("SIGKILL");
    ignorer.kill("SIGKILL");
    await Promise.all([
      new Promise((r) => killerCli!.once("exit", r)),
      new Promise((r) => ignorer!.once("exit", r)),
    ]);

    const t0 = Date.now();
    const statusAfterKill = await cli(5000, "status");
    expect(Date.now() - t0).toBeLessThan(4000);
    expect(statusAfterKill.stdout).toContain("NOT RUNNING");

    // 3. Verify a live lock holder is NOT prematurely stolen, and waits cleanly until released.
    ignorer = spawn(
      process.execPath,
      ["-e", "process.on('SIGTERM', () => setTimeout(() => process.exit(0), 600)); setInterval(() => {}, 1000);"],
      { stdio: "ignore" },
    );
    await new Promise((r) => ignorer!.once("spawn", r));
    const liveBirth = await processBirth(ignorer.pid!);
    await writeFile(
      join(home, ".gateway-state.json"),
      JSON.stringify({
        pid: ignorer.pid,
        config_path: await (await import("node:fs/promises")).realpath(config),
        process_start: liveBirth,
        ready: true,
      }),
    );
    liveHolder = spawn(
      process.execPath,
      [resolve("apps/node/lib/cli.js"), "stop", "--config", config],
      { env, stdio: "ignore" },
    );
    await expect.poll(
      async () =>
        (await import("node:fs")).existsSync(join(home, ".gateway-lifecycle.lock")),
      { interval: 25, timeout: 5000 },
    ).toBe(true);
    const tLive = Date.now();
    const serializedStatus = await cli(10000, "status");
    expect(Date.now() - tLive).toBeGreaterThanOrEqual(350);
    expect(serializedStatus.stdout).toContain("NOT RUNNING");

    // 4. Signal-exit leftover `.gateway-owner/*.json` (without lockDir) AND concurrent dead-lock reapers
    // must NEVER steal a newly acquired live lock or trigger proper-lockfile ECOMPROMISED across >1s heartbeat!
    const { mkdir } = await import("node:fs/promises");
    const ownerDir = join(home, ".gateway-owner");
    await mkdir(ownerDir, { recursive: true });
    await writeFile(
      join(ownerDir, ".gateway-lifecycle.lock.json"),
      JSON.stringify({ pid: 999999991, process_start: "signal-exit-residue", acquired_at: 1 }),
    );
    ignorer = spawn(
      process.execPath,
      ["-e", "process.on('SIGTERM', () => setTimeout(() => process.exit(0), 1400)); setInterval(() => {}, 1000);"],
      { stdio: "ignore" },
    );
    await new Promise((r) => ignorer!.once("spawn", r));
    const raceBirth = await processBirth(ignorer.pid!);
    await writeFile(
      join(home, ".gateway-state.json"),
      JSON.stringify({
        pid: ignorer.pid,
        config_path: await (await import("node:fs/promises")).realpath(config),
        process_start: raceBirth,
        ready: true,
      }),
    );
    // Also plant a dead `.gateway-lifecycle.lock` so 4 concurrent callers race to reap + hold >1s + serialize!
    await mkdir(join(home, ".gateway-lifecycle.lock"), { recursive: true });
    const concurrentResults = await Promise.all([
      cli(15000, "stop"),
      cli(15000, "status"),
      cli(15000, "status"),
      cli(15000, "status"),
    ]);
    expect(concurrentResults[0]!.stdout).toContain("STOPPED");
    for (const r of concurrentResults.slice(1)) {
      expect(r.stdout).toMatch(/RUNNING|NOT RUNNING/);
    }
  } finally {
    ignorer?.kill("SIGKILL");
    killerCli?.kill("SIGKILL");
    liveHolder?.kill("SIGKILL");
    await cli(5000, "stop").catch(() => {});
    await rm(home, { recursive: true, force: true });
  }
}, 40000);
