# PROGRESS — M243 修复群聊 communication context 注入未生效

## 概况

- Milestone: M243
- Branch: main
- Worktree: none（按要求直接在主仓执行）
- test_command: `pytest tests/unit/test_product_profiles.py tests/unit/personal_assistant/test_gateway_pipeline.py tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_m136_group_chat_flow.py tests/im_service/integration/test_m103_im_gateway_e2e.py && if command -v uv >/dev/null 2>&1; then uv run pytest tests/unit/test_product_profiles.py tests/unit/personal_assistant/test_gateway_pipeline.py tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_m136_group_chat_flow.py tests/im_service/integration/test_m103_im_gateway_e2e.py; fi`
- Prevention rules applied:
  - 先对齐 `docs/NodeGateway-SPEC.md` 中群聊行为与 communication context 约束
  - hook 加载按模块 stem 过滤，不能依赖 `__init__`
  - hook 加载验证断言关键模块，不写死总数
  - 直接在主仓执行，不创建/进入 worktree
- Baseline:
  - 定向 pytest 在 `tests/im_service/integration/test_m136_group_chat_flow.py` 卡住
  - 根因待确认；初步怀疑集成测试仍按旧单 relay / 自动回执假设编写，与当前 group relay / receipt 行为不一致

---

### R1 — 修复 hook 加载与群聊 metadata 透传回归
- Context:
  - 现网群聊链路的 communication context 没进最终 system prompt，前半段问题在于 product hook 默认模块与群聊 relay/session metadata 透传没有同时对齐。
  - `bootstrap_product` 只按 hook 模块文件 stem 过滤，不能依赖 `hooks/__init__.py` 被当作 hook 模块加载。
- Decision:
  - 将 `DEFAULT_HOOK_MODULES` 收口到 `src/agent/products/personal_assistant/hooks/communication_context.py`，让 bootstrap 按真实 stem `communication_context` 保留该 hook。
  - IM relay 在 group chat payload.metadata 中补齐 `participant_agent_ids`；Gateway session metadata 优先透传 `participant_agent_ids`，仅在缺失时回退 `mentioned_agent_ids`。
  - 同步修正 `tests/im_service/integration/test_m103_im_gateway_e2e.py`，使其消费真实 group fan-out relay，并接受 direct session metadata 现在显式包含 `conversation_type`。
- Rationale:
  - 问题不只是一处字段缺失，而是“hook 是否被保留 + relay 是否带真参与者 + Gateway 是否沿用真参与者”三段一起漂移；必须同时收口到真实生产契约。
- Evidence:
  - Tests: `pytest tests/unit/test_product_profiles.py tests/unit/personal_assistant/test_gateway_pipeline.py tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_m136_group_chat_flow.py tests/im_service/integration/test_m103_im_gateway_e2e.py` 全绿；`uv run pytest ...` 同样 59 passed。
  - Entry: `tests/unit/test_product_profiles.py` 断言 bootstrap 后 registry 含 `communication_context`；`tests/im_service/unit/test_relay_service.py` / `tests/unit/personal_assistant/test_gateway_pipeline.py` / `tests/im_service/integration/test_m103_im_gateway_e2e.py` 断言 group relay 与 kernel session metadata 都带 `participant_agent_ids`。
- Rollback:
  - 回退到本次续跑前的主仓工作树即可；本轮未创建 git 提交。
- Commits: C1=未创建（主仓续跑）, C2=未创建（主仓续跑）, C3=未创建（主仓续跑）
- Next:
  - 进入 R2，验证 before_agent_start 会在真实 production prompt 上追加 communication context，并用 fresh runtime 的真实请求日志留证。

---

### R2 — 修复 before_agent_start 对真实 system prompt 的追加，并完成真实日志验证
- Context:
  - 仅修复 metadata 透传还不够；若 `before_agent_start` 在 payload 未带 `system_prompt` 时直接写入 context block，会把产品级 base prompt 覆盖掉，仍不符合 SPEC 的“追加到系统提示词后”。
  - 现有 M103 集成测试仍带旧单 relay 假设，group fan-out 后会在 delivery_receipt 之间插入 peer background relay，测试需先对齐真实时序，才能作为回归门禁。
- Decision:
  - `src/agent/products/personal_assistant/hooks/communication_context.py` 在 payload 缺 base prompt 时，改从 `ctx.metadata["system_prompt"]` 回填真实 session prompt，再把 `[Communication Context]` block 追加到其后。
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py` 为 group fan-out 增加 `_receive_group_relays` 和可跳过中途 `relay.message` 的 receipt helper，显式验证 addressed relay、peer background relay、以及 `NO_REPLY` 时不广播 peer context 的现网行为。
  - 使用 `/tmp/m243-validation/run_validation.py` 启动 fresh mock openai_compat(4100) + fresh IM(8111) + fresh Gateway/kernel(8100)，真实创建 group conversation 并发送 `@agent-a` 消息，直接抓取 mock LLM 收到的最终 system prompt。
- Rationale:
  - 只有让 hook 从 session metadata 取回真实 base prompt，才能保证最终 prompt 同时保留产品模板和 communication context；再用 fresh 真实链路抓上游 LLM 请求，才能证明问题在生产路径已闭环修复。
- Evidence:
  - Tests: `pytest tests/unit/test_product_profiles.py tests/unit/personal_assistant/test_gateway_pipeline.py tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_m136_group_chat_flow.py tests/im_service/integration/test_m103_im_gateway_e2e.py` 全绿；`uv run pytest tests/unit/test_product_profiles.py tests/unit/personal_assistant/test_gateway_pipeline.py tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_m136_group_chat_flow.py tests/im_service/integration/test_m103_im_gateway_e2e.py` 全绿。
  - Entry: 历史验证脚本 `PYTHONPATH="/Users/czj/Repos/nano-multiagent/src:/tmp/m243-validation" python /tmp/m243-validation/run_validation.py` 曾产出 `/tmp/m243-validation/logs/validation_result.json`，其中四项 contains 全为 true。
  - Fresh rerun: 2026-03-19 重新启动 fresh mock LLM + IM(8111) + Gateway/kernel(8100) 后，先通过 `/im/v1/bind` 显式完成 node 绑定，再发送新的群聊消息；产物 `/tmp/m243-validation/logs/final_system_prompt.txt` 与 `/tmp/m243-validation/logs/manual_validation_result.json` 再次确认同时包含 `# Nano Personal Assistant`、`[Communication Context]`、`your_agent_id: agent-a`、`group_participants: agent-a, agent-b`。
- Rollback:
  - 回退到本次续跑前的主仓工作树即可；本轮未创建 git 提交。真实验证脚本与日志位于 `/tmp/m243-validation/`，删除该目录即可清理验证环境。
- Commits: C1=未创建（主仓续跑）, C2=未创建（主仓续跑）, C3=未创建（主仓续跑）
- Next:
  - M243 可标记 DONE；后续若复查，只需重跑 `/tmp/m243-validation/run_validation.py` 并核对 `/tmp/m243-validation/logs/final_system_prompt.txt`。
