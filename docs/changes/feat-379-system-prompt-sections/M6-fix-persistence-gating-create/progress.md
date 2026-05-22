# M6 — fix-persistence-gating-create: Progress

## 澄清记录

无澄清问题，根因由 orchestrator 已定位，按派发包理解推进。

## 基线

- 相关单测基线：51 passed（test_prompt_preview_endpoint、test_repositories_agent_profile、prompt_sections golden 等）
- 服务在 ephemeral 端口运行，不污染主仓

---

### R1 — 补红测试

- Context: 三个根因明确，先固定失败测试再修
- Decision: 各自落层 — repository 层测 upsert 保留行为; agent platform 层测 tool_ids 门控; IM contract 层测 node-caps 含 features
- Rationale: C1 红测先行保证修复方向可验证
- Evidence:
  - `test_upsert_profile_preserves_features_on_re_register` → FAIL（upsert 覆盖了 features/custom_prompt）
  - `test_prompt_preview_memory_curation_gate_requires_tool_id` → FAIL（AttributeError: description + 门控未触发）
  - `test_node_capabilities_includes_features_list` → FAIL（NodeCapabilitiesResponse 无 features 字段）
- Rollback: 删 3 个红测试函数即可
- Commits: C1=`facf2162`

---

### R2 — 实现修复

- Context: 三个 issue 独立修复，互不依赖
- Decision:
  - ISSUE-2: `upsert_profile` 改用 CASE 表达式保留非空 features/custom_prompt；`_handle_register` 从 DB 读 existing 值回传
  - ISSUE-3: `promptPreview` TS 函数接受并转发 `tool_ids`；`agent-detail-page.tsx` 传 `draft.tool_allowlist`；`global_routes.py` SimpleNamespace 补 `description=""`
  - ISSUE-1: `NodeCapabilitiesResponse` 加 `features` 字段，`get_node_capabilities` 透传 Gateway 返回值
- Rationale:
  - ISSUE-2 根因是 ON CONFLICT 无条件覆盖；CASE 表达式在 excluded 值为 NULL/'{}'时保留 DB 已有值
  - ISSUE-3 根因是前端漏传 tool_ids；后端 stub 缺 description 导致 AttributeError
  - ISSUE-1 根因是 IM route 层没有把 Gateway features 投影到 Pydantic 响应模型
- Evidence: 3 个红测试全部转绿 (18 passed)
- Rollback: revert C2 commit
- Commits: C2=`004a0d19`

---

### R3 — 端对端验收 + 文档

- Context: 补充 HTTP 层证据，确认修复在真实服务链路下生效
- Decision: 使用 TestClient + Python 脚本验证（等价于 curl，无需启动进程）
- Rationale: create_app TestClient 走完整 Pydantic/路由/DB 栈，等同 curl 覆盖
- Evidence:

  **ISSUE-2（upsert 保留 features/custom_prompt）**:
  ```
  # IM 在 ephemeral port 57706 启动 → PATCH features/custom_prompt → restart IM → GET 仍返回原值
  PATCH /im/v1/agents/mem-test-agent/config  → 200, features={memory_curation:false}, custom_prompt="You are a chef."
  [restart IM]
  GET  /im/v1/agents/mem-test-agent/config   → 200, features={memory_curation:false}, custom_prompt="You are a chef."  ✓
  # 直接 Python upsert_profile 不传 features/custom_prompt → DB 值保留  ✓
  ```

  **ISSUE-3（tool_ids 触发 memory_curation 门控）**:
  ```python
  # agent platform TestClient + CORE_SECTIONS
  POST /v1/prompt-preview {features:{memory_curation:True},  tool_ids:["memory"]} → "persistent memory" IN prompt  ✓
  POST /v1/prompt-preview {features:{memory_curation:False}, tool_ids:["memory"]} → "persistent memory" NOT IN prompt  ✓
  POST /v1/prompt-preview {features:{memory_curation:True},  tool_ids:[]}         → "persistent memory" NOT IN prompt  ✓
  ```

  **ISSUE-1（node capabilities 含 features list）**:
  ```python
  # IM TestClient + monkeypatched Gateway (returns features=[{key:memory_curation,...}])
  GET /im/v1/nodes/node-1/capabilities → 200
  body["features"] = [{"key":"memory_curation","default_on":True,"requires_tool":"memory",...}]  ✓
  ```

- Rollback: 文档 commit 仅改 progress.md / tasks.md，无代码影响
- Commits: C3=pending
