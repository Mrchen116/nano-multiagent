import React from 'react';
import { defineComponent, useFormName, useFormValidation, useIsStreaming, useTriggerAction } from '@openuidev/react-lang';
import { openuiLibrary } from '@openuidev/react-ui/genui-lib';
import { Button } from '@openuidev/react-ui';
import { z } from 'zod';

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
export const interactiveLibrary = openuiLibrary.extend({
  components: { add: [{ component: ContinueButton, slots: ['Card.children'] }], override: [Form] },
});

export const interactiveTools = [
  { name: 'conversation_messages', mode: 'read', description: 'Read messages from the current conversation as the signed-in viewer. Query only.', parameters: { type: 'object', properties: { limit: { type: 'integer' } } } },
  { name: 'continue_conversation', mode: 'write', description: 'Send a new user request with the current UI state to this reply author. Mutation only; returns an enqueue receipt, not a completed business result.', parameters: { type: 'object', properties: { message: { type: 'string' }, context: {} }, required: ['message'] } },
] as const;

export const interactivePrompt = interactiveLibrary.prompt({
  preamble: 'Write OpenUI inside send_message.interactive.source. Keep text an independently readable summary. Choose useful interactive explanations, explorations, comparisons or editors when these help the user understand or work with the subject.',
  bindings: true, builtinFunctions: true, toolCalls: true, editMode: true,
  tools: interactiveTools.map(tool => ({name:tool.name, description:tool.description, inputSchema:{...tool.parameters},outputSchema:{}})),
  additionalRules: [
    'Choose controls that materially help understanding, comparison or input. Distinguish user values, retrieved facts, calculations and explicitly labeled illustrative assumptions. Rendering is not a data source or proof of execution; do not invent live values, task progress, persistence or connected business tools.',
    'Use the complete registered library and native language: local state, computations, conditions, Each, Action, Set and Reset. Fields may stand alone or belong to Forms. Local exploration must respond immediately without a new conversation turn. Build meaningful relations between controls, visual results and explanations, not decorative controls.',
    'Use native Button with ToAssistant only when the user explicitly requests a new Agent response. Multiple local and continuation buttons are supported; the interface remains usable after a request. ContinueButton exists for older messages; prefer native Button in new programs.',
    'The only currently connected tools are conversation_messages for Query and continue_conversation for Mutation. The current conversation and user identity come from the host. No filesystem or arbitrary shell/network tool is implicitly connected. Use ToAssistant OR the continue_conversation Mutation for a request, not both for the same request.',
    'OpenUrl supports http/https navigation. Declare every mutable variable with the dollar prefix. Use actual values for editable content, never placeholders as the content. Labels and units must make parameter changes understandable. Keep the main chat readable on narrow screens.',
    'Match control binding types exactly: Input/TextArea/Select/RadioGroup values are strings, including numeric-looking option IDs; Slider values are number arrays. Set must preserve the bound type. Convert an arithmetic result to a string with empty-string concatenation when storing it in a string-bound variable; use numeric coercion only for calculations.',
    'For edits, send interactive.source_mode="patch" with supersedes_message_id and changed statements, or send a full new source. New versions retain the original publicly readable history.',
    'After send_message confirms delivery, end with the exact non-empty final text NO_REPLY; the host suppresses it because the interactive reply is already delivered. Never end with an empty response.',
  ],
});
