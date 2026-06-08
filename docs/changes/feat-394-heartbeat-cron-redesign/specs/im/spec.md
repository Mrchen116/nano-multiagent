# IM 契约层增量（delta-spec）— feat-394 验收修订（决策 E）

> 本文件是 feat-394 对 canonical `docs/specs/im/spec.md` 的**增量草案**。收尾由 orchestrator
> 据实际 diff 校正后并入 canonical。消费者视角 = IM 前端（agent 配置页）。

## MODIFIED Requirements

### Requirement: Agent 配置返回的 heartbeat cadence 即该 agent 的真实节律值

- `GET /im/v1/agents/{id}/config` 返回的 heartbeat cadence（`every`）是该 agent 的真实配置值；
  未配置时为默认 **30m**。前端据此渲染。
- **Scenario**：某 agent 未配置 `heartbeat.every` → config 响应的 cadence 体现为默认 30m，前端显示 30m。
- **Scenario**：owner 经配置页改 cadence 并保存 → 后续 `GET config` 返回新值，前端显示与之一致。

## ADDED Requirements

### Requirement: 提供 agent 当前 HEARTBEAT.md 全文的只读查看

- 配置页可只读查看某 agent 工作区当前 `HEARTBEAT.md` 全文（经 IM 取自该 agent 所在 node 的 gateway，
  仿系统提示词预览的折叠展示）。该视图**只读**——HEARTBEAT.md 由 agent 经文件工具自管，配置页不写它。
- **Scenario**：owner 在某 agent 的 heartbeat 区展开 HEARTBEAT.md 预览 → 看到该 agent 工作区
  HEARTBEAT.md 的当前全文（含 freeform 清单与 `tasks:` 块）。
- **Scenario**：agent 工作区无 HEARTBEAT.md 或为空 → 预览显示空/占位，不报错。
