# feat-430 delta-spec: im

> 对齐 canonical: [`docs/specs/im/spec.md`](../../../../specs/im/spec.md)
> 本文件只列 feat-430 对 IM 对外可观察行为的增量。草案——收尾由 orchestrator 据实际 diff 校正并软对账并入 canonical。

## MODIFIED Requirements

### Requirement: 节点 runtime 能力按需向在线网关解析,不入库快照

在 canonical 同名 Requirement 基础上，capabilities 返回的 skills 每项增加 `location` 字段，供前端按真实路径区分同名 skill。

#### Scenario: agent 能力的 skills 项携带 location
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的 `skills` 列表中每项携带 `location`（SKILL.md 路径，可空；网关 payload 无此字段时降级为空），前端据此对同名不同路径的 skill 分开展示
