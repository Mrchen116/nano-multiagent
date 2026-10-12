import * as React from 'react';
import * as Jsx from 'react/jsx-runtime';
import * as Dom from 'react-dom';
import * as DomClient from 'react-dom/client';
import * as Cordis from '@deepseek-ai/cordis';
import * as Store from '@deepseek-ai/dsh-client-store';
import * as Slots from '@deepseek-ai/dsh-client-ui-slots';
import * as Primitives from '@deepseek-ai/dsh-client-ui-primitives';
import * as Dockkit from '@deepseek-ai/dsh-client-ui-dockkit';
import sessionRemote from '@deepseek-ai/dsh-api-session-controller/remote';
import commandsRemote from '@deepseek-ai/dsh-commands/remote';
import subagentRemote from '@deepseek-ai/dsh-subagent/remote';
import { createReadonlyTransport } from './transport';

const staticModules = {
  'react': React, 'react/jsx-runtime': Jsx, 'react-dom': Dom, 'react-dom/client': DomClient,
  '@deepseek-ai/cordis': Cordis, '@deepseek-ai/dsh-client-store': Store,
  '@deepseek-ai/dsh-client-ui-slots': Slots, '@deepseek-ai/dsh-client-ui-primitives': Primitives,
  '@deepseek-ai/dsh-client-ui-dockkit': Dockkit,
};
const readonly = () => { throw new Error('Read-only trajectory viewer'); };
// Native conversation stores UI preferences through localStorage. An opaque
// sandbox cannot access origin storage, so keep those preferences in this
// iframe's lifetime only without weakening its origin isolation.
const preferences = new Map();
Object.defineProperty(window, 'localStorage', { value: {
  get length() { return preferences.size; },
  key: index => [...preferences.keys()][index] ?? null,
  getItem: key => preferences.get(String(key)) ?? null,
  setItem: (key, value) => { preferences.set(String(key), String(value)); },
  removeItem: key => { preferences.delete(String(key)); },
  clear: () => preferences.clear(),
} });
const status = (state, message) => parent.postMessage({ type: 'viewer-status', state, message }, '*');
let dispose = () => {};
window.addEventListener('pagehide', () => dispose(), { once: true });

function loadScript(url) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = url;
    script.crossOrigin = 'anonymous';
    script.onload = resolve;
    script.onerror = () => reject(new Error('无法加载原生轨迹组件'));
    document.head.append(script);
  });
}

async function start(init, port) {
  if (init.version !== '0.2.1-alpha.1') throw new Error('轨迹组件版本不一致');
  const base = new URL(init.assetBase, location.href);
  const target = { mode: 'queue', pendingQueue: [], load(registration) { this.pendingQueue.push(registration); } };
  window.__ModuleLoader__ = target;
  const response = await fetch(new URL('manifest.json', base));
  if (!response.ok) throw new Error('无法读取轨迹组件清单');
  const manifest = await response.json();
  if (manifest.rev !== init.version) throw new Error('轨迹组件资源版本不一致');
  for (const entry of manifest.modules) entry.url = new URL(entry.url, base).href;
  await loadScript(new URL('plugins/@deepseek-ai/dsh-client-modules/client.js', base).href);
  const registration = target.pendingQueue.shift();
  const bootstrap = registration.factory(id => staticModules[id]);
  const modules = new bootstrap.ClientModuleSystem({
    manifest, staticModules, registrationTarget: target,
    bootstrapModule: { id: registration.id, exports: bootstrap },
    loadBundle: url => loadScript(url.replace('/plugins/??', '/plugins/').replace('&rev=', '?rev=')),
  });
  const load = id => modules.import(`@deepseek-ai/${id}/client`);
  const [renderer, conversation, session, trajectory, attachment, locale, theme, api, connection, gateway, typert] = await Promise.all([
    'dsh-client-ui-renderer', 'dsh-client-ui-conversation', 'dsh-client-ui-session',
    'dsh-client-ui-trajectory', 'dsh-client-ui-attachment', 'dsh-client-locale', 'dsh-client-ui-theme',
    'dsh-api-session-controller', 'dsh-client-connection', 'dsh-api-gateway', 'dsh-typert-registry',
  ].map(load));
  const ctx = new Cordis.Context();
  const transport = createReadonlyTransport(port, {
    onGenerationChanged: () => { status('interrupted', '连接已更新，正在恢复…'); ctx.connection.reconnect(); },
    onInterrupted: message => status('interrupted', message),
  });
  let reference;
  let unmount = () => {};
  dispose = () => {
    unmount();
    reference?.release();
    void ctx.fiber.dispose().finally(() => transport.dispose());
  };
  renderer.apply(ctx);
  ctx.provide('configForms', {
    get: namespace => Store.createSnapshotStore({ value: {
      preference: namespace.includes('locale') ? 'zh' : 'light', fontSize: 14,
    } }),
    set: readonly, patch: readonly,
    developerTools: { enabled: Store.createSnapshotStore(true) },
  });
  await locale.apply(ctx);
  theme.apply(ctx);
  connection.installConnection(ctx, { transport: { rpc: transport.rpc }, location: { hostname: 'readonly-viewer.invalid' } });
  typert.apply(ctx);
  gateway.apply(ctx);
  for (const contribution of [sessionRemote, commandsRemote, subagentRemote]) await ctx.remote.$mount(contribution);
  ctx.provide('fileUpload', { upload: readonly });
  api.apply(ctx);
  await ctx.sessions.refresh();
  reference = ctx.sessions.retain(init.sessionId, { source: 'mainView' });
  await reference.ready;
  if (Number.isInteger(init.position?.firstSeq)) await reference.binding.session.loadThrough(init.position.firstSeq);
  ctx.effect(() => reference.binding.session.subscribe(() => {
    const snapshot = reference.binding.session.getSnapshot();
    if (snapshot.openState === 'open') status('ready');
    else if (snapshot.openState === 'error') status('interrupted', snapshot.openError?.message ?? '轨迹读取中断');
  }), 'nano-trajectory.status');
  session.apply(ctx);
  ctx.provide('uiWorkspace', { openSession: readonly, openWorkspace: readonly });
  conversation.apply(ctx, { maxConcurrentFileUploads: 2 });
  ctx.slots.register({ name: 'root', id: 'nano-trajectory', children: {
    'conversation.view': { kind: 'list', scope: 'session' },
  } }, function Viewer({ renderSlot, SessionProvider }) {
    return <SessionProvider session={reference}>
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', '--dsh-composer-height': '0px' }}>
        {renderSlot('conversation.view', { inspectCall: undefined, viewRequest: null,
          openView() {}, completeViewRequest() {} }, { only: 'trajectory' })}
      </div>
    </SessionProvider>;
  });
  trajectory.apply(ctx);
  attachment.apply(ctx);
  unmount = ctx.uiRenderer.mount(document.getElementById('root'));
  // Keep only a numeric reading bookmark in the host; history is always read afresh.
  let restoring = Number.isFinite(init.position?.top);
  const publishPosition = event => {
    if (restoring) return;
    const pane = document.querySelector('[data-trajectory-scroll]');
    if (!pane) return;
    parent.postMessage({ type: 'viewer-position', top: pane.scrollTop,
      rowKey: pane.querySelector('[data-selected]')?.getAttribute('data-trajectory-row-key'),
      detailTab: document.querySelector('[role=tab][aria-selected=true]')?.id,
      firstSeq: reference.binding.eventSource.getSnapshot().entries[0]?.event.seq }, '*');
  };
  document.addEventListener('scroll', publishPosition, true);
  const afterSelection = () => requestAnimationFrame(publishPosition);
  document.addEventListener('click', afterSelection);
  const bookmark = new MutationObserver(() => {
    const pane = document.querySelector('[data-trajectory-scroll]');
    if (!pane?.querySelector('[data-scroll-ready]')) return;
    bookmark.disconnect();
    if (restoring) requestAnimationFrame(() => {
      const row = [...pane.querySelectorAll('[data-trajectory-row-key]')].find(item => item.getAttribute('data-trajectory-row-key') === init.position.rowKey);
      row?.click();
      requestAnimationFrame(() => {
        if (init.position.detailTab) document.getElementById(init.position.detailTab)?.click();
        pane.scrollTop = init.position.top;
      });
      pane.scrollTop = init.position.top;
      restoring = false;
      pane.dispatchEvent(new Event('scroll'));
    });
  });
  bookmark.observe(document.getElementById('root'), { subtree: true, childList: true, attributes: true, attributeFilter: ['data-scroll-ready'] });
  ctx.effect(() => () => { bookmark.disconnect(); document.removeEventListener('scroll', publishPosition, true); document.removeEventListener('click', afterSelection); });
  status('ready');
}

window.addEventListener('message', function initialize(event) {
  if (event.source !== parent || event.data?.type !== 'nano-trajectory-init' || !event.ports[0]) return;
  window.removeEventListener('message', initialize);
  const port = event.ports[0];
  start(event.data, port).catch(error => {
    dispose();
    port.close();
    document.getElementById('root').textContent = `执行轨迹加载失败：${error.message}`;
    status('error', error.message);
  });
});
parent.postMessage({ type: 'nano-trajectory-ready' }, '*');
