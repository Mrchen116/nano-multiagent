export const inject = ['systemPrompt'];

export function apply(ctx) {
  ctx.systemPrompt.section({
    name: 'workspace-report-format', order: 850, interpolate: false,
    text: '提供报销分析时，依次给出“汇总”“分类明细”“待核对事项”。金额来自实际数据；没有待核对事项时明确写“无”。其他任务保持原有回答方式。',
  });
}
