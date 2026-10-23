# bugfix-641: PA 代发回执与审核动作投影

状态：快速开发，已实现并做自动化验证；用户实际验收待完成，保留 active。

## Relations

- Related: feat-616, bugfix-640

## 原始报告与已确认范围

用户在 PA 群代发报错后询问：

> 投递和发送还有关联性？两者不是应该解耦的吗？通过你这个修改就能解耦是吧

确认事务内持久化消息与投递任务、事务后后台投递的方案后，用户要求：

> 那就按这个方案快修，开个worktree快修

随后侧聊转交用户已确认的 Guardian 当前动作接口设计：

> 总体结构保持：审核规则 + PA 当前有效上下文窗口 + 当前动作。不要因为窗口很大而裁成几条授权消息，不要额外灌入窗口之外的历史。本次修改范围是 planned_action 的模型可见接口；后端冻结、并发和提交校验继续保留。

接口要求为 `tool + arguments + audience`：正文与原始 mention 不变，完整受众保留且每人只用一个可关联 mention 的身份 ID；校验版本、owner_guard、last_owner_message_id、重复 recipient_ids 与累计正常可读来源列表不进入模型。附件实际内容、交互、共享任务参数和外部可见范围必须完整；当前限制和未知状态仍明确提供；不能新增授权摘要或 authorized 标记。

## 现象与根因

- 生产只读证据表明：一次 reviewed 群代发已经写入消息、代发标记并将 operation 置为 confirmed；PA 不是该群成员，群内接收 Agent 的 relay 数为零，调用方收到 `conversation_id not found`。
- `Gateway.relayMessage` 用发送者身份查询聊天，错误地把“PA 本身入群”作为收件 Agent 投递的隐含条件。该通用实现源于 `ebd3411e44`；feat-616 的授权代发扩展允许 PA 经主人权限向未加入聊天发送，使旧假设失效。
- `PersonalActions.commit` 在消息事务提交后才调用 groupReply，因此建投递任务失败既留下孤立消息，也把持久化成功的发送报告为失败。原测试把 groupReply mock 掉，仅覆盖直接聊天 relay，未覆盖真实的非成员 PA 群代发。
- bugfix-640 有意保留完整当前有效上下文，但直接把冻结证据对象作为 planned_action；内部 freshness 字段和模型判断事实混在一起。字段歧义已确认，其对具体模型误判的因果作用未被证明；本次不改变完整上下文策略，也不宣称消除所有语义误判。
- 必须保留 feat-616 的独立披露、真实作者/主人代发标记、权限复核、真实发送回执及幂等语义。

## 修复

- 用接收 Agent 的成员身份读取投递上下文，保持原 PA 作者与 delegation。
- PA 发送的消息、代发标记、直接/群聊 relay、operation confirmed 在同一 SQLite 事务内提交；建队列失败则全部回滚。
- PA 发送回执不等待 Agent 传输。复用现有 RelayDelivery 定时与重连恢复，不新增队列；浏览器即时广播失败由持久事件重放，不能否定发送回执。sent relay 仍不等于接收回执。
- DSH 的 `pa.review` 入口通过纯投影生成模型当前动作，完整冻结证据仍用于 IM 校验。安全通知沿既有已送达主人通知事实审核；它不再在 PA 中提前裁掉受众/限制字段。
- 不补发生产历史孤立消息、不部署、不修改完整上下文获取及预算策略。

## 验证

- 修前：新增群代发用例复现 `conversation_id not found`，直接聊天用例暴露同步传输，事务回滚用例失败。
- 修后：IM disclosure/PA/source/relay/messaging/attempt 六文件 52 项通过；覆盖非成员 PA、两个接收 Agent、离线/背压恢复、幂等、第二个 relay 写失败整体回滚。
- Guardian/PA 第一轮 25 项通过，覆盖文本、mention、完整受众、交互、附件、任务、外部目的地、限制及 unknown；真实 DSH 子执行用例通过。后续 native 隔离与取消、review 生命周期及 relay 恢复验证全部通过；合计 96 项，精确命令见 code-review.md。独立完整代码审查返回 `[]`。
- 原有受众变更、主人新指令、来源排除、附件内容变化、并行 disclosure 版本失效测试保留并通过。
- 用户实际验收、生产验证及历史孤立 relay 修复未进行；不据单元或 native fixture 声称生产已恢复。
