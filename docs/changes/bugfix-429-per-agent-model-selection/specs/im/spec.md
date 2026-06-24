# IM 契约层增量 — bugfix-429

> 本 unit 对 `docs/specs/im/spec.md` 的草案增量。收尾由 orchestrator 据实际 diff 校正后并入 canonical。

## MODIFIED Requirements

### Requirement: 节点能力上报可选模型列表（携带 provider/格式）

agent 配置可选模型列表不再是裸 model 名数组，每个模型携带其注册的 provider/格式。

#### Scenario: capabilities 返回每个模型的 provider
- **WHEN** 前端拉取 `GET /im/v1/nodes/{id}/capabilities` 或 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的可选模型列表中，每个模型带有它注册的 provider（例：`codex_oauth:gpt-5.5` → `openai_compat`，`kimiCoding:K2.6` → `anthropic`）

#### Scenario: agent 配置页模型下拉展示格式
- **WHEN** 用户打开 agent 配置页的模型下拉
- **THEN** 每个可选模型旁展示它的 provider/格式
