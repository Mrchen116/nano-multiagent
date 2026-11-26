#!/usr/bin/env node
/**
 * Hyper-V Host Control Plane for Clean Windows 10 & Windows 11 Desktop Acceptance.
 *
 * Runs on the Windows Server 2025 Hyper-V host (192.168.184.1 / 192.168.183.1):
 *   - :18080  Primary apps/im-server (publicUrl = http://127.0.0.1:18080 via guest portproxy)
 *   - :18081  Byte-metered Release Asset & Admin Control Server
 *   - :18082  OpenAI-compatible SSE LLM Server (/v1/chat/completions)
 *   - :18083  Secondary apps/im-server (for server-bar switch & IndexedDB isolation)
 *   - :8078   Guest Receipt & PNG Screenshot Receiver
 */
import http from 'node:http';
import { createHash, randomUUID } from 'node:crypto';
import { execFile, spawn } from 'node:child_process';
import { promisify } from 'node:util';
import { copyFile, mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, resolve, basename } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { startSseLlmServer } from './sse-llm-server.mjs';

const exec = promisify(execFile);
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

const [hostIp, bundleDirArg, workDirArg, receiptsDirArg, repoRootArg] = process.argv.slice(2);
if (!hostIp || !bundleDirArg || !workDirArg || !receiptsDirArg || !repoRootArg) {
  console.error('Usage: node host-stack.mjs <hostIp> <bundleDir> <workDir> <receiptsDir> <repoRoot>');
  process.exit(1);
}

const bundleDir = resolve(bundleDirArg);
const workDir = resolve(workDirArg);
const receiptsDir = resolve(receiptsDirArg);
const repoRoot = resolve(repoRootArg);

function sha256(buf) {
  return createHash('sha256').update(buf).digest('hex');
}

async function rewriteDesktopRelease(srcDir, dstDir, version) {
  await mkdir(dstDir, { recursive: true });
  for (const name of await readdir(srcDir)) {
    await copyFile(join(srcDir, name), join(dstDir, name));
  }
  const ghBase = `https://github.com/Mrchen116/nano-multiagent/releases/download/v${version}/`;
  const descPath = join(dstDir, 'desktop-win32-x64.json');
  const manifestPath = join(dstDir, 'manifest.desktop-win32-x64.json');

  const desc = JSON.parse(await readFile(descPath, 'utf8'));
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
  if (
    desc.version === version &&
    manifest.version === version &&
    String(desc.runtime?.download_url ?? '').startsWith(ghBase) &&
    String(manifest.download_url ?? '').startsWith(ghBase)
  ) {
    return { desc, manifest };
  }

  desc.version = version;
  desc.runtime.download_url = ghBase + desc.runtime.name;
  desc.app.download_url = ghBase + desc.app.name;
  const descBytes = Buffer.from(JSON.stringify(desc, null, 2) + '\n');
  await writeFile(descPath, descBytes);

  manifest.version = version;
  manifest.size = descBytes.byteLength;
  manifest.sha256 = sha256(descBytes);
  manifest.download_url = ghBase + 'desktop-win32-x64.json';
  manifest.installer.download_url = ghBase + 'Crewden-Desktop-Setup-x64.exe';
  await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  return { desc, manifest };
}

async function main() {
  await mkdir(workDir, { recursive: true });
  await mkdir(receiptsDir, { recursive: true });
  await mkdir(join(receiptsDir, 'screenshots'), { recursive: true });

  const assetsRoot = join(workDir, 'assets');
  const releaseDir = join(workDir, 'im-releases');
  await mkdir(assetsRoot, { recursive: true });
  await mkdir(releaseDir, { recursive: true });

  const v1 = await rewriteDesktopRelease(join(bundleDir, 'v1.0.0'), join(assetsRoot, 'v1.0.0'), '1.0.0');
  const v2 = await rewriteDesktopRelease(join(bundleDir, 'v1.0.1'), join(assetsRoot, 'v1.0.1'), '1.0.1');
  const v3 = await rewriteDesktopRelease(join(bundleDir, 'v1.0.2'), join(assetsRoot, 'v1.0.2'), '1.0.2');

  // Copy feat-781 lightweight Windows artifacts for coexistence & takeover test
  if (existsSync(join(bundleDir, 'feat781'))) {
    await mkdir(join(assetsRoot, 'feat781'), { recursive: true });
    for (const name of await readdir(join(bundleDir, 'feat781'))) {
      await copyFile(join(bundleDir, 'feat781', name), join(assetsRoot, 'feat781', name));
    }
    if (existsSync(join(bundleDir, 'feat781', 'manifest.win32-x64.json'))) {
      await copyFile(join(bundleDir, 'feat781', 'manifest.win32-x64.json'), join(releaseDir, 'manifest.win32-x64.json'));
    }
  }

  // Seed initial IM manifests (v1.0.0)
  const commit = v1.manifest.source_commit;
  await writeFile(
    join(releaseDir, 'manifest.json'),
    JSON.stringify(
      {
        version: '1.0.0',
        source_commit: commit,
        updater_protocol: 1,
        data_epoch: 1,
        package: 'nano-node.tgz',
        node_major: 24,
        pnpm_version: '11.7.0',
        sha256: '1'.repeat(64),
        download_url: 'https://github.com/Mrchen116/nano-multiagent/releases/download/v1.0.0/nano-node.tgz',
      },
      null,
      2,
    ) + '\n',
  );
  await writeFile(
    join(releaseDir, 'manifest.desktop-darwin-arm64.json'),
    JSON.stringify(
      {
        ...v1.manifest,
        platform: 'desktop-darwin-arm64',
        package: 'desktop-darwin-arm64.json',
        download_url: 'https://github.com/Mrchen116/nano-multiagent/releases/download/v1.0.0/desktop-darwin-arm64.json',
        installer: {
          download_url: 'https://github.com/Mrchen116/nano-multiagent/releases/download/v1.0.0/Crewden-Desktop-arm64.dmg',
          size: 89092913,
          sha256: '2'.repeat(64),
        },
      },
      null,
      2,
    ) + '\n',
  );
  await copyFile(join(assetsRoot, 'v1.0.0', 'manifest.desktop-win32-x64.json'), join(releaseDir, 'manifest.desktop-win32-x64.json'));

  const packagingSummary = {
    installerBytes: v1.manifest.installer.size,
    installerSha256: v1.manifest.installer.sha256,
    v1RuntimeBytes: v1.desc.runtime.size,
    v1RuntimeSha256: v1.desc.runtime.sha256,
    v1AppBytes: v1.desc.app.size,
    v1AppSha256: v1.desc.app.sha256,
    v2RuntimeBytes: v2.desc.runtime.size,
    v2RuntimeSha256: v2.desc.runtime.sha256,
    v2AppBytes: v2.desc.app.size,
    v2AppSha256: v2.desc.app.sha256,
    runtimeIdenticalAcrossV1AndV2: v1.desc.runtime.sha256 === v2.desc.runtime.sha256,
  };
  await writeFile(join(receiptsDir, 'packaging-summary.json'), JSON.stringify(packagingSummary, null, 2) + '\n');

  // 1. Start OpenAI-compatible SSE LLM Server on :18082
  const llm = await startSseLlmServer({
    host: hostIp,
    port: 18082,
    bigCommand: `powershell.exe -NoProfile -Command "[Console]::Write('WINBIG' * 3100000)"`,
  });

  // 2. Start Primary IM Server (:18080) and Secondary IM Server (:18083)
  const imDbPath = join(workDir, 'im-primary.db');
  const imSecret = randomUUID() + randomUUID();
  await exec(
    process.execPath,
    [
      join(repoRoot, 'apps/im-server/lib/main.js'),
      'init_admin',
      '--username',
      'nano',
      '--password',
      'nano1234',
      '--display-name',
      'Nano Owner',
      '--db-path',
      imDbPath,
    ],
    { env: { ...process.env, IM_JWT_SECRET: imSecret } },
  );

  // Pre-seed active users `nano` (with colleague `bob` for background notification & foreign-owner tests)
  const primaryChild = spawn(
    process.execPath,
    [join(repoRoot, 'apps/im-server/lib/main.js'), 'serve', '--host', hostIp, '--port', '18080'],
    {
      cwd: workDir,
      env: {
        ...process.env,
        IM_PUBLIC_URL: 'http://127.0.0.1:18080',
        IM_JWT_SECRET: imSecret,
        IM_DB_PATH: imDbPath,
        IM_NODE_RELEASE_DIR: releaseDir,
        IM_FRONTEND_DIST_DIR: join(repoRoot, 'src/IM/frontend/dist'),
        IM_TRAJECTORY_DIST_DIR: join(repoRoot, 'packages/dsh-trajectory-viewer/dist'),
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );
  primaryChild.stderr.on('data', (d) => process.stderr.write(`[IM1] ${d}`));

  const im2DbPath = join(workDir, 'im-secondary.db');
  const im2Secret = randomUUID() + randomUUID();
  await exec(
    process.execPath,
    [
      join(repoRoot, 'apps/im-server/lib/main.js'),
      'init_admin',
      '--username',
      'nano',
      '--password',
      'nano1234',
      '--display-name',
      'Nano Secondary',
      '--db-path',
      im2DbPath,
    ],
    { env: { ...process.env, IM_JWT_SECRET: im2Secret } },
  );
  const secondaryChild = spawn(
    process.execPath,
    [join(repoRoot, 'apps/im-server/lib/main.js'), 'serve', '--host', hostIp, '--port', '18083'],
    {
      cwd: workDir,
      env: {
        ...process.env,
        IM_PUBLIC_URL: 'http://127.0.0.1:18083',
        IM_JWT_SECRET: im2Secret,
        IM_DB_PATH: im2DbPath,
        IM_NODE_RELEASE_DIR: releaseDir,
        IM_FRONTEND_DIST_DIR: join(repoRoot, 'src/IM/frontend/dist'),
        IM_TRAJECTORY_DIST_DIR: join(repoRoot, 'packages/dsh-trajectory-viewer/dist'),
      },
      stdio: 'ignore',
    },
  );

  for (let i = 0; i < 60; i++) {
    try {
      const r1 = await fetch(`http://${hostIp}:18080/health`);
      const r2 = await fetch(`http://${hostIp}:18083/health`);
      if (r1.ok && r2.ok) break;
    } catch {}
    await delay(300);
  }

  // Register active test accounts (`winfresh`, `winbob`) on primary IM
  for (const [u, dn] of [
    ['winfresh', '小林'],
    ['winbob', '阿哲'],
  ]) {
    await fetch(`http://${hostIp}:18080/im/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: u, password: 'Password123!', display_name: dn, locale: 'zh' }),
    });
  }
  {
    const db = new DatabaseSync(imDbPath);
    db.exec("UPDATE users SET membership_status='active', personal_space_enabled=1, locale='zh'");
    db.close();
  }

  // 3. Start Metered Asset & Admin Server on :18081
  const byteLedger = {};
  const requestLog = [];
  const assetServer = http.createServer(async (req, res) => {
    const urlPath = (req.url ?? '/').split('?')[0];
    if (urlPath === '/__admin/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, packagingSummary }));
      return;
    }
    if (req.method === 'POST' && urlPath === '/__admin/reset-ledger') {
      for (const k of Object.keys(byteLedger)) delete byteLedger[k];
      requestLog.length = 0;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true }));
      return;
    }
    if (req.method === 'GET' && urlPath === '/__admin/ledger') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ byteLedger, requestLog, packagingSummary }));
      return;
    }
    if (req.method === 'POST' && urlPath === '/__admin/publish-version') {
      let raw = '';
      for await (const c of req) raw += c;
      const { version } = JSON.parse(raw);
      const src = join(assetsRoot, `v${version}`, 'manifest.desktop-win32-x64.json');
      await copyFile(src, join(releaseDir, 'manifest.desktop-win32-x64.json'));
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, published: version }));
      return;
    }
    if (req.method === 'POST' && urlPath === '/__admin/seed-remote-node') {
      let raw = '';
      for await (const c of req) raw += c;
      const { owner_id } = JSON.parse(raw);
      const nowIso = new Date().toISOString();
      const db = new DatabaseSync(imDbPath);
      db.prepare(
        "INSERT OR REPLACE INTO nodes(node_id,owner_id,node_name,status,last_heartbeat_at,agent_count,version) VALUES('node-remote-build',?,'Team-Build-Server','online',?,1,'2.4.0')",
      ).run(owner_id, nowIso);
      db.prepare(
        "INSERT OR REPLACE INTO node_binding_state(node_id,owner_id,node_epoch,runtime_token_hash) VALUES('node-remote-build',?,1,'hash-rem')",
      ).run(owner_id);
      db.prepare(
        "INSERT OR REPLACE INTO agent_profiles(agent_id,owner_id,space_id,node_id,display_name,work_mode,is_stale,created_at,updated_at) VALUES('remote-ci',?,'company:default','node-remote-build','Remote CI','global',0,?,?)",
      ).run(owner_id, nowIso, nowIso);
      db.close();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true }));
      return;
    }

    const rel = urlPath.replace(/^\/+/, '');
    const filePath = resolve(join(assetsRoot, rel));
    if (!filePath.startsWith(assetsRoot)) {
      res.writeHead(403);
      res.end('forbidden');
      return;
    }
    try {
      const data = await readFile(filePath);
      byteLedger[urlPath] = (byteLedger[urlPath] ?? 0) + data.byteLength;
      requestLog.push({ method: req.method, path: urlPath, bytes: data.byteLength, at: new Date().toISOString() });
      res.writeHead(200, {
        'Content-Type': urlPath.endsWith('.json') ? 'application/json' : 'application/octet-stream',
        'Content-Length': String(data.byteLength),
      });
      res.end(data);
    } catch {
      res.writeHead(404);
      res.end('not found');
    }
  });
  await new Promise((r) => assetServer.listen(18081, hostIp, r));

  // 4. Start Receipt & Screenshot Receiver on :8078
  const receiptServer = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const body = Buffer.concat(chunks);
    const rawPath = (req.url ?? '/').split('?')[0].replace(/^\/+/, '');
    if (rawPath.startsWith('screenshots/')) {
      const safe = basename(rawPath);
      if (safe.endsWith('.png')) {
        await writeFile(join(receiptsDir, 'screenshots', safe), body);
      }
    } else {
      const safe = basename(rawPath).replace(/[^a-zA-Z0-9._-]/g, '');
      if (safe) {
        const outName = safe.endsWith('.json') ? safe : `${safe}.json`;
        await writeFile(join(receiptsDir, outName), body);
      }
    }
    res.writeHead(200);
    res.end('ok');
  });
  await new Promise((r) => receiptServer.listen(8078, hostIp, r));

  await writeFile(join(workDir, 'host-stack-ready.json'), JSON.stringify({ ready: true, at: new Date().toISOString() }));
  console.log(`[HOST-STACK] Ready on ${hostIp} (IM :18080/:18083, Assets :18081, LLM :18082, Receipts :8078)`);

  const cleanup = async () => {
    primaryChild.kill();
    secondaryChild.kill();
    await llm.close().catch(() => {});
    assetServer.close();
    receiptServer.close();
    process.exit(0);
  };
  process.on('SIGINT', cleanup);
  process.on('SIGTERM', cleanup);
}

main().catch((err) => {
  console.error('[HOST-STACK ERROR]', err);
  process.exit(1);
});
