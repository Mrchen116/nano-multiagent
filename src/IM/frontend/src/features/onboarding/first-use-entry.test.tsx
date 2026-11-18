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
  expect(screen.getByRole('heading',{level:1})).toHaveTextContent('Your team.With AI colleagues.');
  expect(screen.getByRole('region', {name:'Your team, working together'})).toHaveTextContent('Lin Lan');
  const change=screen.getByRole('button',{name:'Catch the change'});
  await userEvent.click(change);
  expect(change).toHaveAttribute('aria-pressed','true');
  expect(screen.getByRole('status')).toHaveTextContent('Preparing');
  await userEvent.click(screen.getByRole('button',{name:'Next step'}));
  expect(screen.getByRole('status')).toHaveTextContent('Moving forward');
  await userEvent.click(screen.getByRole('button',{name:'Bring results back'}));
  expect(screen.getByRole('status')).toHaveTextContent('Your review');
  const document=screen.getByRole('button',{name:'Open release plan'});
  await userEvent.click(document);
  expect(screen.getByRole('dialog')).toHaveTextContent('Nothing has been released');
  await userEvent.keyboard('{Escape}');
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(document).toHaveFocus();
  await userEvent.click(screen.getByRole('button',{name:'Start again'}));
  expect(change).toHaveAttribute('aria-pressed','true');
  await userEvent.click(screen.getByRole('tab',{name:/Specialist Agent/}));
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Quinn');
  await userEvent.click(screen.getByRole('button',{name:/Note · Engineering/}));
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Export retest record.md');
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Different chats. The same partner.');
  screen.getByRole('tab',{name:/Specialist Agent/}).focus();
  await userEvent.keyboard('{Home}');
  expect(screen.getByRole('tab',{name:/Personal assistant/})).toHaveFocus();
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Client update.md');
  await userEvent.click(screen.getByRole('button',{name:/Weekend plans/}));
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Weekend checklist.md');
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Milo');
  expect(screen.getByRole('heading',{name:/Start with a space of your own/})).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getAllByRole('link',{name:/Create account/})[0]).toHaveAttribute('href','/register');
  screen.getByRole('combobox',{name:'Language'}).focus();
  await userEvent.keyboard('{ArrowDown}');
  await userEvent.click(screen.getByRole('option',{name:'简体中文'}));
  expect(screen.getByRole('heading',{level:1})).toHaveTextContent('让 AI 同事，加入你的团队。');
  expect(screen.getByRole('button',{name:'接住变化'})).toHaveAttribute('aria-pressed','true');
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
  await userEvent.click(await screen.findByRole('button', {name:'Set up my assistant'}));
  expect(await screen.findByRole('heading',{name:'Connect your computer'})).toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('link',{name:/Continue later, open your space/}));
  await waitFor(()=>expect(screen.getByRole('heading',{name:'Your personal assistant starts here.'})).toBeInTheDocument());
});
