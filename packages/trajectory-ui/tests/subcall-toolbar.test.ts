// @vitest-environment jsdom
import * as React from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';

vi.mock('@deepseek-ai/dsh-client-ui-primitives', () => ({
  IconSearchOutlineRegular: () => React.createElement('span', { 'data-icon': 'search' }),
}));

import { TrajectoryToolbar } from '../src/client/TrajectoryToolbar';
import { zh } from '../src/client/locales';

const disposals: (() => void)[] = [];
afterEach(() => {
  for (const dispose of disposals.splice(0)) dispose();
  vi.unstubAllGlobals();
});

it('renders the fourth nested subcall fold button in TrajectoryToolbar and toggles subcall state', async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  const container = document.createElement('div');
  document.body.append(container);
  const root = createRoot(container);
  disposals.push(() => {
    React.act(() => root.unmount());
    container.remove();
  });

  const onToggleAllSubCalls = vi.fn();
  const t = ((key: string) => (zh as Record<string, string>)[key] ?? key) as never;

  await React.act(async () => {
    root.render(
      React.createElement(TrajectoryToolbar, {
        actualDuration: false,
        onActualDurationChange: vi.fn(),
        actualTime: false,
        onActualTimeChange: vi.fn(),
        allTurnsCollapsed: false,
        onToggleAllTurns: vi.fn(),
        allAssistantsCollapsed: false,
        onToggleAllAssistants: vi.fn(),
        allSubCallsCollapsed: false,
        onToggleAllSubCalls,
        searchQuery: '',
        onSearchQueryChange: vi.fn(),
        t,
      }),
    );
  });

  const buttons = [...container.querySelectorAll('button:not([hidden])')];
  expect(buttons).toHaveLength(4);
  const subCallBtn = buttons[3]!;
  expect(subCallBtn.getAttribute('aria-pressed')).toBe('false');
  expect(subCallBtn.textContent).toContain(zh['toolbar.subCalls']);

  await React.act(async () => {
    subCallBtn.click();
  });
  expect(onToggleAllSubCalls).toHaveBeenCalledTimes(1);
});
