# gateway delta-spec — bugfix-437

> 本文件是 bugfix-437 对 `docs/specs/gateway/spec.md` 的增量草案。收尾由 orchestrator 据实际 diff 校正并并入 canonical。

## ADDED Requirements

### Requirement: agent 回复失败时即时反馈真实原因

当一轮 agent 回复因故无法完成时,Gateway 即时把该条回复在消息级翻为失败态并附带可读的真实失败原因,
归属到对应 agent。该即时反馈不依赖 IM 的 idle 看门狗;看门狗仅在「整个节点失联、无法发出任何反馈」时
作为最后兜底。

#### Scenario: run 失败即时翻为失败态
- **GIVEN** 用户向某 agent 发了一条消息,该 agent 开始回复
- **WHEN** 这一轮回复在中途失败(例如超长会话腾挪后仍无法继续)
- **THEN** 该条回复在数秒内翻为失败态,携带可读的真实失败原因,并归属到该 agent
- **AND** 用户无需等待约两分钟才看到一句笼统的「relay idle」超时提示

#### Scenario: 节点失联时看门狗仍兜底
- **GIVEN** 一条 agent 回复处于进行中
- **WHEN** 整个节点失联、无法发出任何终态反馈
- **THEN** IM 的 idle 看门狗在静默窗口后仍把该回复兜底翻为失败,避免其永久停在进行中
