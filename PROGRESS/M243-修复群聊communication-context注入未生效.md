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
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

---

### R2 — 修复 before_agent_start 对真实 system prompt 的追加，并完成真实日志验证
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
