# Gateway 契约层增量 — bugfix-429

> 本 unit 对 `docs/specs/gateway/spec.md` 的草案增量。收尾由 orchestrator 据实际 diff 校正后并入 canonical。

## ADDED Requirements

### Requirement: agent 选定的模型在对话中生效，按当前配置每轮路由

Gateway 在每个新 run（用户消息、heartbeat、cron 触发）按 agent 当前 `default_model` 选择模型，传给内核生效。

#### Scenario: agent 选定模型后对话用该模型
- **GIVEN** 某 agent 配置 `default_model = codex_oauth:gpt-5.5`
- **WHEN** 用户与该 agent 对话
- **THEN** 该轮 LLM 请求用 `codex_oauth:gpt-5.5`（而非全局默认）

#### Scenario: 改模型后旧会话继续聊用新模型
- **GIVEN** 某 agent 曾用模型 A 聊过、存在历史会话
- **WHEN** 在配置页改为模型 B 后回到该历史会话发新消息
- **THEN** 新消息用模型 B

#### Scenario: agent 未选模型时用产品层默认兜底
- **GIVEN** 某 agent 的 `default_model` 为空
- **WHEN** 与其对话
- **THEN** 用 Gateway 配置的全局默认模型正常回复，不报错

#### Scenario: heartbeat/cron 触发的轮次也用 agent 当前模型
- **WHEN** heartbeat 或 cron 为某 agent 触发一轮
- **THEN** 该轮用该 agent 当前 `default_model`（或产品默认兜底）

### Requirement: 动态新建 agent 的模型选择持久化

#### Scenario: IM 动态新建 agent 选模型后重启保留
- **GIVEN** 用户在 IM 新建 agent 并选模型 B
- **WHEN** Gateway 重启
- **THEN** 该 agent 仍在、其模型仍是 B，继续用 B 对话
