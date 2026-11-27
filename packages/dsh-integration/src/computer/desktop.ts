import { randomUUID } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { z } from 'zod';
import type { ComputerBackend, ComputerContent, PreparedAction } from './backend.js';
import { cuaDriver, desktopStatus, verifyDesktopApp } from './desktop-status.js';
import { openMcp } from './mcp.js';

const appId = z
  .string()
  .max(255)
  .regex(/^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$/);
const id = z.number().int().positive();
const element = z.string().regex(/^s[0-9a-f]{8}:\d+$/);
const point = { x: z.number().int().nonnegative(), y: z.number().int().nonnegative() };
const noArgs = z.strictObject({});
const descriptions = {
  status: 'Show local CuaDriver permission status and setup guidance.',
  list_windows:
    '{app, title?}: exact macOS bundle identifier and optional exact window title. Returns matching window IDs.',
  bind: '{app, pid, window_id}: request access to this specific window.',
  snapshot: '{query?}: read visible accessibility elements and their tokens in the bound window.',
  screenshot: '{}: show the bound window.',
  click: '{element_token}: click a control in the last snapshot.',
  type: '{element_token, text}: type into a control in the last snapshot.',
  scroll: '{direction, amount?}: scroll the bound window up, down, left or right.',
  move: '{x,y}: move the synthetic cursor using pixels from the last window screenshot.',
  key: '{key}: tab, shift+tab, pageup, or pagedown in the bound window.',
  read_clipboard: '{}: read system clipboard text once on the node owner’s explicit clipboard assignment.',
};
const apps = z.object({
  apps: z.array(
    z.object({
      bundle_id: z.string().optional(),
      launch_path: z.string().optional(),
      pid: z.number().int(),
      running: z.boolean(),
      active: z.boolean(),
    }),
  ),
});
const windows = z.object({
  windows: z.array(
    z.object({
      pid: id,
      window_id: id,
      title: z.string().nullable(),
      layer: z.number(),
      is_on_screen: z.boolean(),
      z_index: z.number().nullable(),
    }),
  ),
});
type WindowTarget = { app: string; pid: number; window_id: number };
type BoundWindow = WindowTarget & {
  title: string;
  foreground: number | undefined;
  pixels: boolean;
  refs: Map<string, string>;
};
const text = (value: unknown): ComputerContent[] => [{ type: 'text', text: JSON.stringify(value) }];
const nav = z.enum(['tab', 'shift+tab', 'pageup', 'pagedown']);
type NavigationKey = z.infer<typeof nav>;
const navigationTTL = 30_000;

/** The host owns the MCP connection and all target identities for one task. */
export class DesktopBackend implements ComputerBackend {
  private connection?: ReturnType<typeof openMcp>;
  private stopped = false;
  private bound?: BoundWindow;
  private navigation?: { window: BoundWindow; key: NavigationKey; until: number };

  constructor(private readonly cwd?: string) {}

  private async client(signal: AbortSignal) {
    signal.throwIfAborted();
    if (this.stopped) throw new Error('Desktop task has ended.');
    if (!this.connection) {
      this.connection = (async () => {
        const status = await desktopStatus(signal);
        if (!status.available) throw new Error(status.message);
        return openMcp(cuaDriver, ['mcp']);
      })().catch((error) => {
        this.connection = undefined;
        throw error;
      });
    }
    const client = await this.connection;
    signal.throwIfAborted();
    if (this.stopped) throw new Error('Desktop task has ended.');
    return client;
  }

  private async lookup(app: string, signal: AbortSignal) {
    const client = await this.client(signal);
    const permissions = await client.callStructured('check_permissions', { prompt: false }, signal);
    if (permissions.accessibility !== true)
      throw new Error('Accessibility permission is required. Check CuaDriver.app permissions on the node.');
    const states = apps.parse(await client.callStructured('list_apps', {}, signal)).apps;
    const running = states.filter((entry) => entry.bundle_id === app && entry.running && entry.pid > 0);
    if (running.length !== 1)
      throw new Error('Open a single instance of the requested application, then list its windows.');
    await verifyDesktopApp(app, running[0]!.launch_path, signal);
    const pid = running[0]!.pid;
    const rows = windows
      .parse(await client.callStructured('list_windows', { pid }, signal))
      .windows.filter((row) => row.pid === pid && row.layer === 0);
    return {
      screenRecording: permissions.screen_recording === true,
      pid,
      rows,
      foreground: states.find((entry) => entry.running && entry.active)?.pid,
    };
  }

  private async inspect(target: WindowTarget, signal: AbortSignal) {
    const { pid, rows, foreground, screenRecording } = await this.lookup(target.app, signal);
    const row = rows.find((row) => row.window_id === target.window_id);
    if (pid !== target.pid || !row)
      throw new Error('Window identity changed. List windows and bind the intended window again.');
    return { row, foreground, rows, screenRecording };
  }

  private async current(bound: BoundWindow, input: boolean, signal: AbortSignal) {
    if (this.bound !== bound) throw new Error('Bind the intended window again.');
    try {
      const { row, foreground, rows, screenRecording } = await this.inspect(bound, signal);
      if (this.bound !== bound || (row.title ?? '') !== bound.title)
        throw new Error('Window changed. Bind the intended window again.');
      if (input) {
        if (!foreground || foreground !== bound.foreground)
          throw new Error('Frontmost application changed. Bind the window again before input.');
        if (
          foreground === bound.pid &&
          rows.some(
            (other) =>
              other.window_id !== row.window_id &&
              other.is_on_screen &&
              (other.z_index === null || row.z_index === null || other.z_index >= row.z_index),
          )
        ) {
          throw new Error('Another window may have focus. Bind the intended window again.');
        }
      }
      return { screenRecording };
    } catch (error) {
      if (this.bound === bound) this.bound = undefined;
      throw error;
    }
  }

  async prepare(action: string, input: Record<string, unknown>, signal: AbortSignal): Promise<PreparedAction> {
    signal.throwIfAborted();
    if (this.stopped) throw new Error('Desktop task has ended.');
    if (action === 'describe' || action === 'status') {
      noArgs.parse(input);
      return {
        access: 'observe',
        evidence: action,
        run: async (signal) => text(action === 'status' ? await desktopStatus(signal) : descriptions),
      };
    }
    if (action === 'read_clipboard') {
      noArgs.parse(input);
      return {
        access: 'system_clipboard',
        evidence: 'Read system clipboard text once',
        run: async (signal) => {
          const result = await (
            await this.client(signal)
          ).callStructured('clipboard_read', { include_text: true }, signal);
          if (typeof result.text !== 'string') throw new Error('The system clipboard has no plain text.');
          return [{ type: 'text', text: result.text }];
        },
      };
    }
    if (action === 'list_windows') {
      const { app, title } = z.strictObject({ app: appId, title: z.string().max(500).optional() }).parse(input);
      return {
        access: 'observe',
        evidence: app,
        run: async (signal) => {
          const { rows } = await this.lookup(app, signal);
          return text(
            rows
              .filter((row) => title === undefined || row.title === title)
              .map((row) => ({ app, pid: row.pid, window_id: row.window_id })),
          );
        },
      };
    }
    if (action === 'bind') {
      const target = z.strictObject({ app: appId, pid: id, window_id: id }).parse(input);
      const initial = await this.inspect(target, signal);
      const title = initial.row.title ?? '';
      return {
        access: 'review',
        evidence: JSON.stringify({ ...target, title }),
        window: {title,candidates:initial.rows.length},
        run: async (signal) => {
          const { row, foreground } = await this.inspect(target, signal);
          if ((row.title ?? '') !== title || foreground !== initial.foreground)
            throw new Error('Window or focus changed during binding. Bind again.');
          this.bound = { ...target, title, foreground, pixels: false, refs: new Map() };
          this.navigation = undefined;
          return text({ bound: target, title });
        },
      };
    }
    const bound = this.bound;
    if (!bound) throw new Error('List windows for the requested app and bind one window first.');
    const target = { kind: 'window', pid: bound.pid, window_id: bound.window_id };
    const identity = { pid: bound.pid, window_id: bound.window_id };
    const evidence = { ...identity, app: bound.app, title: bound.title, action };
    if (action === 'snapshot') {
      const args = z.strictObject({ query: z.string().min(1).max(250).optional() }).parse(input);
      return {
        access: 'observe',
        evidence: JSON.stringify(evidence),
        run: async (signal) => {
          await this.current(bound, false, signal);
          const result = await (
            await this.client(signal)
          ).callStructured(
            'get_window_state',
            { ...identity, ...args, tree_format: 'elements', include_screenshot: false, max_elements: 150 },
            signal,
          );
          const { elements } = z
            .object({
              elements: z.array(
                z.object({
                  element_token: element.optional(),
                  role: z.string(),
                  label: z.string().optional(),
                  value: z.unknown().optional(),
                }),
              ),
            })
            .parse(result);
          bound.refs.clear();
          for (const row of elements)
            if (row.element_token)
              bound.refs.set(row.element_token, [row.role, row.label].filter(Boolean).join(' '));
          return text({ elements, truncated: result.truncated === true });
        },
      };
    }
    if (action === 'screenshot') {
      noArgs.parse(input);
      return {
        access: 'observe',
        evidence: JSON.stringify(evidence),
        run: async (signal) => {
          const { screenRecording } = await this.current(bound, false, signal);
          if (!screenRecording)
            throw new Error('Screen Recording permission is required for a window screenshot.');
          const client = await this.client(signal);
          const result = await client.call(
            'get_window_state',
            { ...identity, include_accessibility_tree: false, max_image_dimension: 1400 },
            signal,
          );
          const image = result.find((block) => block.type === 'image');
          if (!image)
            throw new Error('Window capture unavailable. Check Screen Recording permission on the node.');
          bound.pixels = true;
          if (this.cwd) {
            const outDir = join(this.cwd, '.nano-screenshots');
            await mkdir(outDir, { recursive: true, mode: 0o700 });
            const ext = image.mimeType === 'image/jpeg' ? 'jpg' : image.mimeType === 'image/webp' ? 'webp' : 'png';
            const savedPath = join(outDir, `window-${randomUUID()}.${ext}`);
            await writeFile(savedPath, Buffer.from(image.data, 'base64'), { mode: 0o600 });
            return [
              {
                type: 'text',
                text: `Screenshot saved to ${savedPath} (pass in send_message local_images when delivering to chat).`,
              },
              image,
            ];
          }
          return [image];
        },
      };
    }
    let tool: string;
    let args: Record<string, unknown>;
    let control: string | undefined;
    let key: NavigationKey | undefined;
    let access: PreparedAction['access'] = 'review';
    switch (action) {
      case 'click':
      case 'type': {
        const values =
          action === 'click'
            ? z.strictObject({ element_token: element }).parse(input)
            : z.strictObject({ element_token: element, text: z.string().min(1).max(32_768) }).parse(input);
        control = bound.refs.get(values.element_token);
        if (!control) throw new Error('Observe the target window again for a fresh element token.');
        tool = action === 'click' ? 'click' : 'type_text';
        args = values;
        break;
      }
      case 'scroll':
        args = z
          .strictObject({
            direction: z.enum(['up', 'down', 'left', 'right']),
            amount: z.number().int().min(1).max(50).optional(),
          })
          .parse(input);
        tool = 'scroll';
        access = 'observe';
        break;
      case 'move':
        if (!bound.pixels) throw new Error('Take a fresh window screenshot before moving the cursor.');
        args = z.strictObject(point).parse(input);
        tool = 'move_cursor';
        access = 'observe';
        break;
      case 'key': {
        key = z.strictObject({ key: nav }).parse(input).key;
        if (
          this.navigation?.window === bound &&
          this.navigation.key === key &&
          this.navigation.until > Date.now()
        )
          access = 'observe';
        tool = 'press_key';
        args = key === 'shift+tab' ? { key: 'tab', modifiers: ['shift'] } : { key };
        break;
      }
      default:
        throw new Error('Unknown desktop action. Use describe for supported actions.');
    }
    const previousNavigation = this.navigation;
    return {
      access,
      evidence: JSON.stringify({ ...evidence, control, key }),
      run: async (signal) => {
        await this.current(bound, true, signal);
        if (control && bound.refs.get(String(args.element_token)) !== control)
          throw new Error('Control changed. Observe again before acting.');
        if (
          key &&
          access === 'observe' &&
          (this.navigation !== previousNavigation || previousNavigation!.until <= Date.now())
        ) {
          throw new Error('Navigation approval expired. Request the action again.');
        }
        const result = await (
          await this.client(signal)
        ).call(tool, { ...args, target, delivery_mode: 'background' }, signal);
        if (key && access === 'review')
          this.navigation = { window: bound, key, until: Date.now() + navigationTTL };
        if (!key) this.navigation = undefined;
        return result;
      },
    };
  }

  async close() {
    this.stopped = true;
    this.bound = undefined;
    this.navigation = undefined;
    await (await this.connection?.catch(() => undefined))?.close();
  }
}
