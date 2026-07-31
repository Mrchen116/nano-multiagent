# M150 - 修复 Agent 配置变更污染旧直聊会话

## 背景
- `docs/需求.md` 要求：配置变更仅对新会话生效，已开始的会话保持原行为。
- 真实验收暴露缺陷：旧直聊会话在 Agent prompt/config 更新后发生漂移，后续消息命中了新配置。

## 实际缺口
1. `src/personal_assistant/gateway/session_keys.py` 直聊 session key 仅由 `channel + external_user_id + agent_id` 组成，无法区分同一用户与同一 Agent 下的不同直聊会话。
2. `src/personal_assistant/gateway/inbound_pipeline.py` 的 `register_agent()` 在收到动态配置同步后调用 `session_store.drop_agent(agent_id)`，导致该 Agent 的旧会话绑定被整体清空，旧会话下一条消息会重新建 kernel session 并拾取新配置。

## 设计
- 将直聊 session key 改为与群聊一致的会话级作用域：`{channel}:{external_chat_id}:{agent_id}`。
- `register_agent()` 只更新未来建会话时使用的 agent workspace/title，不再主动清空已存在的 session binding。
- 保持已有动态同步能力：新会话在 config.sync 后仍会使用更新后的 workspace/title 与 IM 侧下发的最新 `config_profile_version/system_prompt`。

## TDD 计划
1. 先修改/新增单元测试，固定以下行为：
   - 直聊 key 按 `external_chat_id` 分隔。
   - 旧直聊会话在 `register_agent()` 后继续复用旧 kernel session。
   - 新直聊会话在 `register_agent()` 后使用新 workspace 并新建 kernel session。
2. 再增加 IM ↔ Gateway 集成回归：
   - 旧 conversation 在 config sync 后继续命中原 kernel session。
   - 新 conversation 在同一 sync 后命中新 kernel session 与新 profile/system_prompt。
3. 最后运行 M150 指定门禁。

## 回滚点
- 如需回滚，仅撤销本里程碑对以下文件的改动：
  - `src/personal_assistant/gateway/session_keys.py`
  - `src/personal_assistant/gateway/inbound_pipeline.py`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`
