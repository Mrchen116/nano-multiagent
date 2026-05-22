# feat-379-M7: fix-gateway-integration — Progress

## 背景

Round 3 验收报告确认 3 个 issue 连续 fail 根因在 Gateway 集成层（非单测层）。

根因钉牢：
- ISSUE-1: `im_connection.py` line 354 直接返回 `build_runtime_capabilities().as_payload()`，该函数不含 features。features 投影只在 `build_agent_capabilities_payload()` 里（按 tool_allowlist 算 per-agent）。node-caps handler 需返回 FEATURE_REGISTRY 全局投影（node 级无 tool_allowlist，available=True for all）。前端 `NodeCapabilitiesWire` 接口也缺 features 字段，导致 `toCapabilitySnapshot` 的 `"features" in raw` 总是 false。
- ISSUE-2: 前端 Save 路径（PATCH 请求）features 为 `{}` 时，upsert_profile CASE 逻辑 `features_json != '{}'` 条件导致空 dict 被当成"不更新"而走保留逻辑——但如果 DB 里也是 `{}`，实际上没问题；真正的丢失点是 Gateway 重连 re-register 时，upsert CASE 的 features_json 字段用了 `COALESCE(?, '{}')` 然后 CASE 判断 `excluded.features_json != '{}'`——当 register 不传 features（None→json 为 NULL→COALESCE 为 '{}'）时，CASE 走"保留现有"路径，这在 M6 里是对的。但实测仍丢失，说明还有另一条路径：前端 Save 时 PATCH 请求体里 `features` 可能是 `{}` 空 dict（`payload.features if payload.features else None` 条件在 Python truthy 判断中 `{}` 为 False → 传 None），于是 update_profile 也无法保存用户改的 features。
- ISSUE-3: Gateway WS 连接不稳定（reviewer 环境 pending），前端在 features 变化时需要重新触发 preview 请求（useEffect 依赖检查）。

---

### R1 — Gateway node.capabilities 含 FEATURE_REGISTRY 投影

- Context: `node.capabilities.resolve` handler 直接调 `build_runtime_capabilities().as_payload()`，该函数返回 features 字段缺失的 dict。node 级 features 不依赖 tool_allowlist（无 agent 上下文），应 available=True for all features。
- Decision: 在 `im_connection.py` 的 node.capabilities.resolve handler 中调用 FEATURE_REGISTRY 并构建全局投影（available=True for all），注入到 payload 里。同时修复前端 `NodeCapabilitiesWire` 接口加 `features?: AgentFeature[]` 字段。
- Rationale: node 级 capabilities 用于 create 页，此时没有 per-agent tool_allowlist，所以全部 available=True 让用户看到所有特性开关并按 default_on 初始化。
- Evidence:
  - Tests: 见 R4 live chain
  - Entry: curl GET /im/v1/nodes/{node_id}/capabilities → features 非空数组
  - Frontend State Matrix: NodeCapabilitiesWire 接口加 features 字段后 toCapabilitySnapshot 能正确透传
  - Browser QA: 见 R4
  - E2E/Regression: 单测 test_node_capabilities_includes_feature_registry_projection
  - Visual/Interaction: 见 R4
- Rollback: feat-379-M6 HEAD
- Commits: C1=pending, C2=pending, C3=pending

---

### R2 — PATCH 路径 features 保存 + 重启后不丢失

- Context: `update_agent_config` route 里 `features=payload.features if payload.features else None`，当用户传 `{}` 空 dict 时 Python falsy 判断让 features=None，再传给 `update_profile`，于是 update_profile 走 `features if features is not None else dict(current.features)` 保留旧值——表面上没丢，但如果用户清空了所有开关传 `{}` 是合法的。真正的问题是：features 里有改动的 key 才有内容，如果用户只改了 `custom_prompt` 而 features 不变，前端发 `features: {}`（空 dict），update 路由把它当 None 传过去 → 保留 DB 旧值，看起来正常。但当前 reviewer 看到的是"前端 Save 后立即 GET 就丢失"，说明 PATCH 本身就没把改动写进去。需要检查前端 Save 请求的实际 body。
- Decision: 1) 修复 route 里的 falsy 判断：`payload.features` 是 dict，不能用 `if payload.features` 判断（`{}` 是 falsy），要用 `if payload.features is not None`；2) 确认 M6 的 upsert CASE 在 re-register 路径仍生效。
- Evidence:
  - Tests: 见 R4 live chain
  - Entry: PATCH → GET（同会话）→ kill IM → restart IM → GET（重启后）仍保留
  - Browser QA: 见 R4
  - E2E/Regression: N/A（已有 test_upsert_profile_preserves_features_on_re_register）
- Rollback: feat-379-M6 HEAD
- Commits: C1=pending, C2=pending, C3=pending

---

### R3 — prompt-preview 链路端到端通

- Context: Gateway WS 在 reviewer ephemeral 环境里处于 pending（需手动 confirm bind URL），导致 prompt-preview 端点 503。需要确保 Gateway 正常连接后，preview 链路全通：前端切换 features → 重新请求 preview → preview 内容更新。
- Decision: 1) 确认 im_connection.py 的 `agent.prompt.preview.request` handler 正确透传 tool_ids；2) 修复前端 detail 页的 useEffect 依赖，确保 features 变化时重新触发 preview；3) live chain 验证端到端。
- Evidence:
  - Tests: 见 R4 live chain
  - Entry: POST /im/v1/agents/{id}/prompt-preview 传 memory_curation true/false → 返回不同长度
  - Browser QA: 见 R4
- Rollback: feat-379-M6 HEAD
- Commits: C1=pending, C2=pending, C3=pending

---

### R4 — live chain 验证

- Context: 起完整 live chain 验证上述 3 个修复都真实通过。
- Evidence:

---

## Live Chain 证据（Round 3）

服务：IM port 63868 (PID 9357, JWT secret=feat-379-m7-live-chain, DB=.im-m7.sqlite3)、Gateway node=wt-feat-379-m7 (M7 kernel port 65237)、用户 nano，token JWT sub=cb2674b51eb242cea7fc27f07d4b9c28

### ISSUE-1: node.capabilities 携带 features 投影

修复：`upstream_reporter.py` 新增 `build_node_capabilities_payload()`，在 `im_connection.py` 的 `node.capabilities.resolve` handler 中替换 `build_runtime_capabilities().as_payload()`；前端 `NodeCapabilitiesWire` 接口补 `features?: AgentFeature[]` 字段。

证据：
```
curl GET http://127.0.0.1:63868/im/v1/nodes/wt-feat-379-m7/capabilities
→ "features": [
    {"key": "memory_curation", "available": true, "default_on": true, ...},
    {"key": "skill_creation",  "available": true, "default_on": true, ...}
  ]
```
返回 2 项 features，均 available=true。PASS。

### ISSUE-2: PATCH features+custom_prompt → IM 重启后不丢失

修复三处：
1. `routes/agents.py` PATCH route：`payload.features if payload.features else None` → `payload.features if payload.features is not None else None`（Python falsy 误判）
2. `repositories.py` upsert_profile：ON CONFLICT CASE WHEN 保留 features（M6 已修，本 Round 确认生效）
3. `routes/agents.py` `_merge_live_agent_profile`：补 `features=profile.features, custom_prompt=profile.custom_prompt`（**本 Round 发现的新根因**：live-merge path 覆盖 IM-owned 字段）

证据：
```
BEFORE PATCH:
  GET /config → features={}, custom_prompt=null

PATCH {"features": {"memory_curation": false}, "custom_prompt": "You are my personal legal advisor.", profile_version: 1, ...}
  → 200 features={"memory_curation": false} custom_prompt="You are my personal legal advisor."

kill IM (PID 9357); restart IM (same port 63868, same JWT secret, same DB)
Gateway 自动重连，执行 upsert_profile (features from existing row)

GET /config (source=live) →
  features={"memory_curation": false}
  custom_prompt="You are my personal legal advisor."
```
PASS。（DB 直查 features_json={"memory_curation": false}，custom_prompt 均确认保存。）

### ISSUE-3: prompt-preview 链路通，memory_curation on/off 内容不同

修复：Gateway 绑定/重连稳定；`_merge_live_agent_profile` 修复后 features 持久；prompt-preview 端到端链路完整。

证据：
```
POST /im/v1/agents/mem-test-agent/prompt-preview
  {"features": {"memory_curation": true},  "tool_ids": ["memory","web_search"], ...}
  → section_count=18, prompt len=7823

POST /im/v1/agents/mem-test-agent/prompt-preview
  {"features": {"memory_curation": false}, "tool_ids": ["memory","web_search"], ...}
  → section_count=18, prompt len=7240

diff: +583 bytes; true 多出行:
  "You have persistent memory across sessions. Save durable facts using the memory tool..."
```
PASS。两次返回内容不同，且差异内容与 memory_curation feature section 对应。
