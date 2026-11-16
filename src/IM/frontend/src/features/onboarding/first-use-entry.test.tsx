import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { appRoutes } from '../../app/router';
import { setLanguage } from '../../i18n';
import { renderRouter, TEST_AUTH_USER } from '../../test/render-router';

vi.mock('../../realtime/user-stream', async importOriginal => ({
  ...await importOriginal<typeof import('../../realtime/user-stream')>(),
  subscribeUserStream: vi.fn(() => () => undefined),
}));

beforeEach(() => {
  localStorage.clear(); setLanguage('en');
  vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
    const url = String(input);
    if (url.endsWith('/im/v1/personal-agent')) return Response.json({binding:null,policy:null});
    if (url.endsWith('/im/v1/onboarding')) return Response.json({nodes:[],agents:[],install:{available:false,origin:'https://example.test',command:'install',script_url:'https://example.test/install.sh'}});
    if (url.includes('/im/v1/contacts')) return Response.json({items:[],next_cursor:null});
    if (url.endsWith('/im/v1/conversations')) return Response.json({items:[]});
    if (url.endsWith('/im/v1/nodes') || url.endsWith('/im/v1/agents')) return Response.json([]);
    return new Response(null,{status:404});
  });
});
afterEach(() => vi.restoreAllMocks());

it('explains the product before sign-in, with a local demo that cannot execute a task', async () => {
  renderRouter({routes:appRoutes,initialEntries:['/'],auth:null});
  expect(screen.getByRole('heading',{level:1})).toHaveTextContent('People and AI.');
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Lin');
  const change=screen.getByRole('tab',{name:/A PA follows a change/});
  await userEvent.click(change);
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Private chat');
  await userEvent.keyboard('{ArrowRight}');
  expect(screen.getByRole('tab',{name:/Progress in parallel/})).toHaveFocus();
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Waiting for a fix');
  expect(screen.getByRole('tabpanel')).toHaveTextContent('In progress');
  await userEvent.keyboard('{End}');
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Results return');
  const note=screen.getByRole('button',{name:/Release verification/});
  await userEvent.click(note);
  expect(note).toHaveAttribute('aria-expanded','true');
  expect(screen.getByText(/Completed: export regression/)).toBeVisible();
  await userEvent.click(screen.getByRole('button',{name:/Start again/}));
  expect(screen.getByRole('tab',{name:/Discuss together/})).toHaveAttribute('aria-selected','true');
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getAllByRole('link',{name:/Create your personal space/})[0]).toHaveAttribute('href','/register');
});

it('keeps protected chat behind sign-in', async () => {
  renderRouter({routes:appRoutes,initialEntries:['/chat'],auth:null});
  expect(await screen.findByRole('button',{name:'Sign in'})).toBeInTheDocument();
  expect(screen.queryByRole('heading',{name:'Your personal assistant starts here.'})).not.toBeInTheDocument();
});

it('gives a returning empty personal account a setup route, not a disabled creation dialog', async () => {
  renderRouter({routes:appRoutes,initialEntries:['/'],auth:{...TEST_AUTH_USER,personal_space_enabled:true,membership_status:'none',owned_node_ids:[]}});
  const next=await screen.findByRole('link',{name:/Connect your first computer/});
  expect(screen.queryByText('Select a conversation')).not.toBeInTheDocument();
  expect(screen.queryByText('Generate skill')).not.toBeInTheDocument();
  await userEvent.click(next);
  expect(await screen.findByRole('heading',{name:'Connect your computer'})).toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('link',{name:/Continue later, open your space/}));
  await waitFor(()=>expect(screen.getByRole('heading',{name:'Your personal assistant starts here.'})).toBeInTheDocument());
});
