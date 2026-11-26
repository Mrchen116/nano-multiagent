/**
 * Clean Windows 10 & Windows 11 Guest End-to-End Verifier for Crewden Desktop (M2).
 *
 * Executed via the unpacked bundled official Node v24.22.1 (`runtime\node.exe`) while
 * the standard `nanoqa` user's system PATH has zero Node/npm/pnpm and WSL disabled.
 */
import assert from 'node:assert/strict';
import http from 'node:http';
import { randomBytes, randomUUID } from 'node:crypto';
import { execFile, spawn } from 'node:child_process';
import { promisify } from 'node:util';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const exec = promisify(execFile);
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

const [phase, edition, hostIp, labDir, desktopExeArg, f781VerRoot, wv2Version] = process.argv.slice(2);
const imOrigin = 'http://127.0.0.1:18080';
const im2Origin = 'http://127.0.0.1:18083';
const assetAdminOrigin = 'http://127.0.0.1:18081';

async function pushReceipt(name, payload) {
  const text = JSON.stringify(payload, null, 2) + '\n';
  await writeFile(join(labDir, name), text, 'utf8');
  await fetch(`http://${hostIp}:8078/${name}`, {
    method: 'PUT',
    body: text,
    signal: AbortSignal.timeout(5000),
  }).catch(() => {});
}

async function captureDesktopScreenshot(fileName, focusPid = null) {
  const outPath = join(labDir, 'screenshots', fileName);
  const ps = `
    Add-Type -AssemblyName System.Windows.Forms, System.Drawing
    Add-Type 'using System; using System.Runtime.InteropServices; public static class Dpi { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow); }'
    [Dpi]::SetProcessDPIAware() | Out-Null
    ${
      focusPid
        ? `$p = Get-Process -Id ${Number(focusPid)} -ErrorAction SilentlyContinue; if ($p -and $p.MainWindowHandle -ne [IntPtr]::Zero) { [Dpi]::ShowWindow($p.MainWindowHandle, 9) | Out-Null; [Dpi]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 500 }`
        : ''
    }
    $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
    $bmp.Save(${JSON.stringify(outPath)}, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
  `;
  await exec('powershell.exe', ['-NoProfile', '-Command', ps], { windowsHide: true });
  const bytes = await readFile(outPath);
  await fetch(`http://${hostIp}:8078/screenshots/${fileName}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'image/png' },
    body: bytes,
    signal: AbortSignal.timeout(10000),
  }).catch(() => {});
}

async function pollUntil(label, fn, timeoutMs = 90_000, intervalMs = 500) {
  const deadline = Date.now() + timeoutMs;
  let lastErr;
  while (Date.now() < deadline) {
    try {
      const v = await fn();
      if (v) return v;
    } catch (e) {
      lastErr = e;
    }
    await delay(intervalMs);
  }
  throw new Error(`Timed out waiting for ${label}${lastErr ? `: ${lastErr.message ?? lastErr}` : ''}`);
}

async function imApi(origin, token, path, body, method = body ? 'POST' : 'GET') {
  const res = await fetch(`${origin}/im/v1${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      'Idempotency-Key': randomUUID(),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
    signal: AbortSignal.timeout(45000),
  });
  if (!res.ok) {
    throw new Error(`${method} ${path} -> ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

async function hostReq(hostState, capCookie, path, { method = 'GET', token, body, internal = false } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (internal) {
    headers['x-crewden-reload-token'] = hostState.reload_token;
  } else {
    headers.Cookie = capCookie;
    headers.Origin = `http://127.0.0.1:${hostState.port}`;
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`http://127.0.0.1:${hostState.port}${path}`, {
    method,
    headers,
    redirect: 'manual',
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    signal: AbortSignal.timeout(240000),
  });
  const text = await res.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {}
  return { status: res.status, headers: res.headers, json, text };
}

async function obtainCapCookie(hostState) {
  const res = await fetch(
    `http://127.0.0.1:${hostState.port}/desktop/bootstrap?nonce=${encodeURIComponent(hostState.boot_nonce)}&next=/chat`,
    { redirect: 'manual' },
  );
  assert.equal(res.status, 307);
  const setCookie = res.headers.get('set-cookie') ?? '';
  const match = setCookie.match(/(__crewden_desktop_cap=[^;]+)/);
  assert.ok(match, `Missing capability cookie in ${setCookie}`);
  return match[1];
}

async function runStep1() {
  assert.equal(process.version, 'v24.22.1', `Expected bundled Node v24.22.1, got ${process.version}`);
  const report = { edition, node_version: process.version, webview2_version: wv2Version, phases: {} };

  const nanoLogin = await imApi(imOrigin, null, '/auth/login', { username: 'nano', password: 'nano1234' });
  const bobLogin = await imApi(imOrigin, null, '/auth/login', { username: 'winbob', password: 'Password123!' });

  // Phase 1: Verify /im/v1/onboarding exposes desktop_win32_x64 & desktop_darwin_arm64
  const onboarding = await imApi(imOrigin, nanoLogin.access_token, '/onboarding');
  assert.ok(onboarding.install?.desktop_win32_x64?.download_url?.endsWith('Crewden-Desktop-Setup-x64.exe'));
  assert.ok(onboarding.install?.desktop_win32_x64?.connect_url?.startsWith('crewden-desktop://connect?origin='));
  assert.ok(onboarding.install?.desktop_darwin_arm64?.download_url?.endsWith('Crewden-Desktop-arm64.dmg'));
  report.phases.onboarding_materials = onboarding.install;
  await pushReceipt('progress.json', { phase: '1_onboarding_verified', edition });

  // Phase 2: Start standalone feat-781 node first so we prove real coexistence & takeover!
  const f781NodeBin = join(f781VerRoot, 'runtime', 'node.exe');
  const f781Cli = join(f781VerRoot, 'apps', 'node', 'lib', 'cli.js');
  const { bootstrapNode } = await import(pathToFileURL(join(f781VerRoot, 'apps/node/lib/bootstrap.js')).href);
  const bootCfg = await bootstrapNode(imOrigin);
  const configPath = bootCfg.path;
  const connDir = dirname(configPath);

  await new Promise((resolve, reject) => {
    const child = spawn(f781NodeBin, [f781Cli, 'setup', '--im-service-url', imOrigin], { windowsHide: true });
    let out = '', approved = false;
    child.stdout.on('data', async (chunk) => {
      out += chunk.toString();
      const m = out.match(/http:\/\/127\.0\.0\.1:18080\/bind\/confirm#token=([a-zA-Z0-9_.=-]+)/);
      if (m && !approved) {
        approved = true;
        try {
          await imApi(imOrigin, nanoLogin.access_token, '/device-binding/inspect', { browser_token: m[1] });
          await imApi(imOrigin, nanoLogin.access_token, '/device-binding/accept', { browser_token: m[1] });
        } catch (e) {
          reject(e);
        }
      }
    });
    child.stderr.on('data', (d) => (out += d.toString()));
    child.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`feat-781 setup failed (${code}): ${out.slice(-1000)}`))));
  });

  const f781State = await pollUntil('feat-781 standalone node ready & online', async () => {
    const st = JSON.parse(await readFile(join(connDir, '.gateway-state.json'), 'utf8'));
    const ob = await imApi(imOrigin, nanoLogin.access_token, '/onboarding');
    const online = ob.nodes.some((n) => n.status === 'online');
    return st.ready && online ? st : null;
  }, 150_000, 1000);

  const f781TaskCheck = (
    await exec('powershell.exe', [
      '-NoProfile',
      '-Command',
      "@(Get-ScheduledTask | Where-Object { $_.TaskName -like 'Crewden-Gateway-*' }).Count",
    ], { windowsHide: true })
  ).stdout.trim();
  assert.equal(Number(f781TaskCheck), 1, 'Expected 1 active Crewden-Gateway-* Scheduled Task before takeover');

  const preservedMarker = join(connDir, 'preserve-across-takeover.txt');
  await writeFile(preservedMarker, 'feat-781-data-intact', 'utf8');
  await pushReceipt('progress.json', { phase: '2_feat781_running', f781Pid: f781State.pid });

  // Phase 3: Launch real CrewdenDesktop.exe GUI, test server switch, foreign-owner guard (winbob), and smooth takeover (nano)!
  const desktopChild = spawn(desktopExeArg, ['--im-origin', imOrigin], {
    detached: true,
    stdio: 'ignore',
    env: {
      ...process.env,
      NANO_ALLOW_LOOPBACK_UPDATE_HTTP: '1',
      NANO_LOOPBACK_RELEASE_ORIGIN: assetAdminOrigin,
    },
  });
  desktopChild.unref();

  const hostStatePath = join(process.env.LOCALAPPDATA, 'CrewdenDesktop', 'host-state.json');
  const hostState = await pollUntil('CrewdenDesktop host-state ready', async () => {
    if (!existsSync(hostStatePath)) return null;
    const hs = JSON.parse(await readFile(hostStatePath, 'utf8'));
    const r = await fetch(`http://127.0.0.1:${hs.port}/desktop/internal/status`, {
      headers: { 'x-crewden-reload-token': hs.reload_token },
    }).catch(() => null);
    return r?.ok ? hs : null;
  }, 240_000, 500);
  const capCookie = await obtainCapCookie(hostState);

  // Server switch round-trip (:18080 -> :18083 -> :18080)
  const sw1 = await hostReq(hostState, capCookie, '/desktop/v1/server', { method: 'PUT', body: { im_origin: im2Origin } });
  assert.equal(sw1.status, 200);
  const ctx2 = await hostReq(hostState, capCookie, '/desktop/v1/context');
  assert.equal(ctx2.json.im_origin, im2Origin);
  const swBack = await hostReq(hostState, capCookie, '/desktop/v1/server', { method: 'PUT', body: { im_origin: imOrigin } });
  assert.equal(swBack.status, 200);

  // Foreign-owner protection as winbob
  const bobHostAuth = await hostReq(hostState, capCookie, '/im/v1/auth/login', {
    method: 'POST',
    body: { username: 'winbob', password: 'Password123!' },
  });
  assert.equal(bobHostAuth.status, 200);
  const bobTok = bobHostAuth.json.access_token;
  const bobInspect = await hostReq(hostState, capCookie, '/desktop/v1/local-node/inspect', { token: bobTok });
  assert.equal(bobInspect.json.ownership, 'foreign_owner');
  assert.equal(bobInspect.json.environment, undefined);
  assert.equal(bobInspect.json.logs, undefined);
  const bobLife = await hostReq(hostState, capCookie, '/desktop/v1/local-node/lifecycle', {
    method: 'POST',
    token: bobTok,
    body: { action: 'stop' },
  });
  assert.equal(bobLife.status, 403);
  const bobUnconfirmed = await hostReq(hostState, capCookie, '/desktop/v1/local-node/connect', {
    method: 'POST',
    token: bobTok,
    body: { confirm_transfer: false },
  });
  assert.equal(bobUnconfirmed.status, 409);

  // Switch to owner `nano` and smoothly take over feat-781 node!
  const nanoHostAuth = await hostReq(hostState, capCookie, '/im/v1/auth/login', {
    method: 'POST',
    body: { username: 'nano', password: 'nano1234' },
  });
  assert.equal(nanoHostAuth.status, 200);
  const nanoTok = nanoHostAuth.json.access_token;
  const preTakeover = await hostReq(hostState, capCookie, '/desktop/v1/local-node/inspect', { token: nanoTok });
  assert.equal(preTakeover.json.ownership, 'takeover_available');
  const originalNodeId = preTakeover.json.node_id;

  const takeoverRes = await hostReq(hostState, capCookie, '/desktop/v1/local-node/connect', {
    method: 'POST',
    token: nanoTok,
    body: {},
  });
  assert.equal(takeoverRes.status, 200, `Takeover failed: ${takeoverRes.text}`);
  assert.equal(takeoverRes.json.node_id, originalNodeId);

  // Verify feat-781 task was retired while .windows-active.json, Crewden.lnk, crewden://, and data remain intact!
  const postTaskCounts = JSON.parse(
    (
      await exec('powershell.exe', [
        '-NoProfile',
        '-Command',
        `@{
          standaloneTasks = @(Get-ScheduledTask | Where-Object { $_.TaskName -like 'Crewden-Gateway-*' }).Count
          desktopTasks = @(Get-ScheduledTask | Where-Object { $_.TaskName -like 'CrewdenDesktop-*' -and $_.TaskName -notlike '*-Update' }).Count
          runReg = (Get-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -Name 'CrewdenDesktop' -ErrorAction SilentlyContinue).CrewdenDesktop
          crewdenUri = (Get-Item 'HKCU:\\Software\\Classes\\crewden\\shell\\open\\command').GetValue('')
          desktopUri = (Get-Item 'HKCU:\\Software\\Classes\\crewden-desktop\\shell\\open\\command').GetValue('')
          crewdenLnk = Test-Path (Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs\\Crewden.lnk')
          desktopLnk = Test-Path (Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs\\Crewden Desktop.lnk')
          oldPidAlive = [bool](Get-Process -Id ${f781State.pid} -ErrorAction SilentlyContinue)
        } | ConvertTo-Json -Compress`,
      ], { windowsHide: true })
    ).stdout.trim(),
  );
  assert.equal(postTaskCounts.standaloneTasks, 0, 'Standalone Crewden-Gateway-* task should be retired');
  assert.equal(postTaskCounts.desktopTasks, 1, 'CrewdenDesktop-* task should be registered');
  assert.ok(String(postTaskCounts.runReg).includes('--background'), 'HKCU Run CrewdenDesktop --background must be set');
  assert.equal(postTaskCounts.crewdenLnk, true, 'feat-781 Crewden.lnk must remain intact');
  assert.equal(postTaskCounts.desktopLnk, true, 'Crewden Desktop.lnk must exist');
  assert.equal(postTaskCounts.oldPidAlive, false, 'Old feat-781 gateway PID must have exited cleanly');
  assert.equal(existsSync(join(connDir, '.windows-active.json')), true, '.windows-active.json must be preserved');
  assert.equal(await readFile(preservedMarker, 'utf8'), 'feat-781-data-intact');
  report.phases.coexistence_and_takeover = { passed: true, node_id: originalNodeId, postTaskCounts };
  await pushReceipt('progress.json', { phase: '3_takeover_verified', node_id: originalNodeId });

  // Phase 4: Configure model, create Personal Assistant, verify chat reply & GUI screenshots
  await pollUntil('taken-over node online in IM', async () => {
    const ob = await imApi(imOrigin, nanoTok, '/onboarding');
    return ob.nodes.some((n) => n.node_id === originalNodeId && n.status === 'online');
  }, 90_000, 1000);

  let modelSetup = await imApi(imOrigin, nanoTok, `/nodes/${originalNodeId}/setup`, { action: 'status' });
  modelSetup = await imApi(imOrigin, nanoTok, `/nodes/${originalNodeId}/setup`, {
    action: 'save',
    revision: modelSetup.revision,
    source: 'custom',
    display_name: 'Windows QA Model',
    protocol: 'openai-completions',
    base_url: 'http://127.0.0.1:18082/v1',
    api_key: 'win-qa-secret',
    models: [{ id: 'crewden-win-qa', context_window: 128000, max_tokens: 8192, input: ['text'] }],
  });
  await pollUntil('model setup succeeded', async () => {
    const s = await imApi(imOrigin, nanoTok, `/nodes/${originalNodeId}/setup`, { action: 'status' });
    if (s.operation?.state === 'failed') throw new Error('Model setup failed: ' + JSON.stringify(s));
    return s.operation?.state === 'succeeded' && s.default_model ? s : null;
  }, 120_000, 1000);

  let pa = await imApi(imOrigin, nanoTok, '/personal-agent', {
    request_key: `win-${edition}-pa`,
    node_id: originalNodeId,
    display_name: '桌面助手',
  });
  pa = await pollUntil('PA active', async () => {
    const cur = await imApi(imOrigin, nanoTok, '/personal-agent');
    return cur.binding?.status === 'active' && !cur.creation ? cur : null;
  }, 120_000, 1000);
  const paAgentId = pa.binding.agent_id;
  const paConvId = pa.binding.conversation_id;

  await imApi(imOrigin, nanoTok, `/conversations/${paConvId}/messages`, {
    sender: { type: 'user', id: nanoLogin.user.id },
    content: 'What is 24 + 18?',
    attachments: [],
    timezone: 'UTC',
  });
  const mathReply = await pollUntil('PA reply 42', async () => {
    const m = await imApi(imOrigin, nanoTok, `/conversations/${paConvId}/messages?limit=20`);
    const items = (m.items ?? m).map((x) => x.message ?? x);
    return items.find((x) => x.sender?.type === 'agent' && String(x.content).includes('42')) ?? null;
  }, 120_000, 1000);

  // Navigate WebView2 window into authenticated chat & capture real GUI screenshot!
  await hostReq(hostState, capCookie, '/desktop/internal/activate-notification', {
    method: 'POST',
    internal: true,
    body: { route: `/chat/${paConvId}` },
  });
  await delay(3000);
  await captureDesktopScreenshot(`${edition}-02-chat-reply-gui.png`);
  report.phases.first_chat_reply = { passed: true, paAgentId, paConvId, reply: mathReply.content };
  await pushReceipt('progress.json', { phase: '4_chat_reply_verified', reply: mathReply.content });

  // Phase 5: Close main window (WM_CLOSE -> hides to tray), verify background /im/ws/user notifications & wakeup!
  await exec('powershell.exe', [
    '-NoProfile',
    '-Command',
    `Add-Type 'using System; using System.Runtime.InteropServices; public static class W { [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l); }'
     $p = Get-Process -Id ${hostState.pid} -ErrorAction SilentlyContinue
     if ($p -and $p.MainWindowHandle -ne [IntPtr]::Zero) { [W]::PostMessage($p.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null }`,
  ], { windowsHide: true });
  await delay(1500);
  // Also explicitly mark window unfocused/hidden if WM_CLOSE hid it
  await hostReq(hostState, capCookie, '/desktop/internal/window-attention', {
    method: 'POST',
    internal: true,
    body: { visible_and_focused: false, current_route: '/chat' },
  });

  await pollUntil('Rust /im/ws/user daemon connected', async () => {
    const st = await hostReq(hostState, capCookie, '/desktop/internal/status', { internal: true });
    return st.json?.ws_connected ? st.json : null;
  }, 30_000, 400);

  const sharedGroup = await imApi(imOrigin, nanoTok, '/conversations', {
    title: 'Windows 协作群',
    type: 'group',
    participants: [
      { type: 'user', id: nanoLogin.user.id },
      { type: 'user', id: bobLogin.user.id },
    ],
  });
  await imApi(imOrigin, bobLogin.access_token, `/conversations/${sharedGroup.id}/messages`, {
    sender: { type: 'user', id: bobLogin.user.id },
    content: '普通后台消息测试',
    attachments: [],
    timezone: 'UTC',
  });
  await imApi(imOrigin, bobLogin.access_token, `/conversations/${sharedGroup.id}/messages`, {
    sender: { type: 'user', id: bobLogin.user.id },
    content: `<mention type="user" target_id="${nanoLogin.user.id}">@Nano</mention> 请查看紧急事项`,
    attachments: [],
    timezone: 'UTC',
  });

  const notifSnap = await pollUntil('background notifications captured', async () => {
    const n = await hostReq(hostState, capCookie, '/desktop/internal/notifications', { internal: true });
    const kinds = new Set((n.json?.items ?? []).map((x) => x.kind));
    return kinds.has('human_message') && kinds.has('mention') ? n.json : null;
  }, 30_000, 400);

  await hostReq(hostState, capCookie, '/desktop/internal/activate-notification', {
    method: 'POST',
    internal: true,
    body: { route: `/chat/${sharedGroup.id}` },
  });
  const woken = await pollUntil('window woken to group route', async () => {
    const st = await hostReq(hostState, capCookie, '/desktop/internal/status', { internal: true });
    return st.json?.current_route === `/chat/${sharedGroup.id}` ? st.json : null;
  }, 15_000, 300);

  // External link safe open check
  const extRes = await hostReq(hostState, capCookie, '/desktop/v1/open-external', {
    method: 'POST',
    body: { url: 'https://example.com/win-docs' },
  });
  assert.equal(extRes.status, 200);
  const blockedExt = await hostReq(hostState, capCookie, '/desktop/v1/open-external', {
    method: 'POST',
    body: { url: 'file:///C:/Windows/System32/calc.exe' },
  });
  assert.equal(blockedExt.status, 400);

  report.phases.background_tray_and_notifications = {
    passed: true,
    unreadTotal: notifSnap.unread_total,
    kinds: [...new Set(notifSnap.items.map((x) => x.kind))],
    wokenRoute: woken.current_route,
  };
  await pushReceipt('progress.json', { phase: '5_notifications_verified', unread: notifSnap.unread_total });

  // Phase 6: >16 MiB Local Direct Trajectory over Windows Named Pipe + Explorer Workspace Reveal & Executable Guard!
  const inspectForWs = await hostReq(hostState, capCookie, '/desktop/v1/local-node/inspect', { token: nanoTok });
  const paWsRoot = inspectForWs.json.agents.find((a) => a.agent_id === paAgentId).workspace_root;
  await mkdir(join(paWsRoot, 'reports'), { recursive: true });
  await mkdir(join(paWsRoot, 'scripts'), { recursive: true });
  await writeFile(join(paWsRoot, 'reports', 'win-summary.md'), '# Windows Local Summary\nReady.\n', 'utf8');
  await writeFile(join(paWsRoot, 'scripts', 'deploy.bat'), '@echo off\r\necho deploy\r\n', 'utf8');

  await imApi(imOrigin, nanoTok, `/conversations/${paConvId}/messages`, {
    sender: { type: 'user', id: nanoLogin.user.id },
    content: 'Run BIG_TRAJECTORY_TEST now',
    attachments: [],
    timezone: 'UTC',
  });
  await pollUntil('BIG_TRAJECTORY_TEST completed (>18MB stdout)', async () => {
    const m = await imApi(imOrigin, nanoTok, `/conversations/${paConvId}/messages?limit=20`);
    const items = (m.items ?? m).map((x) => x.message ?? x);
    return items.find((x) => x.sender?.type === 'agent' && String(x.content).includes('已完成Windows本地轨迹验证')) ?? null;
  }, 150_000, 1000);

  // Read root session_id from local node.sqlite3 (`sessions` / `canonical_sessions` in NodeStore)
  const { DatabaseSync } = await import('node:sqlite');
  const nodeDb = new DatabaseSync(join(connDir, '.dsh-runtime', originalNodeId, 'node.sqlite3'), { readOnly: true });
  const sessionRow =
    nodeDb
      .prepare('SELECT session_id FROM sessions WHERE agent_id=? AND conversation_id=? LIMIT 1')
      .get(paAgentId, `global:${paAgentId}`) ??
    nodeDb.prepare('SELECT session_id FROM canonical_sessions WHERE agent_id=? LIMIT 1').get(paAgentId) ??
    nodeDb.prepare('SELECT session_id FROM sessions WHERE agent_id=? LIMIT 1').get(paAgentId);
  nodeDb.close();
  assert.ok(sessionRow?.session_id, 'Expected persisted PA root session_id in node.sqlite3');
  const rootSessionId = sessionRow.session_id;

  const t0 = performance.now();
  const prepLocal = await hostReq(hostState, capCookie, '/desktop/v1/trajectory/prepare', {
    method: 'POST',
    token: nanoTok,
    body: { agent_id: paAgentId, session_id: rootSessionId },
  });
  assert.equal(prepLocal.status, 200);
  assert.equal(prepLocal.json.mode, 'local', `Expected local trajectory mode over Named Pipe, got ${prepLocal.text}`);

  const wsReady = await new Promise((resolve, reject) => {
    const req = http.request({
      hostname: '127.0.0.1',
      port: hostState.port,
      path: `/desktop/ws/trajectory?ticket=${encodeURIComponent(prepLocal.json.ticket)}&agent_id=${encodeURIComponent(paAgentId)}&session_id=${encodeURIComponent(rootSessionId)}`,
      method: 'GET',
      headers: {
        Connection: 'Upgrade',
        Upgrade: 'websocket',
        'Sec-WebSocket-Version': '13',
        'Sec-WebSocket-Key': randomBytes(16).toString('base64'),
        Cookie: capCookie,
        Origin: `http://127.0.0.1:${hostState.port}`,
      },
    });
    const timer = setTimeout(() => {
      req.destroy();
      reject(new Error('Timed out waiting for /desktop/ws/trajectory ready'));
    }, 15000);
    req.on('upgrade', (_res, socket, head) => {
      let buf = Buffer.from(head);
      const parseFrames = () => {
        while (buf.length >= 2) {
          const opcode = buf[0] & 0x0f;
          let len = buf[1] & 0x7f;
          let offset = 2;
          if (len === 126) {
            if (buf.length < 4) return;
            len = buf.readUInt16BE(2);
            offset = 4;
          } else if (len === 127) {
            if (buf.length < 10) return;
            len = Number(buf.readBigUInt64BE(2));
            offset = 10;
          }
          if (buf.length < offset + len) return;
          const payload = buf.subarray(offset, offset + len);
          buf = buf.subarray(offset + len);
          if (opcode === 0x01) {
            const msg = JSON.parse(payload.toString('utf8'));
            if (msg.type === 'ready') {
              clearTimeout(timer);
              socket.destroy();
              resolve(msg);
              return;
            }
            if (msg.type === 'failed') {
              clearTimeout(timer);
              socket.destroy();
              reject(new Error(msg.message));
              return;
            }
          }
        }
      };
      parseFrames();
      socket.on('data', (chunk) => {
        buf = Buffer.concat([buf, chunk]);
        parseFrames();
      });
      socket.on('error', (err) => {
        clearTimeout(timer);
        reject(err);
      });
    });
    req.on('response', (res) => {
      clearTimeout(timer);
      reject(new Error(`Unexpected HTTP status ${res.statusCode} on WS upgrade`));
    });
    req.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
    req.end();
  });
  const localTrajMs = Math.round((performance.now() - t0) * 10) / 10;

  // Remote node fallback check
  await fetch(`${assetAdminOrigin}/__admin/seed-remote-node`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ owner_id: nanoLogin.user.owner_id }),
  });
  const prepRemote = await hostReq(hostState, capCookie, '/desktop/v1/trajectory/prepare', {
    method: 'POST',
    token: nanoTok,
    body: { agent_id: 'remote-ci', session_id: 'remote-s1' },
  });
  assert.equal(prepRemote.json.mode, 'remote');

  // Workspace open / Explorer reveal / executable block / lowercase drive URL check
  const openMd = await hostReq(hostState, capCookie, '/desktop/v1/workspace/open', {
    method: 'POST',
    token: nanoTok,
    body: { agent_id: paAgentId, path: 'reports/win-summary.md', action: 'open' },
  });
  const lowerDriveUrl =
    'file:///' + join(paWsRoot, 'reports', 'win-summary.md').replace(/\\/g, '/').replace(/^([A-Z]):/, (_, d) => `${d.toLowerCase()}:`);
  const revealLowerUrl = await hostReq(hostState, capCookie, '/desktop/v1/workspace/open', {
    method: 'POST',
    token: nanoTok,
    body: { agent_id: paAgentId, path: lowerDriveUrl, action: 'reveal' },
  });
  const revealBat = await hostReq(hostState, capCookie, '/desktop/v1/workspace/open', {
    method: 'POST',
    token: nanoTok,
    body: { agent_id: paAgentId, path: 'scripts/deploy.bat', action: 'reveal' },
  });
  const blockedBat = await hostReq(hostState, capCookie, '/desktop/v1/workspace/open', {
    method: 'POST',
    token: nanoTok,
    body: { agent_id: paAgentId, path: 'scripts/deploy.bat', action: 'open' },
  });
  const blockedTraverse = await hostReq(hostState, capCookie, '/desktop/v1/workspace/open', {
    method: 'POST',
    token: nanoTok,
    body: { agent_id: paAgentId, path: '..\\outside.txt', action: 'reveal' },
  });
  assert.equal(openMd.status, 200);
  assert.equal(revealLowerUrl.status, 200);
  assert.equal(revealBat.status, 200);
  assert.equal(blockedBat.status, 403);
  assert.equal(blockedTraverse.status, 403);

  await hostReq(hostState, capCookie, '/desktop/internal/activate-notification', {
    method: 'POST',
    internal: true,
    body: { route: `/settings/agents/${paAgentId}?view=work` },
  });
  await delay(3000);
  await captureDesktopScreenshot(`${edition}-03-work-trajectory-gui.png`, hostState.pid);

  report.phases.local_trajectory_and_explorer = {
    passed: true,
    sessionId: rootSessionId,
    localTrajMs,
    trajectoryVersion: wsReady.version,
    remoteFallbackMode: prepRemote.json.mode,
    workspaceChecks: {
      openMd: openMd.status,
      revealLowerDriveUrl: revealLowerUrl.status,
      revealBat: revealBat.status,
      blockedBatOpen: blockedBat.status,
      blockedTraversal: blockedTraverse.status,
    },
  };
  await pushReceipt('progress.json', { phase: '6_trajectory_and_explorer_verified', localTrajMs });

  // Phase 7: `这台电脑` crash auto-recovery (taskkill /F) & config validation/rollback/save!
  await hostReq(hostState, capCookie, '/desktop/internal/activate-notification', {
    method: 'POST',
    internal: true,
    body: { route: '/settings/nodes' },
  });
  await delay(2500);
  await captureDesktopScreenshot(`${edition}-04-nodes-admin-gui.png`, hostState.pid);

  const beforeKill = JSON.parse(await readFile(join(connDir, '.gateway-state.json'), 'utf8'));
  await exec('taskkill.exe', ['/F', '/PID', String(beforeKill.pid)], { windowsHide: true });
  const afterKill = await pollUntil('Windows crash auto-recovery after taskkill /F', async () => {
    if (!existsSync(join(connDir, '.gateway-state.json'))) return null;
    const st = JSON.parse(await readFile(join(connDir, '.gateway-state.json'), 'utf8'));
    return st.ready && st.pid !== beforeKill.pid ? st : null;
  }, 90_000, 1000);

  const badSocks = await hostReq(hostState, capCookie, '/desktop/v1/local-node/config', {
    method: 'PUT',
    token: nanoTok,
    body: {
      worker_runtime: 'dsh',
      proxy: { enabled: true, url: 'socks5://127.0.0.1:9999', no_proxy: 'localhost,127.0.0.1,::1' },
      tool_approval_model: null,
      environment: [{ key: 'CUSTOM_WIN_FLAG', value: 'enabled' }],
    },
  });
  assert.equal(badSocks.status, 422);

  const goodCfg = await hostReq(hostState, capCookie, '/desktop/v1/local-node/config', {
    method: 'PUT',
    token: nanoTok,
    body: {
      worker_runtime: 'dsh',
      proxy: { enabled: false, url: '', no_proxy: 'localhost,127.0.0.1,::1' },
      tool_approval_model: null,
      environment: [
        { key: 'CUSTOM_WIN_FLAG', value: 'enabled' },
        { key: 'NANO_ALLOW_LOOPBACK_UPDATE_HTTP', value: '1' },
        { key: 'NANO_LOOPBACK_RELEASE_ORIGIN', value: assetAdminOrigin },
      ],
    },
  });
  assert.equal(goodCfg.status, 200, `Config save failed: ${goodCfg.text}`);
  report.phases.crash_recovery_and_config = {
    passed: true,
    killedPid: beforeKill.pid,
    recoveredPid: afterKill.pid,
    socksRejectedStatus: badSocks.status,
    savedRestarted: goodCfg.json.restarted,
  };
  await pushReceipt('progress.json', { phase: '7_crash_and_config_verified', recoveredPid: afterKill.pid });

  // Phase 8: Byte-Metered Windows Managed Update (1.0.0 -> 1.0.1 reusing runtime = 0 B) & 1.0.2-bad Automatic Rollback!
  await fetch(`${assetAdminOrigin}/__admin/reset-ledger`, { method: 'POST' });
  await fetch(`${assetAdminOrigin}/__admin/publish-version`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version: '1.0.1' }),
  });

  const avail101 = await pollUntil('IM sees 1.0.1 update available', async () => {
    const nodes = await imApi(imOrigin, nanoTok, '/nodes');
    const local = nodes.find((n) => n.node_id === originalNodeId);
    return local?.update?.available && local.update.target?.version === '1.0.1' ? local.update : null;
  }, 30_000, 500);

  await imApi(imOrigin, nanoTok, `/nodes/${encodeURIComponent(originalNodeId)}/update`, {
    request_id: randomUUID(),
    version: avail101.target.version,
    sha256: avail101.target.sha256,
  });

  const updated101 = await pollUntil('Windows 1.0.0 -> 1.0.1 update succeeded', async () => {
    const nodes = await imApi(imOrigin, nanoTok, '/nodes');
    const local = nodes.find((n) => n.node_id === originalNodeId);
    const st = local?.update?.operation?.state;
    if (st === 'failed' || st === 'rolled_back' || st === 'recovery_required') {
      throw new Error(`1.0.1 update unexpectedly failed: ${JSON.stringify(local.update)}`);
    }
    return st === 'succeeded' && local.version === '1.0.1' ? local : null;
  }, 180_000, 1000);

  const ledgerSnap = await (await fetch(`${assetAdminOrigin}/__admin/ledger`)).json();
  const rtBytes = ledgerSnap.byteLedger['/v1.0.1/desktop-runtime-win32-x64.tar.gz'] ?? 0;
  const appBytes = ledgerSnap.byteLedger['/v1.0.1/desktop-app-win32-x64.tar.gz'] ?? 0;
  assert.equal(rtBytes, 0, `Expected 0 B runtime download on 1.0.0->1.0.1, got ${rtBytes}`);
  assert.ok(appBytes > 0, 'Expected >0 B app archive download on 1.0.0->1.0.1');

  const activePtr101 = JSON.parse(await readFile(join(connDir, '.desktop-active.json'), 'utf8'));
  assert.equal(activePtr101.version, '1.0.1');
  assert.equal(activePtr101.runtime_reused, true);
  const buildNote = await hostReq(hostState, capCookie, '/build-note.txt');
  assert.equal(buildNote.text.trim(), 'upgraded-1.0.1');
  await delay(1500);
  await captureDesktopScreenshot(`${edition}-05-updated-101-gui.png`, hostState.pid);

  // Broken 1.0.2 candidate rollback check
  await fetch(`${assetAdminOrigin}/__admin/publish-version`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version: '1.0.2' }),
  });
  const avail102 = await pollUntil('IM sees 1.0.2 candidate', async () => {
    const nodes = await imApi(imOrigin, nanoTok, '/nodes');
    const local = nodes.find((n) => n.node_id === originalNodeId);
    return local?.update?.available && local.update.target?.version === '1.0.2' ? local.update : null;
  }, 30_000, 500);

  await imApi(imOrigin, nanoTok, `/nodes/${encodeURIComponent(originalNodeId)}/update`, {
    request_id: randomUUID(),
    version: avail102.target.version,
    sha256: avail102.target.sha256,
  });

  const rolledBack = await pollUntil('1.0.2-bad automatically rolled back to 1.0.1', async () => {
    const nodes = await imApi(imOrigin, nanoTok, '/nodes');
    const local = nodes.find((n) => n.node_id === originalNodeId);
    const st = local?.update?.operation?.state;
    if (st === 'succeeded') throw new Error('Broken 1.0.2 candidate unexpectedly succeeded!');
    return st === 'rolled_back' && local.status === 'online' && local.version === '1.0.1' ? local : null;
  }, 180_000, 1000);

  report.phases.managed_update_and_rollback = {
    passed: true,
    upgradedVersion: updated101.version,
    byteLedger100To101: ledgerSnap.byteLedger,
    runtimeBytesTransferred: rtBytes,
    appBytesTransferred: appBytes,
    runtimeReused: activePtr101.runtime_reused,
    uiBuildNote: buildNote.text.trim(),
    rollbackState: rolledBack.update.operation.state,
    rollbackErrorCode: rolledBack.update.operation.error_code,
    versionAfterRollback: rolledBack.version,
  };

  await writeFile(
    join(labDir, 'reboot-context.json'),
    JSON.stringify({ nodeId: originalNodeId, paAgentId, paConvId, configPath, connDir }, null, 2),
    'utf8',
  );
  await pushReceipt('step1-result.json', report);
}

async function runStep2() {
  // Post-Reboot #1: Autostart is ON -> CrewdenDesktop --background & CrewdenDesktop-* task must start automatically!
  const ctx = JSON.parse(await readFile(join(labDir, 'reboot-context.json'), 'utf8'));
  const nanoLogin = await imApi(imOrigin, null, '/auth/login', { username: 'nano', password: 'nano1234' });
  const nanoTok = nanoLogin.access_token;

  const hostStatePath = join(process.env.LOCALAPPDATA, 'CrewdenDesktop', 'host-state.json');
  const hostState = await pollUntil('CrewdenDesktop --background auto-started after reboot', async () => {
    if (!existsSync(hostStatePath)) return null;
    const hs = JSON.parse(await readFile(hostStatePath, 'utf8'));
    const r = await fetch(`http://127.0.0.1:${hs.port}/desktop/internal/status`, {
      headers: { 'x-crewden-reload-token': hs.reload_token },
    }).catch(() => null);
    if (!r?.ok) return null;
    return { hs, status: await r.json() };
  }, 120_000, 1000);

  // --background must keep main window hidden on login!
  assert.equal(hostState.status.window_focused, false, 'Expected silent --background tray startup without popping window');

  const gwState = await pollUntil('managed node online in IM after reboot', async () => {
    if (!existsSync(join(ctx.connDir, '.gateway-state.json'))) return null;
    const st = JSON.parse(await readFile(join(ctx.connDir, '.gateway-state.json'), 'utf8'));
    const nodes = await imApi(imOrigin, nanoTok, '/nodes');
    const local = nodes.find((n) => n.node_id === ctx.nodeId);
    return st.ready && local?.status === 'online' ? st : null;
  }, 150_000, 1000);

  // Verify real post-reboot chat reply works without opening any CLI or window!
  const sent = await imApi(imOrigin, nanoTok, `/conversations/${ctx.paConvId}/messages`, {
    sender: { type: 'user', id: nanoLogin.user.id },
    content: 'What is 19 + 23?',
    attachments: [],
    timezone: 'UTC',
  });
  const reply = await pollUntil('post-reboot PA reply', async () => {
    const m = await imApi(imOrigin, nanoTok, `/conversations/${ctx.paConvId}/messages?limit=20`);
    const items = (m.items ?? m).map((x) => x.message ?? x);
    return (
      items.find(
        (x) => x.sender?.type === 'agent' && x.created_at >= sent.created_at && String(x.content).includes('42'),
      ) ?? null
    );
  }, 120_000, 1000);

  // Now disable login autostart via Desktop API and verify live PID is NOT interrupted!
  const capCookie = await obtainCapCookie(hostState.hs);
  const offRes = await hostReq(hostState.hs, capCookie, '/desktop/v1/local-node/lifecycle', {
    method: 'POST',
    token: nanoTok,
    body: { action: 'autostart', enabled: false },
  });
  assert.equal(offRes.status, 200);
  assert.equal(offRes.json.autostart, false);

  const afterToggle = JSON.parse(await readFile(join(ctx.connDir, '.gateway-state.json'), 'utf8'));
  assert.equal(afterToggle.pid, gwState.pid, 'Disabling autostart must not kill running node PID');

  const regCheck = (
    await exec('powershell.exe', [
      '-NoProfile',
      '-Command',
      "[bool](Get-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -Name 'CrewdenDesktop' -ErrorAction SilentlyContinue)",
    ], { windowsHide: true })
  ).stdout.trim();
  assert.equal(regCheck.toLowerCase(), 'false', 'HKCU Run CrewdenDesktop value must be removed when autostart=false');

  await pushReceipt('step2-reboot-autostart-on.json', {
    ok: true,
    edition,
    silentBackgroundWindowFocused: hostState.status.window_focused,
    autoStartedNodePid: gwState.pid,
    postRebootReply: reply.content,
    autostartDisabledWithoutKillingPid: afterToggle.pid === gwState.pid,
  });
}

async function runStep3() {
  // Post-Reboot #2: Autostart is OFF -> wait 25s after logon and verify nothing started!
  await delay(25_000);
  const ctx = JSON.parse(await readFile(join(labDir, 'reboot-context.json'), 'utf8'));
  const nanoLogin = await imApi(imOrigin, null, '/auth/login', { username: 'nano', password: 'nano1234' });

  const runningProcs = JSON.parse(
    (
      await exec('powershell.exe', [
        '-NoProfile',
        '-Command',
        "@(Get-Process | Where-Object { $_.ProcessName -match '^(CrewdenDesktop|crewden-desktop|DesktopGatewayHost|GatewayHost)$' } | Select-Object -ExpandProperty ProcessName) | ConvertTo-Json -Compress",
      ], { windowsHide: true })
    ).stdout.trim() || '[]',
  );
  const procList = Array.isArray(runningProcs) ? runningProcs : runningProcs ? [runningProcs] : [];
  assert.equal(procList.length, 0, `Expected zero Crewden processes when autostart=false, got ${JSON.stringify(procList)}`);

  const nodes = await imApi(imOrigin, nanoLogin.access_token, '/nodes');
  const local = nodes.find((n) => n.node_id === ctx.nodeId);
  assert.notEqual(local?.status, 'online', 'Node must remain offline after reboot when autostart=false');

  await pushReceipt('step3-reboot-autostart-off.json', {
    ok: true,
    edition,
    runningCrewdenProcesses: procList,
    imNodeStatus: local?.status ?? 'offline',
  });
}

if (phase === 'step1') {
  runStep1().catch(async (e) => {
    console.error(e);
    await pushReceipt('failed.json', { phase: 'step1', edition, error: e.message, stack: e.stack });
    process.exit(1);
  });
} else if (phase === 'step2') {
  runStep2().catch(async (e) => {
    console.error(e);
    await pushReceipt('failed.json', { phase: 'step2', edition, error: e.message, stack: e.stack });
    process.exit(1);
  });
} else if (phase === 'step3') {
  runStep3().catch(async (e) => {
    console.error(e);
    await pushReceipt('failed.json', { phase: 'step3', edition, error: e.message, stack: e.stack });
    process.exit(1);
  });
}
