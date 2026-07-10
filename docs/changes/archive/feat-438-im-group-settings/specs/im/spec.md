# IM Specification — feat-438 delta

> 本文件是 feat-438 对长青契约层 `docs/specs/im/spec.md` 的**增量草案**，收尾由 orchestrator 软对账并并入 canonical。
> 只写本 unit 改变的对外行为；主语 = IM 的消费者（浏览器前端 / 终端用户）。

## ADDED Requirements

### Requirement: 群会话支持成员增减、改名与解散（owner 隔离、解散限创建者）

前端经 `/im/v1/conversations/{id}*` 对一个已存在的群会话管理其成员与元数据：向群添加参与者（Actor）、
移除某个参与者、修改群名、解散整个群。所有操作按 owner 租户隔离（跨租户 404）；解散仅会话创建者可执行，
非创建者被拒。这些能力让用户在内置 Web IM 里完成基本群治理，无需重建群。

#### Scenario: 向已存在的群会话添加参与者
- **GIVEN** 终端用户在自己租户下有一个群会话，且账号下存在尚未加入该群的 agent
- **WHEN** 前端 `POST /im/v1/conversations/{id}/participants` 带一组 Actor（`{type:"agent", id:"<agent_id>"}`）
- **THEN** 200 返回该会话快照，其 `participants` 含新加入的 agent；此后该 agent 能收发该会话后续消息

#### Scenario: 重复添加已在群的参与者保持幂等
- **GIVEN** 某 agent 已是该群成员
- **WHEN** 前端再次 `POST /participants` 提交同一 agent
- **THEN** 成员不重复出现，会话快照参与者集合不变（不报 500）

#### Scenario: 添加请求为空或 agent 无法解析被拒
- **WHEN** 前端 `POST /participants` 提交空列表或无法解析为已知 agent 的 id
- **THEN** 400 拒绝，会话成员不变

#### Scenario: 跨租户添加参与者返回 404
- **WHEN** 用户对不属于自己租户的会话 `POST /participants`
- **THEN** 404，不泄漏该会话存在

#### Scenario: 修改群名生效，空名被拒
- **WHEN** 前端 `PATCH /im/v1/conversations/{id}` 提交非空 `title`
- **THEN** 200 返回更新后的会话，会话列表与详情显示新群名
- **AND** 提交空 `title` 时不接受为新名（会话名保持原值）

#### Scenario: 会话参与者带 user_id 供成员管理
- **WHEN** 前端读取会话（`GET /conversations` 或写操作返回的快照）
- **THEN** 每个 participant 带 `user_id`（agent participant 的 `id` 是 agent_id，`user_id` 是其稳定 IM 用户标识），前端据 `user_id` 调移除端点

#### Scenario: 移除参与者后该成员从群消失
- **GIVEN** 群里有多个 agent 成员
- **WHEN** 前端 `DELETE /im/v1/conversations/{id}/participants/{user_id}` 指定某 agent 的 `user_id`
- **THEN** 204；该会话快照参与者集合不再含该成员；可一直移除到群里只剩用户本人，群仍存在

#### Scenario: 仅创建者可解散群，非创建者被拒
- **WHEN** 会话创建者 `DELETE /im/v1/conversations/{id}`
- **THEN** 204，该会话及其消息被删除，列表不再返回它
- **AND** 非创建者发起同一请求时 403，会话不被删除
