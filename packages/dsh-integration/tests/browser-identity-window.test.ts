import { expect, it } from 'vitest';
import { ReadRegistry, normalizeBoundWindow, selectTab, type DriverTab } from '../src/browser/identity.js';
import { WindowRegistry, choosePrimaryWindow, normalizeWindows } from '../src/browser/windows.js';
import { classifyNewWindows } from '../src/browser/events.js';

const tabs = (rows: { url: string; title: string; active?: boolean; id?: string }[]): DriverTab[] => rows.map((row, index) => ({
  active: row.active ?? false,
  tab_id: row.id ?? `tab-${index}`,
  url: row.url,
  title: row.title,
}));

it('selects the active tab by default and never by array position', () => {
  const bound = tabs([{ url: 'https://a', title: 'A' }, { url: 'https://b', title: 'B', active: true }]);
  expect(selectTab(bound).url).toBe('https://b');
});

it('matches url, title and active together and rejects ambiguity', () => {
  const bound = tabs([
    { url: 'https://a', title: 'Same', active: true },
    { url: 'https://a', title: 'Same', active: false },
  ]);
  expect(selectTab(bound, { url: 'https://a', title: 'Same', active: true }).active).toBe(true);
  try { selectTab(bound, { url: 'https://a' }); throw new Error('expected ambiguity'); }
  catch (error) { expect(error).toMatchObject({ code: 'browser_tab_ambiguous' }); }
  try { selectTab(bound, { url: 'https://missing' }); throw new Error('expected missing'); }
  catch (error) { expect(error).toMatchObject({ code: 'browser_driver_refused', details: { code: 'browser_tab_not_found' } }); }
});

it('recasts target and tab ids on every bind and keeps ids out of the identity error', () => {
  const first = normalizeBoundWindow({ binding_quality: 'exact', target_id: 'bt-1', tabs: [{ active: true, tab_id: 'tab-1', url: 'https://a', title: 'A' }] });
  const second = normalizeBoundWindow({ binding_quality: 'exact', target_id: 'bt-2', tabs: [{ active: true, tab_id: 'tab-2', url: 'https://a', title: 'A' }] });
  expect(first.target_id).not.toBe(second.target_id);
  expect(first.tabs[0]!.tab_id).not.toBe(second.tabs[0]!.tab_id);
  try { selectTab(tabs([{ url: 'x', title: 'x' }, { url: 'x', title: 'x' }]), { url: 'x' }); }
  catch (error) { expect(JSON.stringify((error as { details?: unknown }).details)).not.toContain('tab-'); }
});

it('treats only the latest read_id as current and detects URL or tab drift', () => {
  const registry = new ReadRegistry();
  const tab = tabs([{ url: 'https://a', title: 'A', active: true }])[0]!;
  const r1 = registry.mint(tab, 'first');
  const r2 = registry.mint(tab, 'second');
  expect(r2.readId).not.toBe(r1.readId);
  expect(() => registry.require(r1.readId)).toThrowError(/已过期/);
  expect(registry.validate(r2.readId, tabs([{ url: 'https://a', title: 'A' }]))).toBe(r2);
  expect(() => registry.validate(r2.readId, tabs([{ url: 'https://changed', title: 'A' }]))).toThrowError(/已变化/);
  expect(() => registry.validate(r2.readId, tabs([{ url: 'https://a', title: 'A' }]), { url: 'https://other' })).toThrowError(/另一个标签/);
  registry.clear();
  expect(() => registry.require(r2.readId)).toThrowError(/已过期/);
});

it('normalizes list_windows and registers exactly one exact-bind main window, including about:blank', () => {
  const listed = normalizeWindows({ windows: [
    { window_id: 10, title: 'about:blank', width: 1200, height: 800 },
    { window_id: '11', title: 'popup', bounds: { width: 520, height: 426 } },
  ] });
  expect(listed).toEqual([
    { window_id: '10', title: 'about:blank', width: 1200, height: 800 },
    { window_id: '11', title: 'popup', width: 520, height: 426 },
  ]);
  const registration = choosePrimaryWindow('42', listed, id => id === '10'
    ? { ok: true, binding_quality: 'exact', target_id: 'bt-10' }
    : { ok: false });
  expect(registration).toEqual({ pid: '42', windowId: '10', targetId: 'bt-10' });
});

it('reports zero candidates as session lost and multiple exact candidates as ambiguous', () => {
  const windows = normalizeWindows({ windows: [{ window_id: 1, title: 'a' }, { window_id: 2, title: 'b' }] });
  expect(() => choosePrimaryWindow('42', windows, () => ({ ok: false }))).toThrowError(expect.objectContaining({ code: 'browser_session_lost' }));
  try {
    choosePrimaryWindow('42', windows, () => ({ ok: true, binding_quality: 'exact', target_id: 'bt' }));
    throw new Error('expected ambiguity');
  } catch (error) {
    expect(error).toMatchObject({ code: 'browser_window_ambiguous' });
    expect((error as { details: { candidates: unknown[] } }).details.candidates).toHaveLength(2);
  }
});

it('keeps the registered main window when a real popup appears and rejects foreign window ids', () => {
  const registry = new WindowRegistry();
  registry.adopt('42', '10');
  const windows = normalizeWindows({ windows: [
    { window_id: 10, title: 'main', width: 1200, height: 800 },
    { window_id: 20, title: 'Popup', width: 520, height: 426 },
  ] });
  const classification = classifyNewWindows(['10'], windows, id => id === '20'
    ? { ok: true, binding_quality: 'exact', target_id: 'bt-20', tabs: [{ active: true, url: 'https://popup', title: 'Popup' }] }
    : { ok: true, binding_quality: 'exact', target_id: 'bt-10' });
  expect(classification.events).toHaveLength(1);
  expect(registry.get()).toEqual({ pid: '42', windowId: '10' });
  expect(() => registry.assertRequested('20')).toThrowError(expect.objectContaining({ code: 'browser_window_not_registered' }));
  expect(() => registry.assertRequested('10')).not.toThrow();
});
