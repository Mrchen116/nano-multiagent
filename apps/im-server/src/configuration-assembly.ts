import {AgentLifecycles, lifecycle} from './agent-lifecycle.js';
import type {ImContext} from './context.js';
import {ConfigOperations, type ConfigurationDependencies} from './control.js';

/** Adapt the center's services to the configuration owner's three dependencies. */
export function configurationDependencies(ctx: ImContext): ConfigurationDependencies {
  return {
    db: ctx.db,
    request: (node, command, payload) => ctx.gateway.request(node, command, payload),
    deliverLifecycle: agent => new AgentLifecycles(ctx).deliver(lifecycle(ctx.db, agent)),
  };
}

const operations = new WeakMap<ImContext, ConfigOperations>();
/** Both settings routes must serialize edits and receipt recovery on the same agent queue. */
export function configurationOperations(ctx: ImContext): ConfigOperations {
  let ops = operations.get(ctx);
  if (!ops) {
    ops = new ConfigOperations(configurationDependencies(ctx));
    operations.set(ctx, ops);
  }
  return ops;
}
