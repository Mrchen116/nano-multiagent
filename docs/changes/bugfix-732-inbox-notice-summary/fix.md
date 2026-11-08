# bugfix-732: Inbox 提醒直接交付待读会话摘要

## 原始报告

> 那就按这个方案改吧，通知直接带会话、未读数和艾特信息，正文按需读取，去掉必须先check的要求。然后也要保证现有的提醒那个逻辑。就是在LLM请求过程中，有多少条信息来，最后都要聚合成一条提醒，而不是给一大堆条提醒，浪费token

## 现象 / 复现

Global / PA 收到新消息时只看见无来源的 Inbox 提醒，通知和常驻指导还要求先 check，无法直接根据会话、未读数和提及信息选择 read。用户已确认直接提供这些元信息，正文仍由 Agent 按需读取；check 保留为主动刷新入口。

验收：同一模型请求或工具执行期间到达多条消息，下一请求只新增一条 Inbox 提醒，其摘要涵盖各未读会话、名称、可用读取引用、未读数和实际 @ 信息；已交付后再到达的新消息仍可产生新提醒。查看摘要不推进消费位置，既有来源权限、PA 观察背景语义、正文和发送前复核保留。

## 根因

`GlobalAgent.submitWake` 只提交通用通知；`global-mode.ts` 又要求每次先 check。原设计把正文按需摄取与判断所需元信息一起隐藏，导致必经工具往返。`InboxStore.check` 已具备来源摘要，但 `requires_attention` 同时包含私聊、always 策略和回复等情况，不能代表真实 @。

feat-546 建立跨聊天 Inbox 主动摄取；bugfix-693 在 DSH 公开队列上合并尚未交付的 `nano-system/inbox` 提醒，保留最新 durable inputId、水位和全部原始消息。此次复用该机制，避免额外计时器或第二套去重；不得硬中断已开始的请求/工具，也不得压制提醒交付之后的新批次。

## 本次审查安排

独立 `change-code-review` 核对实现、需求及最终 current spec；组合 `agent-context-review` 核对真实 DSH 子进程受控 provider 请求中的摘要、来源、可用读取引用及聚合行为。扩展已有 Inbox / native Inbox 测试，不把受控请求结果表述为真实模型选择验证。无前端修改、无迁移或生产操作。

## 修复

通知生成前由宿主复用原 check 的 conversation describe 查询，补齐各会话真实名称；离线仍使用已保存名称。Inbox 摘要新增 `mentions`（按服务端 `mentioned_agent_ids` 统计未读消息数），并沿用工具的稳定短引用，使通知里的 target 可以直接 read。普通提醒与 PA 背景提醒都附完整未读快照；PA 保留 participant / observer 关系。常驻指导和通知都移除强制先 check。

DSH 既有待交付 Inbox 提醒替换机制未变；每个新 wake 都携带完整快照，最终只保留最新待交付提醒与 durable inputId，不合并或删除已进入历史的提醒。当前契约增量直接见本分支 `docs/specs/gateway/global-agent.md` 与 `personal-agent.md`，交独立审查同时校对。

## 验证

- Red：既有 Inbox 测试扩展后，在旧实现得到 13 passed / 2 failed，失败均为缺少提及计数。
- 最终窄回归：`pnpm exec vitest run apps/node/tests/global-inbox-native.test.ts packages/personal-assistant/tests --maxWorkers=2`，32 files / 270 tests passed。
- 原生 DSH 子进程 + 受控 `llm/stream` 捕获：模型请求期间跨私聊/外部群聊来信只新增一条摘要；两会话计数准确，其他 Agent 的 @ 不计入自身；摘要短引用直接 read，无 check；后续批次仍唤醒；工具执行期间三条来信合为一条，发送复核继续拦住旧草稿；PA 背景到期不打断忙碌执行，空闲只通知一次并明确观察关系。
- `pnpm -r --if-present build`、最终受影响包重建、`pnpm typecheck`、文档完整性检查通过。完整本地 CI 结果在 review 中汇总。
- 证据仅证明确定性装配与既有运行时行为；未调用真实模型，不声称已测模型选择质量、Token 节省量、生产或飞书平台端到端。
