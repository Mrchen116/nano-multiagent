import type {Context} from '@deepseek-ai/cordis';
import type {} from '@deepseek-ai/dsh-agent';

export const name = 'nano-context-order';

/** Keep native environment updates ahead of the input they describe. */
export function apply(ctx: Context): void {
  ctx.on('agent/pre-step', async (_payload, next) => {
    // Wait for native contributors; never move historical context or synthesize updates.
    const decision = await next();
    if (decision.kind !== 'enter') return decision;
    const runtime = decision.messages.filter(message => String(message.source.kind) === 'runtime-context');
    const catalog = decision.messages.filter(message => message.source.kind === 'skill-catalog');
    const environment = [...runtime, ...catalog];
    if (!environment.length) return decision;
    const updates = new Set(environment);
    return {...decision, messages: [...environment, ...decision.messages.filter(message => !updates.has(message))]};
  }, {prepend: true});
}
