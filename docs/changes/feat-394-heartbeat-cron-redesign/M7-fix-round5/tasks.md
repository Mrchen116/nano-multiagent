# M7-fix-round5: Tasks

## 目标

修复 Round 5 acceptance 发现的全部崩点，并补全 cron 可见投递链（从未实现），
使 cron 任务到点执行后结果真正出现在直聊。

## 退出标准

- `[live]` cron job 到点执行 → IM 直聊出现 cron 结果消息（贴 DB/截图证据）
- `[live]` heartbeat 开启 + 非空 HEARTBEAT.md → 直聊出现 heartbeat 消息
- `[live]` 对 agent 说写 HEARTBEAT.md → agent 用 file 工具写成功
- `[live]` activeHours UI 存在，可配置 start/end
- `[live]` 过期 at 任务重启不触发
- `pytest -m "not e2e"` 全绿（含 im_service）；tsc -b + vitest 全绿

## 测试策略

- R1 (RunOrigin.CRON + unattended): 加 CRON 枚举，单测 submit_message 映射 + gate
- R2 (cron 投递链): 端到端集成测试——注册→消费→observer 发出 streaming_delta；
  复用 test_cron_awareness.py 里的 shim 模式
- R3 (file tools): 单测 sync_agent cron 自动追加 "cron" 时不丢失 DEFAULT_TOOL_IDS
- R4 (activeHours UI): 前端 vitest + tsc 通过；浏览器验收
- R5 (at 过期): _AtSchedule 单测——过期 at + last_due_at=None → 不触发

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | RunOrigin.CRON + submit_message 映射 + _UNATTENDED_ORIGINS | DONE |
| R2 | cron 可见投递链：播种 run_context_store + 消费 stream | DONE |
| R3 | file 工具缺失：cron 追加不覆盖 DEFAULT_TOOL_IDS | DONE |
| R4 | activeHours UI 控件（agent-detail/create page） | DONE |
| R5 | _AtSchedule 过期 at 不补跑 | DONE |
| R6 | 端到端验证 + 文档收口 | DONE |
