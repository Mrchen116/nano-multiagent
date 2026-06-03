# feat-394-M5-fix-round3 Tasks

## 目标

修复 round-3 验收的三个问题：R3-1（blocking：cron 工具被 auto_mode_gate 拦截）、R3-2（major：preview 端点不受开关控制）、R3-3（minor：heartbeat 25min 不 tick）。live-first 打法：先起 live 环境复现，端到端 trace 整链路，修完亲跑通过。

## 退出标准

1. cron 工具调用成功（不被 auto_mode_gate 拦截，jobs.json 创建）
2. preview 端点 4 组合每个显示不同内容（hb/cron 参数生效）
3. heartbeat 在 HEARTBEAT.md 有内容时正常 tick（last_due_at 更新）
4. pytest -m "not e2e"（含 IM + contract）只有预存 macOS 失败 + tsc -b + vitest 全绿

## 测试策略

- R3-1：单测 CronTool.check_permissions 返回 allow（test_cron_tool_permissions.py）；live 验证通过 auto_mode_gate 分析
- R3-2：单测 PromptPreviewRequest 字段 + route 参数传递（test_preview_heartbeat_cron_params.py）；live 验证 4 组合 API 测试
- R3-3：heartbeat 已在 live 环境通过（last_due_at 更新证据），根因是 HEARTBEAT.md 空内容，非代码 bug

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | cron check_permissions + preview 参数红测 + live 复现 | DONE |
| R2 | 实现修复 + live 验证 | DONE |
| R3 | 文档 + 全套测试通过 | DONE |
