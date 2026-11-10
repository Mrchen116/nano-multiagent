import { expect, it } from 'vitest';
import { CHROME_NOISE_SIZES, classifyNewWindows } from '../src/browser/events.js';
import type { DriverWindow } from '../src/browser/windows.js';

const window = (window_id: string, title: string, width: number, height: number): DriverWindow => ({ window_id, title, width, height });

it('classifies an exact bind with an http(s) tab as a real window event', () => {
  const result = classifyNewWindows(['10'], [window('10', 'main', 1200, 800), window('20', 'Popup', 520, 426)], id => id === '20'
    ? { ok: true, binding_quality: 'exact', target_id: 'bt-20', tabs: [{ active: true, url: 'http://127.0.0.1/popup.html', title: 'Popup' }] }
    : { ok: true, binding_quality: 'exact', target_id: 'bt-10' });
  expect(result.events).toEqual([{ kind: 'window', window_id: '20', title: 'Popup', width: 520, height: 426, url: 'http://127.0.0.1/popup.html' }]);
  expect(result.ignored).toEqual([]);
  expect(result.unclassified).toEqual([]);
});

it('classifies the fixed-size, untitled, no-target Chrome overlays as noise', () => {
  for (const size of CHROME_NOISE_SIZES) {
    const title = size.width === 284 ? '翻译此页？' : '';
    const result = classifyNewWindows([], [window('30', title, size.width, size.height)], () => ({ ok: false }));
    expect(result.events).toEqual([]);
    expect(result.unclassified).toEqual([]);
    expect(result.ignored).toEqual([{ width: size.width, height: size.height, title }]);
  }
});

it('separates the observed Chrome password warning from real or unclassified windows', () => {
  const alert = window('30', '更改您的密码', 448, 299);
  const refused = classifyNewWindows([], [alert], () => ({ ok: false }));
  expect(refused.ignored).toEqual([{ width: 448, height: 299, title: '更改您的密码' }]);
  const exact = classifyNewWindows([], [alert], () => ({
    ok: true, binding_quality: 'exact', target_id: 'bt-30', tabs: [{ active: true, url: 'https://fixture.example', title: 'Fixture' }],
  }));
  expect(exact.events).toHaveLength(1);
  expect(classifyNewWindows([], [{ ...alert, height: 300 }], () => ({ ok: false })).unclassified).toHaveLength(1);
});

it('does not treat an incomplete noise signature as noise', () => {
  const cases = [
    { window: window('31', '翻译此页？', 284, 87), probe: { ok: true, binding_quality: 'exact', target_id: 'bt-31', tabs: [] } },
    { window: window('32', '', 900, 700), probe: { ok: false } },
    { window: window('33', 'Popup', 284, 87), probe: { ok: false } },
  ];
  for (const scenario of cases) {
    const result = classifyNewWindows([], [scenario.window], () => scenario.probe);
    expect(result.ignored).toEqual([]);
    expect(result.unclassified).toEqual([scenario.window]);
  }
});

it('classifies exact bindings whose tabs are not http(s) as unclassified', () => {
  const result = classifyNewWindows([], [window('40', '', 900, 700)], () => ({
    ok: true, binding_quality: 'exact', target_id: 'bt-40', tabs: [{ active: true, url: 'about:blank', title: '' }],
  }));
  expect(result.events).toEqual([]);
  expect(result.ignored).toEqual([]);
  expect(result.unclassified).toHaveLength(1);
});

it('reports real events and noise together without counting the main window', () => {
  const result = classifyNewWindows(['10'], [
    window('10', 'main', 1200, 800),
    window('20', 'Popup', 520, 426),
    window('21', '翻译此页？', 284, 87),
  ], id => id === '20'
    ? { ok: true, binding_quality: 'exact', target_id: 'bt-20', tabs: [{ active: true, url: 'https://popup', title: 'Popup' }] }
    : { ok: false });
  expect(result.events.map(event => event.window_id)).toEqual(['20']);
  expect(result.ignored).toHaveLength(1);
  expect(result.unclassified).toHaveLength(0);
});
