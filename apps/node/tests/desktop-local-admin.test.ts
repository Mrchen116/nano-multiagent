import { chmod, mkdir, mkdtemp, readFile, realpath, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { expect, it } from 'vitest';
import {
  LocalAdminHttpError,
  controlLocalNodeLifecycle,
  inspectLocalNode,
  probeDesktopWorkers,
  resolveLocalWorkspaceTarget,
  updateLocalNodeConfig,
} from '../src/local-admin.js';
import { LocalNodeBridge } from '../src/local-bridge.js';
import { gatewayPlist, processBirth } from '../src/lifecycle.js';

// The Windows candidate supplies a loopback SMB path in addition to its local drive.
const workspaceParents = [tmpdir(), ...(process.env.CREWDEN_TEST_UNC_PARENT ? [process.env.CREWDEN_TEST_UNC_PARENT] : [])];
it.each(workspaceParents)('resolves workspace file URLs against real files under %s', async parent => {
  const root = await mkdtemp(join(parent, 'crewden-file-url-'));
  try {
    const workspace = join(root, 'work');
    const configPath = join(root, 'config.yaml');
    await mkdir(workspace);
    await writeFile(configPath, JSON.stringify({
      node: { node_id: 'local', user_id: 'owner' },
      agents: [{ agent_id: 'agent', workspace_root: workspace }],
    }));
    const file = join(workspace, 'total #1 %20.pdf');
    await writeFile(file, 'report');
    const open = (targetPath: string) => resolveLocalWorkspaceTarget({
      origin: 'https://im.example', ownerId: 'owner', agentId: 'agent', mode: 'open', targetPath, configPath,
    });
    const url = pathToFileURL(file);
    await expect(open(url.href)).resolves.toMatchObject({ resolved_path: await realpath(file) });
    await expect(open(pathToFileURL(configPath).href)).rejects.toMatchObject({ status: 403, errorCode: 'outside_workspace' });

    // A different authority must never select the same pathname on the current host.
    url.hostname = 'other-server.invalid';
    await expect(open(url.href)).rejects.toMatchObject({ status: process.platform === 'win32' ? 403 : 400 });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

it('enforces owner_id isolation, probes workers with candidate PATH, validates empty-node approval models, toggles autostart in isolation, and blocks workspace escapes & executables', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-desktop-admin-'));
  const installRoot = join(root, 'nano-home');
  const autostartDir = join(root, 'autostart');
  const customBin = join(root, 'custom-bin');
  const workspace = join(root, 'workspaces', 'e1');
  const outside = join(root, 'outside-secret.txt');
  const prevInstall = process.env.NANO_INSTALL_ROOT;
  const prevAutostart = process.env.NANO_TEST_AUTOSTART_DIR;
  process.env.NANO_INSTALL_ROOT = installRoot;
  process.env.NANO_TEST_AUTOSTART_DIR = autostartDir;

  try {
    await mkdir(customBin, { recursive: true });
    await mkdir(join(workspace, 'reports'), { recursive: true });
    await mkdir(join(workspace, 'scripts'), { recursive: true });
    await writeFile(join(customBin, 'claude'), '#!/bin/sh\necho ok\n');
    await chmod(join(customBin, 'claude'), 0o755);
    await writeFile(join(workspace, 'reports', 'perf.md'), '# Report\n');
    await writeFile(join(workspace, 'scripts', 'run.sh'), '#!/bin/sh\necho hi\n');
    await writeFile(outside, 'secret');
    await symlink(outside, join(workspace, 'reports', 'escape-link.txt'));

    const configPath = join(installRoot, 'connections', 'test', 'config.yaml');
    await mkdir(join(installRoot, 'connections', 'test'), { recursive: true });
    await writeFile(
      join(installRoot, 'connections', 'test', 'gateway.log'),
      '[10:00:00] INFO gateway ready\n[10:01:00] WARN proxy retry\n',
    );
    await writeFile(
      configPath,
      JSON.stringify({
        node: { node_id: 'node-air', node_name: 'Air-Studio', user_id: 'owner-alice', workspace_base: join(root, 'workspaces') },
        im_service: { url: 'https://im.example.com', token: 'secret-runtime-token' },
        agents: [{ agent_id: 'e1', workspace_root: workspace, work_mode: 'global', default_model: 'gpt-6' }],
        gateway: {
          autostart: true,
          worker_runtime: 'dsh',
          environment: {
            NANO_OWNER_CONFIG_ROOT: installRoot,
            SEARXNG_URL: 'http://127.0.0.1:8888',
            PATH: customBin,
          },
        },
        llm: {
          default_model: 'gpt-6',
          providers: [{ name: 'openai', base_url: 'https://api.example.com', models: [{ name: 'gpt-6' }] }],
        },
      }),
    );

    // 1. Foreign owner receives ONLY ownership + node_name (no env, no logs, no workspaces) and gets 403 on mutations.
    const foreignInspect = await inspectLocalNode({ origin: 'https://im.example.com', ownerId: 'owner-bob', configPath });
    expect(foreignInspect).toEqual({ ownership: 'foreign_owner', node_name: 'Air-Studio' });
    await expect(
      controlLocalNodeLifecycle({ origin: 'https://im.example.com', ownerId: 'owner-bob', action: 'stop', configPath }),
    ).rejects.toMatchObject({ status: 403, errorCode: 'foreign_owner' });
    await expect(
      resolveLocalWorkspaceTarget({
        origin: 'https://im.example.com',
        ownerId: 'owner-bob',
        agentId: 'e1',
        targetPath: 'reports/perf.md',
        mode: 'open',
        configPath,
      }),
    ).rejects.toMatchObject({ status: 403, errorCode: 'foreign_owner' });

    // 2. Owner sees takeover_available (since .desktop-active.json not written yet), filtered logs, and customBin `claude`.
    const ownerInspect = await inspectLocalNode({
      origin: 'https://im.example.com',
      ownerId: 'owner-alice',
      configPath,
      logQuery: 'warn',
    });
    expect(ownerInspect.ownership).toBe('takeover_available');
    expect(ownerInspect.logs).toEqual(['[10:01:00] WARN proxy retry']);
    expect(ownerInspect.workers?.find(w => w.runtime === 'claude')?.available).toBe(true);
    expect(ownerInspect.environment).toEqual([
      { key: 'SEARXNG_URL', value: 'http://127.0.0.1:8888' },
      { key: 'PATH', value: customBin },
    ]);

    const supervision = await inspectLocalNode({ origin: 'https://im.example.com', ownerId: 'owner-alice', configPath, supervisionOnly: true });
    expect(supervision).toEqual({ ownership: 'takeover_available', node_name: 'Air-Studio', version: 'source', autostart: true, scheduled_at_login: false });

    const probed = await probeDesktopWorkers(customBin);
    expect(probed.find(w => w.runtime === 'claude')?.resolved_path).toBe(join(customBin, 'claude'));

    // 3. Rejects socks:// proxy and unregistered tool_approval_model even when agents=[].
    const emptyConfigPath = join(installRoot, 'connections', 'empty', 'config.yaml');
    await mkdir(join(installRoot, 'connections', 'empty'), { recursive: true });
    await writeFile(
      emptyConfigPath,
      JSON.stringify({
        node: { node_id: 'node-empty', user_id: 'owner-alice' },
        im_service: { url: 'https://im2.example.com', token: 'tok' },
        agents: [],
        llm: { default_model: '', providers: [] },
      }),
    );
    await expect(
      updateLocalNodeConfig({
        origin: 'https://im2.example.com',
        ownerId: 'owner-alice',
        configPath: emptyConfigPath,
        update: {
          worker_runtime: 'dsh',
          proxy: { enabled: false, url: '', no_proxy: '' },
          tool_approval_model: 'missing-model',
          environment: [],
        },
      }),
    ).rejects.toThrow(LocalAdminHttpError);

    await expect(
      updateLocalNodeConfig({
        origin: 'https://im.example.com',
        ownerId: 'owner-alice',
        configPath,
        update: {
          worker_runtime: 'codex',
          proxy: { enabled: true, url: 'socks5://127.0.0.1:1080', no_proxy: '' },
          tool_approval_model: null,
          environment: [],
        },
      }),
    ).rejects.toMatchObject({ status: 422, errorCode: 'invalid_proxy_scheme' });

    // 4. Accepts `antigravity` worker_runtime, blocks restart when active_tasks > 0 unless confirm_restart: true,
    //    and allows `stop` even when config has an unregistered tool_approval_model!
    await writeFile(join(customBin, 'agy'), '#!/bin/sh\necho ok\n');
    await chmod(join(customBin, 'agy'), 0o755);
    const probedWithAgy = await probeDesktopWorkers(customBin);
    expect(probedWithAgy.find(w => w.runtime === 'antigravity')?.available).toBe(true);

    const activeBridge = new LocalNodeBridge({
      configPath,
      nodeId: 'node-air',
      ownerId: () => 'owner-alice',
      nodeEpoch: () => 1,
      ready: () => true,
      connected: () => true,
      bindings: () => [],
      activeTasks: () => 2,
      runtime: { request: async () => ({}) },
    });
    const stateFile = join(installRoot, 'connections', 'test', '.gateway-state.json');
    const birth = await processBirth(process.pid);
    await writeFile(
      stateFile,
      JSON.stringify({ pid: process.pid, config_path: configPath, process_start: birth, ready: true }),
    );
    await activeBridge.start();
    try {
      await expect(
        updateLocalNodeConfig({
          origin: 'https://im.example.com',
          ownerId: 'owner-alice',
          configPath,
          update: {
            worker_runtime: 'antigravity',
            proxy: { enabled: true, url: 'http://127.0.0.1:7890', no_proxy: 'localhost,127.0.0.1' },
            tool_approval_model: 'gpt-6',
            environment: [{ key: 'PATH', value: customBin }],
          },
        }),
      ).rejects.toMatchObject({ status: 409, errorCode: 'active_tasks_running' });
    } finally {
      await activeBridge.close();
      await rm(stateFile, { force: true });
    }

    await updateLocalNodeConfig({
      origin: 'https://im.example.com',
      ownerId: 'owner-alice',
      configPath,
      update: {
        worker_runtime: 'antigravity',
        proxy: { enabled: true, url: 'http://127.0.0.1:7890', no_proxy: 'localhost,127.0.0.1' },
        tool_approval_model: 'gpt-6',
        environment: [{ key: 'PATH', value: customBin }],
      },
    });
    const afterUpdate = await inspectLocalNode({ origin: 'https://im.example.com', ownerId: 'owner-alice', configPath });
    expect(afterUpdate.worker_runtime).toBe('antigravity');
    expect(afterUpdate.proxy).toEqual({ enabled: true, url: 'http://127.0.0.1:7890', no_proxy: 'localhost,127.0.0.1' });
    expect(afterUpdate.tool_approval_model).toBe('gpt-6');

    await writeFile(
      emptyConfigPath,
      JSON.stringify({
        node: { node_id: 'node-empty', user_id: 'owner-alice' },
        im_service: { url: 'https://im2.example.com', token: 'tok' },
        agents: [],
        llm: { default_model: '', tool_approval_model: 'deleted-model', providers: [] },
      }),
    );
    const stoppedInvalid = await controlLocalNodeLifecycle({
      origin: 'https://im2.example.com',
      ownerId: 'owner-alice',
      action: 'stop',
      configPath: emptyConfigPath,
    });
    expect(stoppedInvalid.ok).toBe(true);

    // 5. Autostart toggle writes only inside NANO_TEST_AUTOSTART_DIR without touching ~/Library/LaunchAgents.
    expect(gatewayPlist(configPath).startsWith(autostartDir)).toBe(true);
    await controlLocalNodeLifecycle({ origin: 'https://im.example.com', ownerId: 'owner-alice', action: 'autostart-on', configPath });
    expect(await readFile(gatewayPlist(configPath), 'utf8')).toContain(configPath);
    await controlLocalNodeLifecycle({ origin: 'https://im.example.com', ownerId: 'owner-alice', action: 'autostart-off', configPath });
    await expect(readFile(gatewayPlist(configPath), 'utf8')).rejects.toThrow();

    // A failed native registration must restore the last saved preference.
    const brokenRegistration = gatewayPlist(configPath);
    await mkdir(brokenRegistration, { recursive: true });
    await expect(controlLocalNodeLifecycle({
      origin: 'https://im.example.com', ownerId: 'owner-alice', action: 'autostart-on', configPath,
    })).rejects.toThrow();
    expect((await inspectLocalNode({
      origin: 'https://im.example.com', ownerId: 'owner-alice', configPath, supervisionOnly: true,
    })).autostart).toBe(false);

    // 6. Workspace open allows regular files, blocks symlink escape, and blocks direct open on .sh while allowing reveal.
    const openedDoc = await resolveLocalWorkspaceTarget({
      origin: 'https://im.example.com',
      ownerId: 'owner-alice',
      agentId: 'e1',
      targetPath: 'reports/perf.md',
      mode: 'open',
      configPath,
    });
    expect(openedDoc.is_directory).toBe(false);

    await expect(
      resolveLocalWorkspaceTarget({
        origin: 'https://im.example.com',
        ownerId: 'owner-alice',
        agentId: 'e1',
        targetPath: pathToFileURL(join(workspace, 'reports', 'escape-link.txt')).href,
        mode: 'open',
        configPath,
      }),
    ).rejects.toMatchObject({ status: 403, errorCode: 'outside_workspace' });

    await expect(
      resolveLocalWorkspaceTarget({
        origin: 'https://im.example.com',
        ownerId: 'owner-alice',
        agentId: 'e1',
        targetPath: 'scripts/run.sh',
        mode: 'open',
        configPath,
      }),
    ).rejects.toMatchObject({ status: 403, errorCode: 'executable_open_blocked' });

    const revealedScript = await resolveLocalWorkspaceTarget({
      origin: 'https://im.example.com',
      ownerId: 'owner-alice',
      agentId: 'e1',
      targetPath: 'scripts/run.sh',
      mode: 'reveal',
      configPath,
    });
    expect(revealedScript.resolved_path).toContain('run.sh');
  } finally {
    if (prevInstall === undefined) delete process.env.NANO_INSTALL_ROOT;
    else process.env.NANO_INSTALL_ROOT = prevInstall;
    if (prevAutostart === undefined) delete process.env.NANO_TEST_AUTOSTART_DIR;
    else process.env.NANO_TEST_AUTOSTART_DIR = prevAutostart;
    await rm(root, { recursive: true, force: true });
  }
});
