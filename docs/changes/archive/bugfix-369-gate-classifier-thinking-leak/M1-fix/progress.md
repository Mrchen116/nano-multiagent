# bugfix-369-M1 progress

## R1 — C1 红测 + C2 实现 + C3 文档

- Context: `_classify_action` 调用 `ctx.call_model` 无 `extra_body` 参数，无法覆盖模型元数据 thinking；stage-1 64-token 被 reasoning 吃空 → content 空 → fail-closed → ask → 整轮卡住
- Decision:
  1. `HookModelCall` 加 `extra_body` 字段
  2. `HookContext.call_model()` 透传 `extra_body`
  3. `runtime._call_hook_model` 透传到 `LLMGenerateRequest.extra_body`
  4. `_classify_action` stage-1 / stage-2 均传 `extra_body={"thinking": {"type": "disabled"}}`
- Rationale: `LLMGenerateRequest.extra_body` 和 `AnthropicClient.generate()` 的 call 端覆盖逻辑早已存在，只需打通上层调用链。`"disabled"` 是与 `"adaptive"` 对称的关 thinking 取值。
- Evidence:
  - Tests: `pytest tests/unit/test_auto_mode_gate.py -q` → 62 passed（含 3 个新 regression case）
  - Entry: 纯后端逻辑修复，无需浏览器验收；测试直接 mock `ctx.call_model` 验证 extra_body 参数
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 3 个新单元 regression case 在 `tests/unit/test_auto_mode_gate.py::TestClassifyActionThinkingDisabled`
  - Visual/Interaction: N/A
- Rollback: 回退到 C1 前（origin/unit/bugfix-369，`94fac595`）
- Commits: C1=`6a67920e`, C2=`00f94d77`, C3=pending
- Next: C3 文档 commit → 集成到 unit/bugfix-369
