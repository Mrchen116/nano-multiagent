import {AgentLifecycles, lifecycle} from './agent-lifecycle.js';
import type {ImContext} from './context.js';
import type {ConfigurationDependencies} from './control.js';

/** Adapt the center's services to the configuration owner's three dependencies. */
export function configurationDependencies(ctx: ImContext): ConfigurationDependencies {
  return {
    db: ctx.db,
    request: (node, command, payload) => ctx.gateway.request(node, command, payload),
    deliverLifecycle: agent => new AgentLifecycles(ctx).deliver(lifecycle(ctx.db, agent)),
  };
}
