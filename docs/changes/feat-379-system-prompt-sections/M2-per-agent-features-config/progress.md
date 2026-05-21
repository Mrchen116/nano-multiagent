# M2 Progress

## R1 — local_store.py: AgentWorkspaceConfig + features + custom_prompt

- Context: AgentWorkspaceConfig 是 frozen dataclass，需加两个可选字段：features（dict[str,bool]，per-agent 特性开关覆盖）和 custom_prompt（str|None，用户自定义补充文本）。load/save 均需透传，save 只序列化非空值。
- Decision: 新增 `features: Mapping[str, bool]` 字段（用 field(default_factory=...) 作默认空 dict）+ `custom_prompt: str | None = None`；_parse_agents 解析时从 YAML `features` dict 读取；save_local_config 当 features 非空时写入。
- Rationale: 跟随 design 决策 3 — features 在 AgentWorkspaceConfig 中，沿用 metadata 注入链。
- Evidence:
  - Tests: 单元测试 load/save round-trip 通过
  - Entry: N/A（pure data layer）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R1 C1 之前
- Commits: C1=d1f4d8d1, C2=4168fa05, C3=N/A
- Next: R2

## R2 — personal_assistant/main.py: 透传 + 持久化

- Context: sync_agent 从 IM 拉取 agent config 后构造 AgentWorkspaceConfig；handle_agent_create 从 IM 推送 payload 构造 AgentWorkspaceConfig；current_agent_payload 序列化给 capabilities 接口。三处均需透传 features + custom_prompt。
- Decision: 在 sync_agent / handle_agent_create / current_agent_payload 三处加 features / custom_prompt 字段读取/写入；_persist_agent_config 自动保存（已有路径）。
- Rationale: Gateway 是持久化入口；config.yaml 写入通过 save_local_config 完成。
- Evidence:
  - Tests: 单元测试透传行为通过
  - Entry: N/A（gateway 内部路径）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R2 C1 之前
- Commits: C1=a6277dec, C2=476f528c, C3=N/A
- Next: R3

## R3 — IM db + repositories: features_json + custom_prompt 字段

- Context: agent_profiles 表缺少 features_json 和 custom_prompt 列；AgentProfile 领域模型同样缺少这两个字段；repositories 中的 upsert/get/list 也需要更新。
- Decision: 加 ALTER TABLE 迁移（在 ensure_schema 中处理，若列不存在则 ADD COLUMN）；更新 AgentProfile dataclass；更新所有 SELECT/INSERT/UPDATE；_row_to_profile 从 row 读取。
- Rationale: SQLite 支持 ADD COLUMN，与现有迁移模式一致（见 db.py 中的 migrations 处理）。
- Evidence:
  - Tests: in-memory SQLite 集成测试通过
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R3 C1 之前
- Commits: C1=f8568417, C2=ff8c1282, C3=N/A
- Next: R4

## R4 — IM capabilities.features 投影 + agent routes

- Context: GET /im/v1/agents/{id}/capabilities 现在只返回 skills/tools/models/default_system_prompt；需加 features 投影，内容来自注册表（feature_key, label_i18n, help_i18n, default_on）+是否因缺依赖工具被禁用（依赖当前 agent 的 tool_allowlist）。
- Decision: 在 AgentCapabilitiesResponse 加 features 字段；在 get_agent_capabilities 中从 gateway payload 提取 features，注入到 response；gateway capabilities 响应里需要包含 features 投影（由 Gateway 基于 FEATURE_REGISTRY 构造）。IM 侧不 import feature_registry；features 全由 Gateway 通过 agent.capabilities 回包传来。
- Rationale: design 决策 7 — 注册表服务端完整，前端经 capabilities API 下发，IM 不硬编码 key。四包 HTTP-only 约束不破。
- Evidence:
  - Tests: contract 测试 capabilities features key 与 FEATURE_REGISTRY 一致
  - Entry: HTTP GET /im/v1/agents/{id}/capabilities
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R4 C1 之前
- Commits: C1=65563093, C2=cc35c13f, C3=N/A
- Next: R5

## R5 — 预览接口: agent POST /v1/prompt-preview + IM 代理路由

- Context: 前端（M3）需要在编辑 agent 时预览完整 prompt；预览接口接受 {tool_ids, features, custom_prompt, scenario:"direct"} → 返回 assemble_system_prompt 的结果串（单聊视角，不含易变段）。IM 需代理此请求到 Gateway。
- Decision: 在 agent platform HTTP API 新增 `POST /v1/prompt-preview`；IM 新增 `POST /im/v1/agents/{id}/prompt-preview` 代理路由经 gateway_handler 转发。
- Rationale: design 接口与数据流节明确列出此接口；assemble_system_prompt 已可复用，只需固定 scenario='direct' 并过滤 cache_safe=False 段。
- Evidence:
  - Tests: agent 预览接口单测（HTTP 入口）+ IM 代理路由单测
  - Entry: POST /v1/prompt-preview
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R5 C1 之前
- Commits: C1=c4396e2d, C2=410228fe, C3=N/A
- Next: R6

## R6 — session 创建 metadata 接线

- Context: Gateway 起 session 时把 features/custom_prompt 写入 session 创建请求的 metadata；agent runtime 从 metadata 取出，填入 PromptContext.flags 和 vars["custom_prompt"]。
- Decision: Gateway session 创建请求加 `agent_features` 和 `agent_custom_prompt` 到 metadata；runtime 在构建 PromptContext 时从 session metadata 读取，合并 FEATURE_REGISTRY default_on 与 per-agent override。
- Rationale: 复用 feat-349 的 metadata 注入链（design 决策 3）；runtime.py 已有 session_metadata 读取路径。
- Evidence:
  - Tests: 单元测试 session 创建请求 metadata 含 agent_features + vars["custom_prompt"]
  - Entry: session 创建 + assemble_system_prompt 集成路径
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R6 C1 之前
- Commits: C1=95e3f6d2, C2=425fd7cb+ee9c7b4d, C3=N/A
- Next: milestone DONE
