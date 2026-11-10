import { expect, it } from 'vitest';
import { ToolSelection, defaultOffTools } from '../src/capabilities.js';
import { contextTools } from '../src/agent-context.js';
import { safeTools, unattendedFallbackAllows } from '../src/policy/approval.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import { BROWSER_ACT_ACTIONS, MAX_INPUT_TEXT, staticBrowserGuard, validateBrowserArguments } from '../src/browser/guard.js';
import { BROWSER_ACT_DESCRIPTION, BROWSER_READ_DESCRIPTION, installBrowserTools } from '../src/features/browser-control.js';
import { BROWSER_APPROVAL_REASON } from '../src/browser/contract.js';
import type { BrowserControl } from '../src/browser/control.js';

it('rejects non-http schemes, coordinate clicks, missing scroll anchors, and oversized text', () => {
  expect(validateBrowserArguments('browser_act', { action: 'open', url: 'file:///tmp/a.html' })).toMatchObject({ code: 'browser_navigation_rejected' });
  expect(validateBrowserArguments('browser_act', { action: 'open', url: 'javascript:alert(1)' })).toMatchObject({ code: 'browser_navigation_rejected' });
  expect(validateBrowserArguments('browser_act', { action: 'click', read_id: 'r1' })).toMatchObject({ code: 'browser_arguments_invalid' });
  expect(validateBrowserArguments('browser_act', { action: 'click', read_id: 'r1', ref: 'p1:0', x: 10, y: 20 })).toMatchObject({ code: 'browser_arguments_invalid' });
  expect(validateBrowserArguments('browser_act', { action: 'scroll', read_id: 'r1', ref: 'p1:0' })).toMatchObject({ code: 'browser_arguments_invalid' });
  expect(validateBrowserArguments('browser_act', { action: 'scroll', read_id: 'r1', delta_y: 100 })).toMatchObject({ code: 'browser_arguments_invalid' });
  expect(validateBrowserArguments('browser_act', { action: 'type', read_id: 'r1', ref: 'p1:0', text: 'x'.repeat(MAX_INPUT_TEXT + 1) })).toMatchObject({ code: 'browser_arguments_invalid' });
  expect(validateBrowserArguments('browser_act', { action: 'close' })).toMatchObject({ code: 'browser_arguments_invalid' });
  expect(validateBrowserArguments('browser_read', { max_chars: 20_001 })).toMatchObject({ code: 'browser_arguments_invalid' });
  expect(validateBrowserArguments('browser_act', { action: 'scroll', read_id: 'r1', ref: 'p1:0', delta_y: 600 })).toBeUndefined();
  expect(BROWSER_ACT_ACTIONS).toEqual(['open', 'click', 'type', 'scroll']);
});

it('guards platform, cooldown, window identity and presence before approval', () => {
  const args = { action: 'click', read_id: 'r1', ref: 'p1:0' };
  expect(staticBrowserGuard({ platform: 'linux', tool: 'browser_act', args })).toMatchObject({ code: 'browser_platform_unsupported' });
  expect(staticBrowserGuard({
    platform: 'darwin', tool: 'browser_act', args, now: 100,
    cooldown: { message: 'release failed', failedAt: 0, until: 300_100 },
  })).toMatchObject({ code: 'browser_foreground_release_failed', message: expect.stringContaining('release failed') });
  expect(staticBrowserGuard({
    platform: 'darwin', tool: 'browser_act', args, now: 300_100,
    cooldown: { message: 'release failed', failedAt: 0, until: 300_100 },
  })).toBeUndefined();
  expect(staticBrowserGuard({ platform: 'darwin', tool: 'browser_act', args: { ...args, window_id: '99' }, instance: { windowId: '10' } }))
    .toMatchObject({ code: 'browser_window_not_registered' });
  expect(staticBrowserGuard({ platform: 'darwin', tool: 'browser_act', args, needsLaunch: true, turnAllowed: false }))
    .toMatchObject({ code: 'browser_launch_requires_user_turn', message: expect.stringContaining('刷新在场窗口') });
  expect(staticBrowserGuard({ platform: 'darwin', tool: 'browser_act', args, needsLaunch: true, turnAllowed: true })).toBeUndefined();
});

it('registers both tools only on macOS with the required descriptions and schema', () => {
  const registered: { name: string; description: string; parameters: Record<string, unknown> }[] = [];
  const ctx = { tools: { register: (tool: { name: string; description: string; parameters: Record<string, unknown> }) => registered.push(tool) } };
  expect(installBrowserTools(ctx as never, { control: {} as BrowserControl, configuration: () => undefined, platform: 'linux' })).toBe(false);
  expect(registered).toEqual([]);
  expect(installBrowserTools(ctx as never, { control: {} as BrowserControl, configuration: () => undefined, platform: 'darwin' })).toBe(true);
  expect(registered.map(tool => tool.name)).toEqual(['browser_read', 'browser_act']);
  const read = registered[0]!; const act = registered[1]!;
  const readProps = (read.parameters.properties as Record<string, unknown>);
  const actProps = (act.parameters.properties as Record<string, unknown>);
  expect(read.parameters.additionalProperties).toBe(false);
  expect(act.parameters.additionalProperties).toBe(false);
  expect(actProps.x).toBeUndefined();
  expect(actProps.y).toBeUndefined();
  expect((actProps.action as { enum: string[] }).enum).toEqual(['open', 'click', 'type', 'scroll']);
  expect((actProps.action as { enum: string[] }).enum).not.toContain('close');
  expect(readProps.max_chars).toMatchObject({ type: 'integer', maximum: 20_000 });
});

it('keeps the model-visible contract sentences in both tool descriptions', () => {
  for (const description of [BROWSER_READ_DESCRIPTION, BROWSER_ACT_DESCRIPTION]) {
    expect(description).toContain('不抢焦点地操作页面；新窗口或首次接入可能短暂占前台');
    expect(description).toContain('只接受 ref，无坐标');
    expect(description).toContain('截图用 read_image 读 workspace 相对路径');
    expect(description).toContain('不下载、不上传');
    expect(description).toContain('浏览器自带弹层是噪声，不算失败');
    expect(description).toContain('非用户发起的轮次（含定时、心跳、任务续跑）及其后台派生的子 Agent 不能新开实例');
    expect(description).toContain('请用户再发一条消息以刷新在场窗口');
  }
  expect(BROWSER_READ_DESCRIPTION).toContain('read_id 只在最近一次 browser_read 后有效');
  expect(BROWSER_READ_DESCRIPTION).toContain('首次读取可能启动独立浏览器窗口并短暂占前台');
  expect(BROWSER_READ_DESCRIPTION).toContain('refs[].actions');
  expect(BROWSER_ACT_DESCRIPTION).toContain('没有 close 动作');
  expect(`${BROWSER_READ_DESCRIPTION}${BROWSER_ACT_DESCRIPTION}`).not.toContain('绝不打扰用户');
  expect(BROWSER_APPROVAL_REASON).toContain('不下载、不上传');
  expect(BROWSER_ACT_DESCRIPTION).toContain('登录、提交表单和发送网页消息');
  expect(BROWSER_APPROVAL_REASON).toContain('登录、提交表单和发送网页消息');
  expect(BROWSER_APPROVAL_REASON).toContain('要先读后做');
  expect(BROWSER_APPROVAL_REASON).toContain('不接受坐标点击');
});

it('keeps both tools default-off in the callable view', () => {
  const selection = new ToolSelection({ on: () => undefined } as never);
  const config = { agentId: 'a', revision: '1', provider: 'p', model: 'm' };
  expect(selection.selection(config as never, ['browser_read', 'browser_act', 'read'])).toEqual(['read']);
  expect(defaultOffTools).toEqual(expect.arrayContaining(['browser_read', 'browser_act']));
});

it('wires browser_read as safe and excludes browser_act from every automatic fallback', () => {
  expect(safeTools.has('browser_read')).toBe(true);
  expect(safeTools.has('browser_act')).toBe(false);
  expect(contextTools.has('browser_act')).toBe(false);
  expect(approvalDefaults.alwaysAllowTools).not.toContain('browser_act');
  const approval = { ...approvalDefaults, unattendedFallback: 'allow' as const };
  expect(unattendedFallbackAllows('unattended', approval, 'browser_act')).toBe(false);
  expect(unattendedFallbackAllows('unattended', approval, 'bash')).toBe(true);
  expect(unattendedFallbackAllows('return_to_agent', approval, 'browser_act')).toBe(false);
  expect(unattendedFallbackAllows('interactive', approval, 'browser_act')).toBe(false);
  expect(unattendedFallbackAllows('unattended', { ...approval, unattendedFallback: 'deny' }, 'bash')).toBe(false);
});
