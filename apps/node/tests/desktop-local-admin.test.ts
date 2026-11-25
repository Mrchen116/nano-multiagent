import { chmod, mkdir, mkdtemp, readFile, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import {
  LocalAdminHttpError,
  controlLocalNodeLifecycle,
  inspectLocalNode,
  probeDesktopWorkers,
  resolveLocalWorkspaceTarget,
  updateLocalNodeConfig,
} from '../src/local-admin.js';
import { gatewayPlist } from '../src/lifecycle.js';

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
    ).rejects.toMatchObject({ status: 422, errorCode: 'invalid_config' });

    // 4. Valid proxy + env update writes 9 proxy keys cleanly while preserving NANO_OWNER_CONFIG_ROOT.
    await updateLocalNodeConfig({
      origin: 'https://im.example.com',
      ownerId: 'owner-alice',
      configPath,
      update: {
        worker_runtime: 'codex',
        proxy: { enabled: true, url: 'http://127.0.0.1:7890', no_proxy: 'localhost,127.0.0.1' },
        tool_approval_model: 'gpt-6',
        environment: [{ key: 'PATH', value: customBin }],
      },
    });
    const afterUpdate = await inspectLocalNode({ origin: 'https://im.example.com', ownerId: 'owner-alice', configPath });
    expect(afterUpdate.worker_runtime).toBe('codex');
    expect(afterUpdate.proxy).toEqual({ enabled: true, url: 'http://127.0.0.1:7890', no_proxy: 'localhost,127.0.0.1' });
    expect(afterUpdate.tool_approval_model).toBe('gpt-6');

    // 5. Autostart toggle writes only inside NANO_TEST_AUTOSTART_DIR without touching ~/Library/LaunchAgents.
    expect(gatewayPlist(configPath).startsWith(autostartDir)).toBe(true);
    await controlLocalNodeLifecycle({ origin: 'https://im.example.com', ownerId: 'owner-alice', action: 'autostart-on', configPath });
    expect(await readFile(gatewayPlist(configPath), 'utf8')).toContain(configPath);
    await controlLocalNodeLifecycle({ origin: 'https://im.example.com', ownerId: 'owner-alice', action: 'autostart-off', configPath });
    await expect(readFile(gatewayPlist(configPath), 'utf8')).rejects.toThrow();

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
        targetPath: 'reports/escape-link.txt',
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
