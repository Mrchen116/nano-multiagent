import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import * as Cordis from '@deepseek-ai/cordis'
import * as React from 'react'
import * as Store from '@deepseek-ai/dsh-client-store'
import { it, expect } from 'vitest'
import { registerTrajectoryMessageDefinitions } from '../src/client/trajectory-message-definitions'
import { registerTrajectoryRequestHeaderDefinition } from '../src/client/trajectory-request-header-definition'
import { registerTrajectoryAssistantDefinition } from '../src/client/trajectory-assistant-definition'
import { registerTrajectoryToolDefinition } from '../src/client/trajectory-tool-definition'
import { registerTrajectoryCompactionDefinitions } from '../src/client/trajectory-compaction-definition'
import { trajectoryViewDefinition } from '../src/client/trajectory-snapshot-builder'
// Load the pinned browser registration through its public factory, as the viewer does.
// No UI is mounted; React/Cordis/Store are real and UI-only imports stay inert.
let registration: { factory: (load: (id: string) => unknown) => any }
const source = readFileSync(createRequire(import.meta.url).resolve(
  '@deepseek-ai/dsh-client-ui-conversation/client',
), 'utf8')
new Function('window', source)({
  __ModuleLoader__: { load: (value: typeof registration) => { registration = value } },
})
const modules: Record<string, unknown> = {
  '@deepseek-ai/cordis': Cordis,
  react: React,
  '@deepseek-ai/dsh-client-store': Store,
  '@deepseek-ai/dsh-client-ui-primitives': {},
  '@deepseek-ai/dsh-client-ui-slots': {},
  'react/jsx-runtime': {},
  'react-dom': {},
}
const api = registration!.factory((id: string) => {
  if (!(id in modules)) throw new Error(`Unexpected browser dependency: ${id}`)
  return modules[id]
})
const definitions: any[] = []
const ctx: any = {
  uiConversation: {
    events: { register: (definition: any) => definitions.push(definition) },
    inspectRequestPrompt: api.inspectRequestPrompt,
    inspectSystemPrompt: (...args: any[]) => api.UiConversation.prototype.inspectSystemPrompt(...args),
  },
}
for (const register of [
  registerTrajectoryMessageDefinitions,
  registerTrajectoryRequestHeaderDefinition,
  registerTrajectoryAssistantDefinition,
  registerTrajectoryToolDefinition,
  registerTrajectoryCompactionDefinitions,
]) register(ctx)
const at = (seq: number, type: string, data: unknown, extra = {}) => ({
  type: 'event', event: { seq, time: seq, type, data, ...extra },
})
const system = (seq: number, text: string, surfaceOp: unknown = 'append', turn = 1) => at(seq, 'system/message', {
  turn, step: 1,
  message: { id: `system-${seq}`, role: 'system', content: [{ type: 'text', text }], source: { kind: 'system-prompt' } },
}, { surfaceOp })
const header = (seq: number, reason: string) => at(seq, 'request/header', {
  reason, header: { config: { provider: 'test', model: 'test' }, tools: [] },
})
const assistant = (seq: number, turn: number) => at(seq, 'assistant/message', {
  turn, step: 1, stream: [],
  message: { id: `assistant-${seq}`, role: 'assistant', content: [{ type: 'text', text: 'done' }], source: { kind: 'model', provider: 'test', model: 'test' } },
})
function assemble(events: ReturnType<typeof at>[], more = false) {
  const assembler = new api.ConversationNodeAssembler(
    { entries: () => definitions, fallbackEntry: () => undefined },
    { entries: () => [trajectoryViewDefinition] },
  )
  assembler.replaceWindow(events, more)
  assembler.activateTarget('trajectory')
  return assembler
}
// Locations carry observable-store functions; compare the actual display facts.
const displayed = (assembler: any) => {
  const { eventNodes, requests, systemPrompts, runningCalls, partial } = assembler.get('trajectory')
  return { eventNodes, requests, systemPrompts, runningCalls, partial }
}

it('restores initial context and request details across every page boundary of a replaced prompt', () => {
  const history = [
    at(1, 'turn/start', { turn: 1 }), at(2, 'step/start', { turn: 1, step: 1 }),
    system(3, 'initial system prompt'), header(4, 'initial'),
    at(5, 'developer/message', { turn: 1, step: 1, message: {
      id: 'skills', role: 'developer', content: [{ type: 'text', text: 'Skill catalog' }], source: { kind: 'custom' },
    } }, { surfaceOp: 'append' }),
    assistant(6, 1), at(7, 'step/end', { turn: 1, step: 1 }),
    at(8, 'turn/end', { turn: 1, reason: { kind: 'completed' } }),
    at(9, 'turn/start', { turn: 2 }), at(10, 'step/start', { turn: 2, step: 1 }),
    system(11, 'replacement prompt', { op: 'replace', startSeq: 3, endSeq: 3 }, 2),
    header(12, 'series'), assistant(13, 2),
  ]
  const full = displayed(assemble(history))
  expect(full.requests.map((request: any) => request.prompt.system)).toEqual(['initial system prompt', 'replacement prompt'])
  expect(full.eventNodes.some((node: any) => JSON.stringify(node).includes('Skill catalog'))).toBe(true)
  for (let split = 1; split < history.length; split++) {
    const paged = assemble(history.slice(split), true)
    // Load one event at a time, so repeated incremental publication is covered too.
    for (let index = split - 1; index >= 0; index--) {
      paged.prepend([history[index]], index > 0)
      paged.flush()
    }
    expect(displayed(paged)).toEqual(full)
    paged.prepend(history.slice(0, split), false)
    paged.flush()
    expect(displayed(paged)).toEqual(full)
    const next = at(14, 'step/end', { turn: 2, step: 1 })
    paged.append(next)
    paged.flush()
    expect(displayed(paged)).toEqual(displayed(assemble([...history, next])))
  }
})

it('hides a standalone prompt when an older replacement makes its order uncertain, then restores it', () => {
  const earlier = [system(1, 'A'), system(3, 'B')]
  const replacement = system(6, 'C', { op: 'replace', startSeq: 3, endSeq: 3 })
  const tail = system(7, 'known but unordered')
  const paged = assemble([tail], true)
  expect(displayed(paged).systemPrompts?.[0]?.text).toBe('known but unordered')
  paged.prepend([replacement], true)
  paged.flush()
  expect(displayed(paged).systemPrompts).toBeUndefined()
  paged.prepend(earlier, false)
  paged.flush()
  expect(displayed(paged)).toEqual(displayed(assemble([...earlier, replacement, tail])))
})
