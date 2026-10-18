import { defineTool } from '@deepseek-ai/dsh-tools';
export const inject = ['tools'];

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'workspace_total',
    description: '汇总整数分金额，返回笔数和总分数。',
    parameters: { cents: { type: 'array', items: { type: 'integer' }, required: true } },
    output: {
      schema: { type: 'object', properties: { count: { type: 'integer', required: true }, totalCents: { type: 'integer', required: true } }, additionalProperties: false },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
    },
    execute: ({ cents }) => ({ count: cents.length, totalCents: cents.reduce((sum, value) => sum + value, 0) }),
  }));
}
