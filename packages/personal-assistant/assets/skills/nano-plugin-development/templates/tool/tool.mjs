export const inject = ['tools'];

export function apply(ctx) {
  ctx.tools.register({
    name: 'workspace_total',
    description: '汇总整数分金额，返回笔数和总分数。',
    parameters: { type: 'object', properties: { cents: { type: 'array', items: { type: 'integer' } } }, required: ['cents'], additionalProperties: false },
    output: {
      schema: { type: 'object', properties: { count: { type: 'integer' }, totalCents: { type: 'integer' } }, required: ['count', 'totalCents'] },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
    },
    execute: ({ cents }) => ({ count: cents.length, totalCents: cents.reduce((sum, value) => sum + value, 0) }),
  });
}
