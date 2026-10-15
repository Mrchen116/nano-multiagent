export const inject = ['tools', 'workspaceCallCounter'];

export function apply(ctx) {
  ctx.tools.register({
    name: 'workspace_counted_echo', description: '返回输入文本，由局部监听记录成功调用次数。',
    parameters: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'], additionalProperties: false },
    output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
    execute: ({ text }) => text,
  });
  ctx.tools.register({
    name: 'workspace_counter_status', description: '查看当前 Agent preset 的成功 echo 调用次数，重载后清零。',
    parameters: { type: 'object', properties: {}, additionalProperties: false },
    output: { schema: { type: 'integer' }, render: (_args, value) => [{ type: 'text', text: String(value) }] },
    execute: () => ctx.workspaceCallCounter.count,
  });
  // Cordis owns this listener; disabling the bundle disposes it with the consumer.
  ctx.on('tools/result', (exec, result) => {
    if (exec.name === 'workspace_counted_echo' && !result.isError) ctx.workspaceCallCounter.count++;
  });
}
