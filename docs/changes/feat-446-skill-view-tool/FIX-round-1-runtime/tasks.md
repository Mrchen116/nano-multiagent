# FIX-round-1-runtime — tasks

## 目标

修复 reviewer round 1 中归属后端/runtime 的问题：自动 compaction skill reinjection、F4 batch review production drain、skill prompt allowlist gating、usage owning root 归属，以及 backend code-review nits。

## 退出标准

- Threshold 与 overflow compaction 在真实 runtime run 路径都会把本 session 已 view 的 skill 以 `<system-reminder>` 重新注入；skill 文件删除/移动时 compaction 不失败。
- `skill_view` 越过 F4 阈值后，queued batch review 会通过 Gateway 或 CLI 产品入口被 drain。
- 当 active tool allowlist 不含 `skill_view` 时，`<available_skills>` 不再提示模型调用 `skill_view`。
- 同名/priority-hit skill usage 写入命中 skill 所属 root，避免 PA/shared skill 被记到 agent-local sidecar。
- 指定 backend/code-review fixes 已修复或在 progress 中记录 disposition。

## 测试策略

- 被测行为：上述退出标准逐条覆盖。
- 已有测试在：
  - `tests/integration/test_compaction_runtime_integration.py` 扩展 threshold/overflow runtime compaction 回归。
  - `tests/unit/test_skill_view.py`、`tests/unit/test_usage.py` 扩展 owning root/usage 行为。
  - `tests/unit/test_agent_prompting.py` 或 `tests/unit/agent/test_core_sections.py` 扩展 prompt allowlist gating。
  - `tests/unit/test_skill_batch_review.py`、`tests/unit/personal_assistant/test_gateway_im_connection_behavior.py` 扩展 F4 drain/housekeeping路径。
  - `tests/im_service/unit/test_repositories_user_conversation.py` 扩展 JSONL session source resolution。
- 落层/目录/marker：unit + integration；无 e2e marker。真实长驻服务不纳入永久测试。
- 可选依赖 importorskip：无。
- 一次性验收证据：backend/runtime slice 不涉及浏览器；以 integration/product-entrypoint tests 作为入口证据。

## Roadpoints

| ID | 状态 | 内容 | 验证 |
|---|---|---|---|
| R1 | TODO | Runtime compaction reinjection + prompt gating + usage owning root | `PYTHONPATH=src pytest tests/integration/test_compaction_runtime_integration.py tests/unit/test_skill_view.py tests/unit/test_agent_prompting.py tests/unit/agent/test_core_sections.py -x` |
| R2 | TODO | F4 batch review product drain + backend review nits | `PYTHONPATH=src pytest tests/unit/test_skill_batch_review.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/unit/test_repositories_user_conversation.py tests/im_service/integration/test_agent_config_api.py -x` |
| R3 | TODO | Final narrow gates, docs/progress, merge readiness | `PYTHONPATH=src pytest tests/unit/test_skill_view.py tests/unit/test_usage.py tests/unit/test_skill_batch_review.py tests/integration/test_compaction_runtime_integration.py tests/unit/test_agent_prompting.py tests/unit/agent/test_core_sections.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/unit/test_repositories_user_conversation.py tests/im_service/integration/test_agent_config_api.py tests/contract/test_core_no_platform_imports.py -x` |
