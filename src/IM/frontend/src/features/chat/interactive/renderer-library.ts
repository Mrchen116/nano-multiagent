import { defineAction } from '@openuidev/react-lang';
import { z } from 'zod';
import { library } from './open-intelligent-ui/library';

export const SendToChat = defineAction({
  name: 'SendToChat',
  description: "Post a user message with submitted UI state to the current conversation and mark the card's Agent for attention. The optional context travels with the submitted message.",
  params: z.object({message: z.string(), context: z.any().optional()}),
});

export const ComposeMessage = defineAction({
  name: 'ComposeMessage',
  description: 'Adopt text into the signed-in user’s composer for an explicit Nano IM conversation id. Does not send or ask an Agent.',
  params: z.object({target: z.string(), text: z.string()}),
});

/** Web and iOS render exactly the same catalog, without loading prompt generation. */
export const interactiveLibrary = library.extend({actions: {add: [SendToChat, ComposeMessage]}});
