# M2: per-agent-features-config

## 目标

把 per-agent features/custom_prompt 配置端到端打通，让「config.yaml 某 agent 的 features/custom_prompt → session 组装出的 prompt 段相应增减」全链路可测、可持久化；并提供「预览接口」让前端（M3）能在保存前展示完整 prompt 组装结果。

## 退出标准

1. 改 `config.yaml` 某 agent 的 `features`/`custom_prompt` → 该 agent 组装出的 prompt 段相应增减（集成测试，含 golden 或 HTTP 入口验证）
2. 特性开关写后重启 Gateway 仍保持（持久化测试）
3. `GET /im/v1/agents/{id}/capabilities` 返回 `features` 投影且与注册表 key 一致（contract 测试）
4. 预览接口 `POST /v1/prompt-preview` 按给定 features/custom_prompt 返回组装串、单聊场景不含易变段（单测）
5. IM 代理路由 `POST /im/v1/agents/{id}/prompt-preview` 转发到 Gateway（单测或集成）
6. 四包 HTTP-only 依赖方向不破（tests/contract/ 验收）

## 测试策略

- **R1**（local_store 字段）：单元测试 —— load/save round-trip（parse + serialize + 再 parse 断言等价）
- **R2**（main.py 透传）：单元测试 —— sync_agent、handle_agent_create、current_agent_payload 透传 features/custom_prompt
- **R3**（IM db/repositories）：集成测试（in-memory SQLite）—— upsert/get 含 features_json/custom_prompt 字段
- **R4**（capabilities.features 投影）：contract 测试 —— GET /capabilities 返回 features 列表与 FEATURE_REGISTRY key 一致
- **R5**（agent 预览接口）：单元测试 + HTTP 入口测试 —— POST /v1/prompt-preview 按 features/custom_prompt 返回组装串，不含 pa.communication_context/core.memory_block 等易变段
- **R6**（session metadata 接线）：单元测试 —— session 创建时 metadata 含 features + vars["custom_prompt"]，runtime 取出填 PromptContext.flags/vars

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | local_store.py — AgentWorkspaceConfig 加 features + custom_prompt | DONE |
| R2 | personal_assistant/main.py — 透传 + 持久化 | DONE |
| R3 | IM db + repositories — features_json + custom_prompt 字段 | DONE |
| R4 | IM capabilities.features 投影 + agent routes | DONE |
| R5 | agent `POST /v1/prompt-preview` 预览接口 + IM 代理路由 | DONE |
| R6 | session 创建 metadata 接线 — features/custom_prompt → PromptContext | DONE |
