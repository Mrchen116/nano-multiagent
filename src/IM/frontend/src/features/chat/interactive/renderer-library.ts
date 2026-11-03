import { defineAction } from '@openuidev/react-lang';
import { z } from 'zod';
import { library } from './open-intelligent-ui/library';

export const ComposeMessage = defineAction({
  name: 'ComposeMessage',
  description: 'Adopt text into the signed-in user’s composer for an explicit Nano IM conversation id. Does not send or ask an Agent.',
  params: z.object({target: z.string(), text: z.string()}),
});

/** Web and iOS render exactly the same catalog, without loading prompt generation. */
export const interactiveLibrary = library.extend({actions: {add: [ComposeMessage]}});
