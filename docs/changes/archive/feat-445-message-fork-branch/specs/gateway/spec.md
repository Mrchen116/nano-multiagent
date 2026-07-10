# gateway delta-spec — feat-445

> 对齐: feat-445

本 unit 对 `docs/specs/gateway/spec.md` 的增量。收尾由 orchestrator 据实际 diff 校正后并入 canonical。

## ADDED Requirements

### Requirement: Gateway 受 IM 委托对某 agent 会话按 fork 点 fork 出独立新会话

IM 不持有 conversation↔session 映射、也不直读 Gateway 侧会话日志，故「让分支单聊的 agent 记得历史」由 Gateway 受委托完成。Gateway 收到 IM 的 fork 请求后：复制**源会话在指定 fork 点那一刻所用的上下文视图**（源若已压缩则含当时的压缩摘要；未压缩则为到 fork 点的完整内容），生成一个独立的新会话，并把请求里的新 conversation 预绑定到该新会话——之后该新会话的首条入站消息命中预绑定、agent 带着「与源在 fork 点时一致」的记忆回复。新会话独立：对它的后续追加不回流源会话。

#### Scenario: 受委托 fork 后新会话带源在 fork 点的记忆
- **GIVEN** 一个已有多轮对话的 agent 会话，IM 经 WS RPC 请求对它在某 agent 回复处 fork 出新 conversation
- **WHEN** Gateway 处理该 fork 请求
- **THEN** Gateway 生成一个新会话，其上下文 = 源会话在该 fork 点那一刻所用的视图；新 conversation 被绑定到该新会话；该会话首条入站消息复用此绑定、不另建空会话
- **AND** 用户在新 conversation 继续对话时，agent 表现出对这段历史的记忆

#### Scenario: fork 复刻源在 fork 点的上下文（含压缩态），与源体验一致
- **GIVEN** 源会话在 fork 点之前曾发生过上下文压缩（喂模型时历史被摘要替代）
- **WHEN** Gateway 受委托 fork 该会话到该 fork 点
- **THEN** 新会话复制的是源在该 fork 点的视图（含当时已生效的压缩摘要），与源在该点的记忆一致——不还原压缩前的完整原始历史（不比源记得更多），也不丢失源当时已有内容

#### Scenario: fork 点之后的源历史不进入新会话、两会话独立
- **GIVEN** fork 点之后源会话还有更晚的对话
- **WHEN** fork 完成后用户在新会话与源会话各自继续对话
- **THEN** 新会话不含 fork 点之后的源历史；两会话各自独立演进，互不影响对方记忆

#### Scenario: fork 失败回包让 IM 可回滚
- **GIVEN** Gateway 处理 fork 请求时失败（如源会话绑定缺失、内核 fork 出错）
- **WHEN** Gateway 回复该 WS RPC
- **THEN** 回包标明失败，IM 据此回滚已建的新 conversation；Gateway 不留下半成品绑定
