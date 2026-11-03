import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { it, expect } from 'vitest';
import { Renderer } from '@openuidev/react-lang';
import { interactiveLibrary, interactivePrompt } from './catalog';
import { library } from './open-intelligent-ui/library';

it('preserves the upstream components, functions and worked examples', () => {
  expect(Object.keys(interactiveLibrary.components)).toEqual(Object.keys(library.components));
  expect(interactivePrompt).toContain('Svg(');
  expect(interactivePrompt).toContain('HtmlView(');
  expect(interactivePrompt).toContain('@Clamp');
});
it('restores edits, computes with upstream functions, and keeps drawing/actions local', async () => {
  const source = `$n = 1
root = Col([Input($n, "数量", "number"), Text("数量 " + @Clamp($n, 0, 9)), Svg([Rect(0, 0, $n * 10, 20)], "0 0 100 30"), Button("下一步", @Set($n, $n + 1)), Button("重置", @Reset($n))])`;
  let state:Record<string, unknown> = {}; let requests=0;
  const first=render(<Renderer response={source} library={interactiveLibrary} publishObservability={false} onStateUpdate={value=>{state=value}} onAction={()=>{requests++}} />);
  fireEvent.click(await screen.findByRole('button',{name:'下一步'}));
  expect(await screen.findByText('数量 2')).toBeVisible();
  expect(document.querySelector('rect')).toHaveAttribute('width', '20');
  await waitFor(()=>expect(state['$n']).toBe(2));
  first.unmount();
  render(<Renderer response={source} library={interactiveLibrary} initialState={state} publishObservability={false} onAction={()=>{requests++}} />);
  expect(await screen.findByText('数量 2')).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'重置'}));
  expect(await screen.findByText('数量 1')).toBeVisible();
  expect(requests).toBe(0);
});
