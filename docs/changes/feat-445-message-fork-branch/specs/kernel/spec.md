# kernel delta-spec — feat-445

> 对齐: feat-445

本 unit 对 `docs/specs/kernel/spec.md` 的增量。声明本 unit 预计给 canonical 增加/修改的对外行为；收尾由 orchestrator 据实际 diff 校正后并入。

## MODIFIED Requirements

### Requirement: fork_session 复制源会话的无损历史到指定 fork 点，生成独立新会话

`agent.sdk` 的消费者（如 Node Gateway）可对一个已有会话发起 fork：内核以**源会话的完整无损历史**（不是压缩后的上下文视图）为依据，复制到一个指定的 fork 点为止，生成一个**独立**的新会话——新会话拥有自己的历史副本，后续运行带着"源会话到 fork 点为止"的记忆，且对新会话的追加不回流源会话。fork 点之后的源历史不进入新会话。

（现状 `fork_session` 是忽略源会话、只建空会话的 stub；本 unit 将其修正为真实复制，并新增"复制到 fork 点"的能力。）

#### Scenario: fork 出的新会话带着源历史到 fork 点为止的记忆
- **GIVEN** 一个已有多轮对话的源会话，消费者指定其中某一条消息为 fork 点（即便同一轮里产出了多条消息，也能精确指向其中某一条）
- **WHEN** 消费者经 `agent.sdk` fork 该会话到该 fork 点
- **THEN** 得到一个新会话，其历史 = 源会话从起点到 fork 点那条消息（含）的完整内容；在新会话里继续运行时，模型表现出对这段历史的记忆；fork 点之后的源内容不在新会话中

#### Scenario: fork 取无损历史而非压缩视图
- **GIVEN** 源会话曾发生过上下文压缩（历史在喂模型时被摘要替代，但底层记录无损保留）
- **WHEN** 消费者 fork 该会话
- **THEN** 新会话复制的是压缩前的完整原始历史，而非压缩后的摘要视图

#### Scenario: 新会话与源会话相互独立
- **GIVEN** 已从源会话 fork 出新会话
- **WHEN** 在新会话继续对话、或在源会话继续对话
- **THEN** 两者各自独立演进，互不影响对方的历史
