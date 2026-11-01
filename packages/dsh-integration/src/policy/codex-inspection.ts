import type { Context } from '@deepseek-ai/cordis';
import type { ToolDefinition } from '@deepseek-ai/dsh-tools';

export const inspectionNames = ['read', 'read_image', 'glob', 'grep'] as const;

/** Capture host definitions without consulting the parent workspace's tool overlays.
 *
 * Args:
 *   ctx: Host runtime service context, outside every workspace/agent scope.
 * Returns:
 *   The native read-only definitions, including their schemas and executors.
 */
export function inspectionTools(ctx: Context): ToolDefinition[] {
  return inspectionNames.map(name => {
    const tool = ctx.tools.get(name);
    if (!tool) throw new Error(`Native review inspection tool unavailable: ${name}`);
    return tool;
  });
}
