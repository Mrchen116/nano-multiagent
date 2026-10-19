import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Renderer } from '@openuidev/react-lang';
import { interactiveLibrary } from './catalog';

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
