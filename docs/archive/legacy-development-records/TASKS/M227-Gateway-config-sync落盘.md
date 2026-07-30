# M227 Gateway config.sync落盘

## Goal
当 IM 通过 `config.sync` 通知 Gateway 配置变更时，Gateway 拉取最新 agent 配置后，除了更新内存态 registry，还要把配置落盘到本地 `config.yaml`，确保重启后仍能恢复，且 IM 离线时继续使用最近稳定本地配置。

## Roadpoints
- [x] 确认架构约束：不在 Gateway 暴露 HTTP API，沿用 Gateway 主动 WebSocket + IM HTTP 拉取模型
- [x] 扩展 `_IMConfigSyncClient`，使其在 sync 后持久化本地配置
- [x] 将 `system_prompt` / `skills` / `tool_allowlist` / `group_reply_policy` / `default_model` 一并写入本地 `AgentWorkspaceConfig`
- [x] 增加落盘测试，验证 `config.yaml` 真实变化且可重新加载
- [x] 跑定向测试并完成提交
