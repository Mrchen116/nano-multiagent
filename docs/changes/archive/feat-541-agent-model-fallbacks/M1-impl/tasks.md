# feat-541 M1 实施块

## 范围

Gateway 持备用链与粘性；内核 per-run 单模型，窄开失败文案 / `error.kind` / replay-last-user。配置 `model_fallbacks` 与前端折叠入口。Coding CLI 无备用链。

## 实施块

1. 内核三条缝：失败气泡含模型 id、`run_status.error.kind`、SDK `replay_last_user`
2. 配置：IM profile / SQLite / API / YAML / `AgentWorkspaceConfig` / apply 校验
3. 选模与粘性：`resolve_model_candidates`、第一次 admit 用 `candidates[0]`、心跳/cron 显式 `model=`
4. Failover 循环：聊天 / 心跳 / cron；失败带 kind 返回；成功 replay 不重投失败气泡；说明只发一次
5. 前端折叠备用列表 + i18n + vitest
6. 合同：列表不进内核；PA 不 import `agent.core`

## 验证

最窄相关 pytest / vitest，见 `progress.md`。
