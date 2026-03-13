# M150 - 修复 Agent 配置变更污染旧直聊会话

## 结论
已完成代码修复与自动化回归，恢复“配置变更仅影响新直聊会话”的隔离语义，同时保留 M147/M148 动态同步能力。

## 已实施改动
- `src/personal_assistant/gateway/session_keys.py`
  - 直聊 session key 从用户级切换为会话级：使用 `external_chat_id` 而不是 `external_user_id`。
- `src/personal_assistant/gateway/inbound_pipeline.py`
  - `register_agent()` 不再在配置同步时清空该 Agent 的全部 session binding，仅更新未来会话使用的 agent 配置。
- `tests/unit/personal_assistant/test_gateway_pipeline.py`
  - 更新旧断言，新增旧会话/新会话分流回归。
- `tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - 新增 IM -> Gateway 直聊回归，验证旧 conversation 继续使用旧 kernel session，新 conversation 使用新 kernel session 与新 profile/system_prompt。

## 证据
### 先失败的测试
- `tests/unit/personal_assistant/test_gateway_pipeline.py`
  - 在修复前出现 3 个失败：
    - 直聊 session key 仍为 `web:user-1:agent-a`
    - pipeline 结果中的直聊 session key 未按 conversation 分隔
    - `register_agent()` 后旧直聊会话被重建到 `sess-2`

### 修复后通过的聚焦回归
- `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_main.py`
- `PYTHONPATH=src pytest -q tests/im_service/integration/test_m103_im_gateway_e2e.py`

### 指定门禁
- 待本文件最后更新后运行：
  - `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_m102_gateway_im_connection.py tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_m103_im_gateway_e2e.py`

## 兼容性说明
- M147/M148 的 config.sync 仍然触发 live agent registry 更新。
- 新会话无需 Gateway 重启或 node-config 改动，即可使用更新后的 workspace/title 与 IM 下发的新 prompt/profile。
- 旧会话继续绑定旧 kernel session，因此其 reply context 也保持原绑定快照；本里程碑未改变该既有行为。

## 风险
- 旧会话 reply context 的元数据仍沿用首次绑定快照；当前不影响“旧会话保持原行为”的目标，但若后续产品要求旧会话复用旧内核同时更新外层投递元数据，需要单独里程碑处理。

## 回滚点
- 回滚本里程碑时，恢复下列文件到前一版本即可：
  - `src/personal_assistant/gateway/session_keys.py`
  - `src/personal_assistant/gateway/inbound_pipeline.py`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`
