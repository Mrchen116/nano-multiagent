# bugfix-369-M1: 修复门禁分类器继承主 agent thinking

## 目标

auto_mode_gate 的 stage-1 / stage-2 call_model 调用显式关闭 thinking，使 stage-1 能在 64 token 内正常吐 `<block>`，主 agent 循环不受影响。

## 退出标准

1. `_classify_action` 的两个 `call_model` 调用都携带 `extra_body={"thinking": {"type": "disabled"}}`
2. 单元测试覆盖："门禁分类调用不带 thinking"（确认传出的 `HookModelCall.extra_body` 含 disable thinking）
3. 单元测试覆盖："stage-1 在 64 token 内能出 `<block>`"（mock 掉 thinking 时能正常 parse）
4. `pytest tests/unit/test_auto_mode_gate.py tests/unit/test_llm_model_registry.py` 全绿

## 测试策略

本 bug 是纯后端逻辑缺陷。测试方式：
- 在 `test_auto_mode_gate.py` 补充新 case，mock `ctx.call_model` 验证传入的 extra_body
- 验证 `_classify_action` 在 stage-1 能正常 parse `<block>` 时走快路

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | C1 红测：验证 extra_body 不传时 parse 失败的 regression + 验证传 disabled 后 parse 成功 | DONE |
| R2 | C2 实现：打通 HookModelCall → call_model → runtime → classify_action extra_body 链路 | DONE |
| R3 | C3 文档：tasks/progress 补全 + fix.md 回填 | DONE |
