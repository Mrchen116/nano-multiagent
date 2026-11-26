import { randomUUID } from 'node:crypto';
import { readFile, realpath, rm, stat, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import type { ComputerBackend, ComputerContent, PreparedAction } from './backend.js';
import { openMcp } from './mcp.js';
import {
  chromeExecutable,
  dailyPrerequisites,
  pairing,
  recordCheck,
  requiresRepair,
  seatDirectory,
  type Pairing,
} from './browser-connection.js';

const cli = join(dirname(createRequire(import.meta.url).resolve('@playwright/mcp/package.json')), 'cli.js');
type Client = Awaited<ReturnType<typeof openMcp>>;
type Tab = { id: string; index: number; url: string; title: string; revision: number };
type Mode = 'daily' | 'isolated';
const operations = {
  status: [],
  describe: [],
  open: ['url', 'mode'],
  navigate: ['url'],
  new_tab: ['url'],
  tabs: [],
  select_tab: ['tab'],
  close_tab: [],
  snapshot: [],
  screenshot: [],
  console: [],
  network: [],
  click: ['ref'],
  type: ['ref', 'text'],
  upload: ['path'],
  copy: ['text'],
  paste: ['ref'],
} as const;
type Action = keyof typeof operations;
const reads = new Set<Action>([
  'status',
  'describe',
  'tabs',
  'select_tab',
  'snapshot',
  'screenshot',
  'console',
  'network',
  'copy',
]);
const text = (value: string): ComputerContent[] => [{ type: 'text', text: value }];
function body(content: ComputerContent[]) {
  return content
    .filter((x) => x.type === 'text')
    .map((x) => x.text)
    .join('\n');
}
function field(input: Record<string, unknown>, key: string) {
  const value = input[key];
  if (typeof value !== 'string' || !value.length) throw new Error('Supply ' + key + '.');
  return value;
}
function webUrl(raw: string) {
  const url = new URL(raw);
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password)
    throw new Error('A web URL without embedded credentials is required.');
  return url;
}
function publicUrl(raw: string) {
  const url = new URL(raw);
  return url.origin + url.pathname;
}
function label(t: Tab) {
  return publicUrl(t.url) + ' ' + t.title.slice(0, 140);
}
function sameDocument(a: Tab, b: Tab) {
  return a.id === b.id && a.url === b.url && a.revision === b.revision;
}

// Playwright loads this fixed hook for client-owned pages. Keep document identities
// outside page JavaScript, so page text cannot turn a stale ref into a live one.
const initCode = `const {randomUUID}=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const byPage=new WeakMap();
const file=path.join(__dirname,'tabs.json');
exports.default=async ({page})=>{
  if(byPage.has(page)) return;
  const state={id:randomUUID(),revision:0};
  byPage.set(page,state);
  const publish=()=>{
    const tabs=page.context().pages().map(p=>{
      const known=byPage.get(p);
      return known ? {...known,url:p.url()} : null;
    });
    fs.writeFileSync(file+'.tmp',JSON.stringify(tabs),{mode:0o600});
    fs.renameSync(file+'.tmp',file);
  };
  page.on('framenavigated',frame=>{if(frame===page.mainFrame()){++state.revision;publish();}});
  page.on('close',publish);
  publish();
  const cdp=await page.context().newCDPSession(page);
  await cdp.send('Emulation.setFocusEmulationEnabled',{enabled:true});
};`;

/** One paired extension client or isolated browser for one host-owned task. */
export class BrowserBackend implements ComputerBackend {
  private client?: Client;
  private dir?: string;
  private mode?: Mode;
  private connection?: Pairing;
  private closed = false;
  private readonly origins = new Set<string>();
  private readonly tabs = new Set<string>();
  private readonly pendingTabs = new Set<string>();
  private seen?: { tab: Tab; snapshot: string; refs: Map<string, string> };
  private clipboard?: string;

  constructor(private readonly cwd: string) {}

  private async start(mode: Mode, signal: AbortSignal, saved?: Pairing) {
    const exe = saved ? await dailyPrerequisites(saved.profile) : await chromeExecutable();
    signal.throwIfAborted();
    this.dir = await seatDirectory();
    const init = join(this.dir, 'page.cjs');
    await writeFile(init, initCode, { mode: 0o600 });
    const argv = [
      cli,
      '--executable-path',
      exe,
      '--no-webmcp',
      '--codegen',
      'none',
      '--output-dir',
      this.dir,
      '--snapshot-mode',
      'none',
      '--init-page',
      init,
    ];
    if (saved)
      argv.push(
        '--extension',
        '--background',
        '--profile-dir-name',
        saved.profile,
        '--session-name',
        'Nano ' + randomUUID().slice(0, 8),
      );
    else argv.push('--headless', '--user-data-dir', join(this.dir, 'profile'));
    const client = await openMcp(
      process.execPath,
      argv,
      saved ? { PLAYWRIGHT_MCP_EXTENSION_TOKEN: saved.token } : {},
      this.cwd,
    );
    if (this.closed || signal.aborted) {
      await client.close();
      throw new Error('Browser task ended.');
    }
    this.client = client;
    this.mode = mode;
    this.connection = saved;
  }

  private async inventory(signal: AbortSignal): Promise<{ tabs: Tab[]; current: Tab }> {
    const parts = await this.client!.call('browser_tabs', { action: 'list', _meta: { json: true } }, signal);
    const rows: string[] = JSON.parse(body(parts)).result.split('\n');
    const data: (Pick<Tab, 'id' | 'revision' | 'url'> | null)[] = JSON.parse(
      await readFile(join(this.dir!, 'tabs.json'), 'utf8'),
    );
    if (rows.length !== data.length) throw new Error('The browser tab list changed. Try the observation again.');
    let active: Tab | undefined;
    const tabs = rows.map((line, index) => {
      const doc = data[index];
      const prefix = '- ' + index + ': ';
      const current = line.startsWith(prefix + '(current) ');
      const start = prefix + (current ? '(current) ' : '') + '[';
      const end = doc && '](' + doc.url + ')';
      if (!doc || !end || !line.startsWith(start) || !line.endsWith(end))
        throw new Error('Browser tab metadata is stale. Refresh the browser task.');
      const tab = { ...doc, index, title: line.slice(start.length, -end.length) };
      if (current) active = tab;
      return tab;
    });
    if (!active) throw new Error('No verified browser tab for this task. Reopen the browser task.');
    return { tabs, current: active };
  }

  private async current(signal: AbortSignal) {
    if (this.closed || !this.client) throw new Error('Open a browser seat first.');
    if (this.connection && (await pairing())?.id !== this.connection.id) {
      await this.close();
      throw new Error('Daily Chrome pairing changed. Open a new browser task.');
    }
    return (await this.inventory(signal)).current;
  }
  private allowed(t: Tab) {
    return this.tabs.has(t.id) && this.origins.has(new URL(t.url).origin);
  }
  private async snapshot(signal: AbortSignal) {
    const parts = await this.client!.call('browser_snapshot', { _meta: { json: true } }, signal);
    type Node = {
      role?: string;
      name?: string;
      ref?: string;
      text?: string;
      disabled?: boolean;
      checked?: boolean;
      children?: Node[];
    };
    const nodes = JSON.parse(body(parts)).snapshot as Node[];
    if (!Array.isArray(nodes)) throw new Error('A fresh page snapshot is unavailable.');
    const refs = new Map<string, string>();
    const lines: string[] = [];
    let length = 0;
    const visit = (node: Node, depth: number) => {
      if (length >= 48000) return;
      const ref = node.ref && /^e\d+$/.test(node.ref) ? node.ref : undefined;
      const label = [
        node.role,
        node.name && JSON.stringify(node.name.slice(0, 512)),
        ref && '[ref=' + ref + ']',
        node.disabled && 'disabled',
        node.checked !== undefined && 'checked=' + node.checked,
      ]
        .filter(Boolean)
        .join(' ');
      const line =
        '  '.repeat(Math.min(depth, 12)) + label + (node.text ? ' ' + JSON.stringify(node.text.slice(0, 3000)) : '');
      length += line.length + 1;
      lines.push(line);
      if (ref) refs.set(ref, label);
      if (node.role !== 'iframe') for (const child of node.children ?? []) visit(child, depth + 1);
    };
    for (const node of nodes) visit(node, 0);
    if (length >= 48000) lines.push('[snapshot truncated]');
    return { snapshot: lines.join('\n'), refs };
  }
  private async uploadFile(raw: string) {
    const root = await realpath(this.cwd);
    const target = await realpath(resolve(root, raw));
    const privateFile = process.env.NANO_BROWSER_PAIRING_FILE;
    if (privateFile) {
      const privateDir = await realpath(dirname(privateFile)).catch(() => dirname(privateFile));
      if (target === privateDir || target.startsWith(privateDir + sep))
        throw new Error('Node-private browser data cannot be uploaded.');
    }
    const rel = relative(root, target);
    if (!rel || rel === '..' || rel.startsWith('..' + sep) || isAbsolute(rel) || !(await stat(target)).isFile())
      throw new Error('Choose a file within the task workspace.');
    return target;
  }

  async prepare(actionName: string, input: Record<string, unknown>, signal: AbortSignal): Promise<PreparedAction> {
    if (this.closed) throw new Error('Browser task ended.');
    if (!Object.hasOwn(operations, actionName)) throw new Error('Unknown browser action. Use describe.');
    const action = actionName as Action;
    if (Object.keys(input).some((k) => !(operations[action] as readonly string[]).includes(k)))
      throw new Error('Unsupported browser parameter. Use describe.');
    if (action === 'describe' || action === 'status')
      return {
        access: 'observe',
        evidence: action,
        run: async () => {
          if (action === 'describe')
            return text(
              'First open with url and optional mode (daily or isolated). Use snapshot before ref-based actions. tab is the ID returned by tabs. copy takes text seen on this page; paste uses only this task’s clipboard. Actions and fields: ' +
                JSON.stringify(operations),
            );
          const saved = await pairing();
          let daily = 'not_paired: Install the Playwright Extension and run browser pair on the node.';
          if (!['darwin', 'win32'].includes(process.platform)) daily = 'unsupported: choose isolated mode.';
          else if (saved) {
            try {
              await dailyPrerequisites(saved.profile);
              daily = (await requiresRepair(saved.id))
                ? 'reconnect: run browser pair on the node.'
                : this.connection?.id === saved.id
                  ? 'connected'
                  : 'paired; verified on open';
            } catch (error) {
              daily = String(error);
            }
          }
          return text(JSON.stringify({ daily, seat: this.mode ?? 'unopened' }));
        },
      };
    const url = ['open', 'navigate', 'new_tab'].includes(action) ? webUrl(field(input, 'url')) : undefined;
    if (action === 'open') {
      const mode = input.mode ?? 'daily';
      if (mode !== 'daily' && mode !== 'isolated') throw new Error('Choose daily or isolated.');
      if (this.client) throw new Error('This task already has a browser seat.');
      const saved = mode === 'daily' ? await pairing() : undefined;
      if (mode === 'daily' && !saved)
        throw new Error(
          'Daily Chrome is not paired. Install the Playwright Extension and run browser pair on the node.',
        );
      if (saved) {
        if (await requiresRepair(saved.id))
          throw new Error('Daily Chrome needs a new pairing. Run browser pair on the node.');
        await dailyPrerequisites(saved.profile);
      }
      return {
        access: 'review',
        evidence: `Open ${mode} browser at ${publicUrl(url!.href)}`,
        run: async (sig) => {
          if (this.client || this.closed) throw new Error('Browser seat changed.');
          try {
            if (saved && (await pairing())?.id !== saved.id)
              throw new Error('Browser pairing changed. Request the action again.');
            await this.start(mode, sig, saved);
            const initial = await this.current(sig);
            if (initial.url !== 'about:blank' && initial.url !== 'chrome://newtab/')
              throw new Error('The new browser seat did not start on a blank tab.');
            this.tabs.add(initial.id);
            if (this.connection) await recordCheck(this.connection.id, 'verified');
            await this.client!.call('browser_navigate', { url: url!.href }, sig);
            this.origins.add(url!.origin);
            return text('Browser seat opened. Use snapshot to observe the page.');
          } catch (error) {
            if (this.connection && !this.tabs.size) await recordCheck(this.connection.id, 'reconnect');
            await this.release();
            if (mode === 'daily')
              throw new Error(
                'Daily Chrome could not be opened. Check browser status, start Chrome and verify the Playwright Extension pairing.',
              );
            throw error;
          }
        },
      };
    }
    const tab = await this.current(signal);
    if (
      !['tabs', 'select_tab'].includes(action) &&
      (!this.tabs.has(tab.id) || (!this.allowed(tab) && action !== 'navigate'))
    )
      throw new Error('This page is outside the approved task site. Navigate to an explicitly authorized URL.');
    let target: string | undefined;
    let value: string | undefined;
    let file: string | undefined;
    if (['click', 'type', 'paste'].includes(action)) {
      const ref = field(input, 'ref');
      target = this.seen && sameDocument(this.seen.tab, tab) ? this.seen.refs.get(ref) : undefined;
      if (!target) throw new Error('Unknown or expired ref. Request a new snapshot.');
      if (action === 'type') value = field(input, 'text');
      if (action === 'paste') {
        if (this.clipboard === undefined) throw new Error('This browser task clipboard is empty.');
        value = this.clipboard;
      }
    }
    if (action === 'upload') file = await this.uploadFile(field(input, 'path'));
    const evidence = [action, label(tab), target, url && publicUrl(url.href), file].filter(Boolean).join(' · ');
    return {
      access: reads.has(action) ? 'observe' : 'review',
      evidence,
      run: async (sig) => {
        const live = await this.current(sig);
        if (!sameDocument(tab, live))
          throw new Error('Browser target changed. Observe the page and request the action again.');
        const client = this.client!;
        if (action === 'tabs' || action === 'select_tab') {
          const list = (await this.inventory(sig)).tabs.filter((t) => this.allowed(t));
          if (action === 'tabs')
            return text(JSON.stringify(list.map((t) => ({ tab: t.id, current: t.id === live.id, label: label(t) }))));
          const chosen = list.find((t) => t.id === field(input, 'tab'));
          if (!chosen) throw new Error('Unknown task tab.');
          await client.call('browser_tabs', { action: 'select', index: chosen.index }, sig);
          if (!sameDocument(chosen, await this.current(sig))) throw new Error('Selected tab changed. List tabs again.');
          this.seen = undefined;
          return text('Tab selected.');
        }
        if (action === 'snapshot') {
          const observed = await this.snapshot(sig);
          if (!sameDocument(live, await this.current(sig)))
            throw new Error('Page changed while reading. Retry snapshot.');
          this.seen = { tab: live, ...observed };
          return text(label(live) + '\n' + observed.snapshot);
        }
        if (action === 'copy') {
          const value = field(input, 'text');
          if (!this.seen || !sameDocument(this.seen.tab, live) || !this.seen.snapshot.includes(value))
            throw new Error('Copy text from the current page snapshot.');
          this.clipboard = value;
          return text('Copied to this task’s browser clipboard.');
        }
        if (action === 'screenshot' || action === 'console' || action === 'network') {
          const name = {
            screenshot: 'browser_take_screenshot',
            console: 'browser_console_messages',
            network: 'browser_network_requests',
          }[action];
          const parts = await client.call(name, action === 'screenshot' ? { type: 'jpeg' } : {}, sig);
          if (!sameDocument(live, await this.current(sig))) throw new Error('Page changed while reading. Retry.');
          if (action === 'screenshot') return parts.filter((p) => p.type === 'image');
          if (action === 'console')
            return text(
              body(parts).match(/Total messages: \d+ \(Errors: \d+, Warnings: \d+\)/)?.[0] ??
                'Console summary unavailable.',
            );
          const requests = [];
          for (const m of body(parts).matchAll(
            /^\d+\. \[([A-Z]+)\] (https?:\/\/\S+?)(?: => \[(\d{3}|FAILED)\].*)?$/gm,
          )) {
            try {
              requests.push([m[1], new URL(m[2]!).origin, m[3] ?? 'pending']);
            } catch {
              /* omit unparseable request */
            }
          }
          return text(JSON.stringify(requests.slice(-100)));
        }
        if (target && (!this.seen || (await this.snapshot(sig)).refs.get(field(input, 'ref')) !== target))
          throw new Error('Target control changed. Request a fresh snapshot.');
        this.seen = undefined;
        if (action === 'navigate' || action === 'new_tab') {
          if (action === 'navigate') await client.call('browser_navigate', { url: url!.href }, sig);
          else {
            const marker = 'about:blank#nano-' + randomUUID();
            this.pendingTabs.add(marker);
            await client.call('browser_tabs', { action: 'new', url: marker }, sig);
            const created = await this.current(sig);
            if (created.url !== marker) throw new Error('New tab changed before binding.');
            this.tabs.add(created.id);
            this.pendingTabs.delete(marker);
            await client.call('browser_navigate', { url: url!.href }, sig);
          }
          this.origins.add(url!.origin);
        } else if (action === 'close_tab') {
          await client.call('browser_tabs', { action: 'close', index: live.index }, sig);
          this.tabs.delete(live.id);
          if (!this.tabs.size) await this.release();
        } else if (action === 'upload') {
          if ((await this.uploadFile(field(input, 'path'))) !== file) throw new Error('Upload target changed.');
          await client.call('browser_file_upload', { paths: [file] }, sig);
        } else if (action === 'click') await client.call('browser_click', { target: input.ref }, sig);
        else await client.call('browser_type', { target: input.ref, text: value }, sig);
        return text('Action completed. Use snapshot to verify the result.');
      },
    };
  }

  async close() {
    this.closed = true;
    await this.release();
  }

  private async release() {
    try {
      if (this.mode === 'daily' && this.client && (this.tabs.size || this.pendingTabs.size)) {
        // Chrome keeps extension tab groups on disconnect. Leave any tabs added by the user alone.
        const signal = AbortSignal.timeout(5000);
        try {
          if (this.pendingTabs.size) {
            for (const tab of (await this.inventory(signal)).tabs)
              if (this.pendingTabs.has(tab.url)) this.tabs.add(tab.id);
          }
          for (const id of this.tabs) {
            const live = (await this.inventory(signal)).tabs.find((t) => t.id === id);
            if (live) await this.client.call('browser_tabs', { action: 'close', index: live.index }, signal);
          }
        } finally {
          await this.client.close();
        }
      } else await this.client?.close();
    } finally {
      if (this.dir) await rm(this.dir, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
      this.client = undefined;
      this.mode = undefined;
      this.dir = undefined;
      this.connection = undefined;
      this.clipboard = undefined;
      this.seen = undefined;
      this.tabs.clear();
      this.pendingTabs.clear();
      this.origins.clear();
    }
  }
}
