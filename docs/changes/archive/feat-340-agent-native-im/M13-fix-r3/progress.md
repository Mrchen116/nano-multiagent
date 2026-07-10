# feat-340-M13 — Progress

## R1 — 红测试:HTTP 入口 + repository 单测

- Context: 新建含无主 agent(owner_id='')的群聊 → POST 201 成功,但 GET /im/v1/conversations 返回空列表。根因:create_conversation 路由 `del user` 丢弃 caller 身份;repository 在 multi-owner participants 时 `uuid4().hex` 作为 conversation owner_id,导致 list_conversations_for_owner 查不到。
- Decision: 先写失败测试覆盖两个层次:HTTP 入口(test_group_with_agent_appears_in_sidebar)+ repository 单测(test_create_group_conversation_owner_id_uses_caller)。同时补跨租户隔离测试。
- Rationale: HTTP 入口测试证明用户真实操作路径;repository 单测精确定位 owner_id 写入逻辑。
- Evidence:
  - Tests: pytest 2 new FAIL (red confirmed) ✓
  - Entry: test_group_with_agent_appears_in_sidebar 向真实 TestClient 发 POST + GET,断言 GET 返回为空(bug 复现)
- Rollback: git revert c3fa2ab5
- Commits: C1=c3fa2ab5

## R2 — 实现:caller_owner_id 穿透 routes → service → repository

- Context: 三处改动:route 去掉 `del user`,service 新增 caller_owner_id 参数,repository 在 caller 提供时直接用其 owner_id 而非 uuid4。
- Decision: 当 `caller_owner_id is not None` 直接采用;单 owner 时用 owner 自身;多 owner 且无 caller 时保留原 uuid4 fallback(维持老测试兼容)。
- Rationale: 强制 caller 必须提供 caller_owner_id 会破坏大量现有 repository 单测(这些测试直接绕过 HTTP 层创建跨-owner 对话)。fallback 路径不是新暴露的 bug,不在本 milestone 修复范围。
- Evidence:
  - Tests: pytest tests/im_service/ (ignore m103/m136) → 203 passed ✓; vitest 238 passed ✓; tsc -b 无错误 ✓
  - Entry: test_group_with_agent_appears_in_sidebar PASS — POST 201 → GET 返回含该会话 ✓
- Rollback: git revert 6df03f00
- Commits: C2=6df03f00
- Next: C3 文档收尾后合并到 unit 分支
