import React from 'react';
import { defineComponent, useFormName, useFormValidation, useIsStreaming, useTriggerAction } from '@openuidev/react-lang';
import { openuiLibrary, Button } from '@openuidev/react-ui';
import { z } from 'zod';
import { compositionExamples } from './composition-examples';

const ContinueButton = defineComponent({
  name: 'ContinueButton',
  description: 'Submit the visible label and current choices as a new user message. Use a unique static id and a clear static label naming the intended next step.',
  props: z.object({ id: z.string(), label: z.string() }),
  component: ({ props }) => {
    const trigger = useTriggerAction();
    const form = useFormName();
    const validation = useFormValidation();
    const disabled = useIsStreaming();
    return <Button disabled={disabled} onClick={() => {
      if (!validation || validation.validateForm()) trigger(props.label, form, { type: 'nano_continue', params: { action_id: props.id } });
    }}>{props.label}</Button>;
  },
});

// Extend only for already-published messages; all upstream components and slots remain.
const Form = defineComponent({
  name: 'Form', description: openuiLibrary.components.Form.description,
  props: openuiLibrary.components.Form.props.extend({buttons: z.union([openuiLibrary.components.Form.props.shape.buttons, ContinueButton.ref])}),
  component: openuiLibrary.components.Form.component,
});
// Keep upstream rendering and props; expose only a hook for responsive card rows.
const UpstreamStack = openuiLibrary.components.Stack.component;
const Stack = defineComponent({
  name: 'Stack', description: openuiLibrary.components.Stack.description,
  props: openuiLibrary.components.Stack.props,
  component: args => args.props.direction === 'row' && args.props.wrap
    ? <div className="nano-ui-card-row" style={{ display: 'contents' }}><UpstreamStack {...args} /></div>
    : <UpstreamStack {...args} />,
});
export const interactiveLibrary = openuiLibrary.extend({
  components: { add: [{ component: ContinueButton, slots: ['Card.children'] }], override: [Form, Stack] },
});

export const interactiveTools = [
  { name: 'conversation_messages', mode: 'read', description: 'Read messages from the current conversation as the signed-in viewer. Query only.', parameters: { type: 'object', properties: { limit: { type: 'integer' } } } },
  { name: 'continue_conversation', mode: 'write', description: 'Send a new user request with the current UI state to this reply author. Mutation only; returns an enqueue receipt, not a completed business result.', parameters: { type: 'object', properties: { message: { type: 'string' }, context: {} }, required: ['message'] } },
] as const;

const libraryPrompt = interactiveLibrary.prompt({
  preamble: 'Write OpenUI inside send_message.interactive.source. Keep text an independently readable summary. Choose useful interactive explanations, explorations, comparisons or editors when these help the user understand or work with the subject.',
  bindings: true, builtinFunctions: true, toolCalls: true, editMode: true,
  tools: interactiveTools.map(tool => ({name:tool.name, description:tool.description, inputSchema:{...tool.parameters},outputSchema:{}})),
  additionalRules: [
    'COMPOSITION: Nano owns colors, fonts, borders, control appearance and chart palettes. Choose structure and semantic variants, not a new skin. Lead with one useful conclusion or question, then the main exploration or comparison, then supporting detail. Do not give every fact an equally prominent card.',
    'Use three spacing levels: tight text/labels (Stack gap s), related controls/results (m or l), and separate sections (xl). Use a clear Stack as the page scaffold, Card for a distinct result or input group, sunk for a secondary control group. Avoid a Card around the entire page and cards nested inside cards. Use short paragraphs in cards; move lengthy background into plain sections or Tabs.',
    'Put the most important control close to its changing result and explanatory graphic. Use charts for quantitative relationships, Steps for processes, tables for comparable facts; a graphic must explain something. Label units, series and assumptions. A large headline result plus a small comparison is usually clearer than four equally weighted metrics. Do not repeat the same title, summary or numbers in several sections.',
    'For side-by-side content use Stack with direction row and wrap true; the host gives direct Cards a readable column width and wraps them in narrow panels. Keep compared options symmetric in labels, order and units. Keep button groups in Buttons. Prefer a few meaningful controls; secondary detail should not push the first useful result far below the controls on a phone.',
    'Before sending, check the first screen: can the reader identify the main idea and next useful interaction without reading everything? Keep essential output in the main flow, with related explanation nearby. Use Tabs only for genuinely alternate views or optional details, never to hide the only result behind a vague label. Use semantic heading hierarchy and concise labels. The examples illustrate composition, not fixed topics or mandatory templates.',

    'Choose controls that materially help understanding, comparison or input. Distinguish user values, retrieved facts, calculations and explicitly labeled illustrative assumptions. Rendering is not a data source or proof of execution; do not invent live values, task progress, persistence or connected business tools.',
    'Use the complete registered library and native language: local state, computations, conditions, Each, Action, Set and Reset. Fields may stand alone or belong to Forms. Local exploration must respond immediately without a new conversation turn. Build meaningful relations between controls, visual results and explanations, not decorative controls.',
    'Use native Button with ToAssistant only when the user explicitly requests a new Agent response. Multiple local and continuation buttons are supported; the interface remains usable after a request. ContinueButton exists for older messages; prefer native Button in new programs.',
    'The only currently connected tools are conversation_messages for Query and continue_conversation for Mutation. The current conversation and user identity come from the host. No filesystem or arbitrary shell/network tool is implicitly connected. Use ToAssistant OR the continue_conversation Mutation for a request, not both for the same request.',
    'OpenUrl supports http/https navigation. Declare every mutable variable with the dollar prefix. Use actual values for editable content, never placeholders as the content. Labels and units must make parameter changes understandable. Keep the main chat readable on narrow screens.',
    'Match control binding types exactly: Input/TextArea/Select/RadioGroup values are strings, including numeric-looking option IDs; Slider values are number arrays. Set must preserve the bound type. Convert an arithmetic result to a string with empty-string concatenation when storing it in a string-bound variable; use numeric coercion only for calculations.',
    'For edits, send interactive.source_mode="patch" with supersedes_message_id and changed statements, or send a full new source. New versions retain the original publicly readable history.',
    'After send_message confirms delivery, end with the exact non-empty final text NO_REPLY; the host suppresses it because the interactive reply is already delivered. Never end with an empty response.',
  ],
}).replace('as the third Form argument', 'as the second Form argument'); // Match the published Form schema; upstream prose has the wrong position.

export const interactiveCompositionGuide = '\n## Composition examples\n\n' + compositionExamples.map(example =>
  `### ${example.title}\n${example.intent}\n\n\`\`\`openui\n${example.source}\n\`\`\``,
).join('\n\n');

export const interactivePrompt = libraryPrompt + interactiveCompositionGuide;
