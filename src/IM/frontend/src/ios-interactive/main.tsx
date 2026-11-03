import React, { Component, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Renderer, type ActionEvent } from '@openuidev/react-lang';
import { ThemeProvider } from '@openuidev/react-ui';
import '@openuidev/react-ui/defaults.css';
import '@openuidev/react-ui/components.css';
import { interactiveLibrary } from '../features/chat/interactive/renderer-library';
import { nativeRequest } from './bridge';
import './style.css';

interface Configuration {source: string; state: Record<string, unknown>; disabled: boolean}

class Boundary extends Component<React.PropsWithChildren, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  componentDidCatch(error: Error) { void nativeRequest({type: 'error', message: error.message}); }
  render() { return this.state.failed ? <p role="alert">无法呈现交互内容，请阅读消息正文。</p> : this.props.children; }
}

function Card({config}: {config: Configuration}) {
  const [disabled, setDisabled] = useState(config.disabled);
  window.nanoSetStatus = value => setDisabled(value.disabled);
  const label = React.useRef('');
  // Refs persist through host status changes; Renderer owns reactive local state.
  const state = React.useRef(config.state);
  const touched = React.useRef(false);
  const sequence = React.useRef(0);
  function report() {
    return {state: state.current, touched: touched.current, sequence: ++sequence.current};
  }
  async function action(event: ActionEvent) {
    try { await nativeRequest({type: 'action', event, label: label.current, ...report()}); }
    catch (error) { await nativeRequest({type: 'error', message: String(error)}); }
  }
  const tools = React.useMemo(() => Object.fromEntries(['conversation_messages', 'continue_conversation'].map(name => [name,
    (args: Record<string, unknown>) => nativeRequest({type: 'tool', name, args, label: label.current, ...report()}),
  ])), []);
  return <section className="native-card" onPointerDownCapture={() => {touched.current = true;}}
    onKeyDownCapture={() => {touched.current = true;}} onChangeCapture={() => {touched.current = true;}}
    onClickCapture={event => {
      touched.current = true;
      const target = event.target instanceof Element ? event.target.closest('button,[role="button"],a') : null;
      label.current = (target?.getAttribute('aria-label') || target?.textContent || '').trim();
    }}>
    <fieldset disabled={disabled} inert={disabled}>
      <ThemeProvider mode="light" cssSelector=".native-card">
        <Renderer response={config.source} library={interactiveLibrary} initialState={config.state}
          toolProvider={tools} publishObservability={false}
          onParseResult={parsed => {
            state.current = {...parsed?.stateDeclarations, ...state.current};
            void nativeRequest({type: 'state', ...report()});
          }}
          onStateUpdate={value => {state.current = value; void nativeRequest({type: 'state', ...report()});}}
          onAction={event => {void action(event);}}
          onError={errors => {
            if (errors.length) void nativeRequest({type: 'error', message: errors.map(error => error.message).join('\n')});
          }} />
      </ThemeProvider>
    </fieldset>
  </section>;
}

async function start() {
  const config = await nativeRequest({type: 'ready'}) as Configuration;
  createRoot(document.getElementById('root')!).render(<Boundary><Card config={config}/></Boundary>);
  let last = 0;
  new ResizeObserver(() => {
    const height = Math.ceil(document.getElementById('root')!.getBoundingClientRect().height);
    if (height !== last) {last = height; void nativeRequest({type: 'height', height});}
  }).observe(document.getElementById('root')!);
}
void start();
