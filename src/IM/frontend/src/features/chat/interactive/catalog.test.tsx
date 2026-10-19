import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { defineComponent, Renderer } from '@openuidev/react-lang';
import { interactiveLibrary } from './catalog';
import { openuiLibrary } from '@openuidev/react-ui';

const source = `root = Stack([form])
form = Form("draft", send, [field])
field = FormControl("消息草稿", TextArea("body", "编辑草稿", 3, null, "林悦，周六11点断桥见"))
send = ContinueButton("continue", "继续修改")`;

describe('interactive catalogue', () => {
  it('retains edited content on remount and emits only the visible continuation', async () => {
    let state: Record<string, unknown> = {};
    let action: unknown;
    const first = render(<Renderer response={source} library={interactiveLibrary} publishObservability={false} onStateUpdate={value => { state = value; }} onAction={value => { action = value; }} />);
    const field = await screen.findByRole('textbox');
    expect(field).toHaveValue('林悦，周六11点断桥见');
    fireEvent.change(field, { target: { value: '林悦，改成周日10点吧' } });
    await waitFor(() => expect(JSON.stringify(state)).toContain('周日10点'));
    first.unmount();
    render(<Renderer response={source} library={interactiveLibrary} initialState={state} publishObservability={false} onAction={value => { action = value; }} />);
    expect(await screen.findByRole('textbox')).toHaveValue('林悦，改成周日10点吧');
    fireEvent.click(screen.getByRole('button', { name: '继续修改' }));
    expect(action).toMatchObject({ type: 'nano_continue', params: { action_id: 'continue' }, humanFriendlyMessage: '继续修改' });
  });
});

it('preserves every upstream component and executes local actions without host messages', async () => {
  expect(Object.keys(interactiveLibrary.components)).toEqual(expect.arrayContaining(Object.keys(openuiLibrary.components)));
  let requests=0;
  render(<Renderer response={'$n = 1\nroot = Stack([TextContent("" + $n), Button("下一步", @Set($n, $n + 1)), Button("重置", @Reset($n))])'} library={interactiveLibrary} publishObservability={false} onAction={() => {requests++}} />);
  fireEvent.click(await screen.findByRole('button',{name:'下一步'}));
  expect(await screen.findByText('2')).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'重置'}));
  expect(await screen.findByText('1')).toBeVisible();
  expect(requests).toBe(0);
});

it('keeps the published composition examples executable with local state and no host request', async () => {
  // This seam covers program bindings/actions; browser acceptance covers chart layout.
  const library = interactiveLibrary.extend({ components: { override: ['LineChart', 'BarChart'].map(name =>
    defineComponent({ ...openuiLibrary.components[name], component: () => null }),
  ) } });
  const { compositionExamples } = await import('./composition-examples');
  let requests = 0;
  const reading = render(<Renderer response={compositionExamples[0].source} library={library} publishObservability={false} onAction={() => { requests++; }} />);
  const minutes = await screen.findByRole('spinbutton');
  expect(await screen.findByText('140 分钟')).toBeVisible();
  fireEvent.change(minutes, { target: { value: '30' } });
  expect(await screen.findByText('210 分钟')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: '恢复20分钟' }));
  expect(await screen.findByText('140 分钟')).toBeVisible();
  reading.unmount();
  render(<Renderer response={compositionExamples[1].source} library={library} publishObservability={false} onAction={() => { requests++; }} />);
  const days = await screen.findByRole('spinbutton');
  expect(await screen.findByText('每周 20 元')).toBeVisible();
  expect(await screen.findByText('每周 50 元')).toBeVisible();
  fireEvent.change(days, { target: { value: '6' } });
  expect(await screen.findByText('每周 24 元')).toBeVisible();
  expect(await screen.findByText('每周 60 元')).toBeVisible();
  expect(requests).toBe(0);
});
