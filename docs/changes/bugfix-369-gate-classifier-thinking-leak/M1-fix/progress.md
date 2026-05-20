# bugfix-369-M1 progress

## R1 — C1 红测

- Context: 门禁 call_model 没有 extra_body 参数，无法覆盖模型级 thinking；需要先写失败测试确认 invariant
- Decision: 在 test_auto_mode_gate.py 补两个 case：
  1. `test_classify_action_stage1_extra_body_disables_thinking`：assert call_model 被调用时 extra_body 含 thinking disabled
  2. `test_classify_action_stage1_parse_failure_when_content_empty`：验证 content 为空时 parse 返回 None（regression）
- Rationale: 这两个 case 确保 invariant "门禁分类调用携带 thinking off + stage-1 正常快路"
- Evidence: (pending)
- Rollback: (pending)
- Commits: C1=pending, C2=pending, C3=pending
- Next: 写 C1 红测试
