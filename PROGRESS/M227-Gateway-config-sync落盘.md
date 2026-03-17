# M227 Gateway config.sync落盘

## Context
`docs/Gateway配置归位整改计划.md` 原阶段 B 写成“Gateway 暴露配置 HTTP API”。核对 `docs/NodeGateway-SPEC.md` 后确认这是错误方向：Gateway 在 NAT 后面，不应被 IM 主动调用，正确模型应为 Gateway 主动保持 WebSocket，接收 `config.sync` 通知后再从 IM HTTP API 拉取最新配置。

## Decision
不新增 Gateway HTTP 配置入口；改为在 `src/personal_assistant/main.py` 的 `_IMConfigSyncClient.sync_agent` 内，在拉取并 `register_agent()` 后调用 `save_local_config()`，把 agent 完整配置落盘到本地 `config.yaml`。

## Evidence
### Code
- `src/personal_assistant/main.py`
  - `_IMConfigSyncClient` 新增 `local_config` 持有与 `_persist_agent_config()`
  - `sync_agent()` 现在会把 `skills` / `tool_allowlist` / `system_prompt` / `group_reply_policy` / `default_model` 一起转成 `AgentWorkspaceConfig`
  - `build_runtime()` 传入 `local_config=config`
- `tests/unit/personal_assistant/test_main.py`
  - 更新既有 sync tests
  - 新增 `test_im_config_sync_client_persists_agent_config_to_local_yaml`
- `docs/Gateway配置归位整改计划.md`
  - 已同步修正阶段 B 的架构描述

### Tests
- `python -m pytest tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_gateway_pipeline.py -q`
- 结果：`56 passed`

## Commits
- `f1afa1c feat(M227): persist synced agent config locally`

## Notes
这次提交实际还带入了仓库里此前已暂存的其他文件，不是纯净的 M227-only commit；但 M227 本身的代码与测试已经包含在该提交内。
