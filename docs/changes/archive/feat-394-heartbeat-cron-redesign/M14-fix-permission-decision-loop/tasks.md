# feat-394-M14 tasks — 权限决策回路 + cron NameError 修复

## 目标

修复两个 live 实测暴露的运行时缺陷：
1. Issue A：用户点击 IM 权限卡片 Allow/Deny 无任何反应（run 永久 park）
2. Issue B：cron tick 每次 NameError(`_WCD` 名不在 `_cron_tick_for_agent` 作用域)，cron 子系统全瘫

## 退出标准

- Issue A：权限卡片全链路可用：IM 卡片出现 → 点 Allow once → run 恢复 → 工具真执行；点 Deny → 工具被拒，run 结束
- Issue B：cron tick 无 NameError；配置 30s cron 任务投递到直聊，日志无 NameError
- `pytest -m "not e2e"` 全绿（不计预存失败的 2 个 IM 集成测试）
- contract 白名单行号如有位移则同步更新

## 测试策略

- Issue A：新增权限回路单测（broker.resolve → future done → response 正确）；删 SDK 死代码赋值行的 `# type: ignore`；live e2e 验收（kimiCoding:K2.6 模型怪癖触发 ask）
- Issue B：补 `_cron_tick_for_agent` 调到 `state_store` 构造行的回归测试；确保测试不被更早的 stub 截断

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | cron NameError 修复（Issue B） | DONE |
| R2 | 权限回路修复（Issue A）— SDK + runtime + gateway | DONE |
| R3 | 全量测试 + contract 白名单 + live e2e | DONE |
