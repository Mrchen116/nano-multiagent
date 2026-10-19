import React from 'react';
import { createLibrary, defineComponent, useFormName, useFormValidation, useIsStreaming, useTriggerAction } from '@openuidev/react-lang';
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

// Keep the upstream form layout/validation, with a visible, host-owned continuation.
const Form = defineComponent({
  name: 'Form',
  description: 'A named group of labelled fields with one ContinueButton.',
  props: z.object({ name: z.string(), buttons: ContinueButton.ref, fields: z.array(openuiLibrary.components.FormControl.ref).default([]) }),
  component: openuiLibrary.components.Form.component,
});
const names = new Set([
  'Stack', 'Card', 'CardHeader', 'TextContent', 'Form', 'FormControl',
  'Input', 'TextArea', 'Select', 'SelectItem', 'Slider', 'CheckBoxGroup', 'CheckBoxItem',
  'RadioGroup', 'RadioItem', 'Table', 'Col', 'BarChart', 'LineChart', 'Series', 'Separator',
]);

/** The only catalogue used to generate the server schema and model instructions. */
const narrowedLibrary = openuiLibrary.extend({
  components: {
    add: [{ component: ContinueButton, slots: ['Card.children'] }],
    override: [Form],
    remove: Object.keys(openuiLibrary.components).filter(name => !names.has(name)),
  },
});

// Upstream group notes refer to components removed from this catalogue.
export const interactiveLibrary = createLibrary({
  components: Object.values(narrowedLibrary.components), root: 'Stack', id: 'nano-1',
  componentGroups: narrowedLibrary.componentGroups?.map(({name, components}) => ({name, components})),
});

export const interactivePrompt = interactiveLibrary.prompt({
  preamble: 'Write an OpenUI program only inside send_message.interactive.source. The text argument remains a readable summary. These language instructions do not replace your normal tool-use or final-answer workflow.',
  bindings: true, builtinFunctions: true, toolCalls: false,
  additionalRules: [
    'Nano supports complete, immutable replies. Use only the components listed here. Never use Query, Mutation, Action, @ToAssistant, @OpenUrl, @Run, HTML or JavaScript.',
    'ContinueButton(id, label) is the only action. Both arguments must be string literals, not variables, expressions or hidden instructions. Local fields never execute business actions.',
    'Use static, unique form and field names. Wrap each field in FormControl with a visible label. Declare every mutable variable with the dollar prefix: $mode = "walk", then bind Select value to $mode. mode = "walk" is an ordinary constant and does NOT initialize $mode. Use bindings for local derived displays. Keep all fields inside a named Form; conditional controls and dynamically generated fields are unsupported.',
    'Editable drafts must use the value argument, never placeholder as content: TextArea("draft", "Edit the draft", 4, null, "Actual editable draft"). Initialize chosen values explicitly; do not tell users a blank value means accepting hidden defaults.',
    'Use a single primary continuation. Form(name, continueButton, fields) accepts ContinueButton directly. Keep mobile layouts readable; do not add large navigation sections.',
    'Provide an independently readable text summary alongside the interactive response. Plain questions should receive plain text. After send_message confirms delivery, end with the exact non-empty final text NO_REPLY; the host suppresses this sentinel because the card is already delivered. Never end with an empty response.',
  ],
});
