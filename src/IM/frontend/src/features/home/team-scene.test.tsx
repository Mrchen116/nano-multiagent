import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { setLanguage } from '../../i18n';
import { TeamScene } from './team-scene';

beforeEach(() => { vi.useFakeTimers(); setLanguage('en'); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
function advanceTime(ms: number) { act(() => vi.advanceTimersByTime(ms)); }

it('stops at the human decision and never sends the illustrated work to a server', () => {
  const fetch = vi.spyOn(globalThis, 'fetch');
  render(<TeamScene />);
  advanceTime(2600);
  expect(screen.getByText('Milo has it. Bringing the team in.')).toBeInTheDocument();
  advanceTime(1800);
  expect(screen.getByText('Milo prepares the brief')).toBeInTheDocument();
  advanceTime(3800);
  advanceTime(60000);
  expect(screen.getByRole('button', { name: 'Let’s go with that' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Let’s go with that' }));
  advanceTime(2600);
  expect(screen.getByText('One shared plan. A whole team ready.')).toBeInTheDocument();
  advanceTime(60000);
  expect(screen.getByText('One shared plan. A whole team ready.')).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

it('pauses progression and can restart the demonstration', () => {
  render(<TeamScene />);
  fireEvent.click(screen.getByRole('button', { name: 'Hand it to Milo' }));
  fireEvent.click(screen.getByRole('button', { name: 'Pause demo' }));
  advanceTime(20000);
  expect(screen.getByText('Milo has it. Bringing the team in.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Resume demo' }));
  advanceTime(1800);
  expect(screen.getByText('Milo prepares the brief')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Replay' }));
  expect(screen.getByRole('button', { name: 'Hand it to Milo' })).toBeInTheDocument();
});

it('lets reduced-motion visitors complete the story without automatic progression', () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  render(<TeamScene />);
  advanceTime(60000);
  fireEvent.click(screen.getByRole('button', { name: 'Hand it to Milo' }));
  advanceTime(60000);
  expect(screen.getByText('Milo has it. Bringing the team in.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  fireEvent.click(screen.getByRole('button', { name: 'Let’s go with that' }));
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByText('One shared plan. A whole team ready.')).toBeInTheDocument();
});
