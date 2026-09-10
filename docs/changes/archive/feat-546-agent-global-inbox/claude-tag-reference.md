# Claude Tag：独立工作会话与跨讨论的信息联系

调研日期：2026-09-09。本文记录官方公开做法，供 feat-546 需求对齐使用，不代表本单已采用该方案；未实际运行 Claude Tag。

## Thread 与 Session 的区别

Channel 是 Slack 频道，Thread 是围绕消息展开的讨论串；Agent Session 是执行工作的上下文。Claude Tag 为频道顶层保留一个 session；需要调查、工具或持续交流的任务进入 Thread，并绑定独立 session 和 sandbox。不同 Thread 的工作状态不直接共享。[运行机制](https://claude.com/docs/claude-tag/concepts/how-it-works)

```text
Channel A
├─ 频道顶层 → Session A
├─ 工作 Thread 1 → Session A1
└─ 工作 Thread 2 → Session A2

Channel B
├─ 频道顶层 → Session B
└─ 工作 Thread 3 → Session B3
```

因此，Thread 本身不是 Session，但该产品将工作 Thread 绑定到了各自的 Session。任务结果回到对应讨论，成员可以通过新回复继续引导工作。[运行机制](https://claude.com/docs/claude-tag/concepts/how-it-works)

## 跨讨论的信息怎样延续

公共频道产生的记忆在 workspace 内共享；私有频道保存自身记忆，并可读取公共 workspace memory；DM 保持独立。记忆是整理过的笔记，不是完整聊天记录。Claude 还可以列出并读取本频道以往 session 的 transcript。[记忆规则](https://claude.com/docs/claude-tag/users/memory)

所以，A 频道记录的公共知识可以被 B 使用，但 B 不会因此自动拥有 A 的全部工作上下文或实时中间状态。“跨讨论连续认知”在这里包含记忆和信息检索，不等于一个全局 Session。

## 如何决定参与及接续已有工作

2026-08-13 的官方更新描述：Claude 结合频道上下文、记忆和长期指令，在直接回复、另开 Thread 深入处理、把消息路由给进行中的工作、保持沉默之间选择。新信息因此可以补充已有工作，而非每条消息都变成独立任务。[主动参与机制](https://claude.com/blog/claude-tag-now-reads-even-more-of-the-room)

主动响应可以关闭，也可用自然语言规定参与范围。长期判断没有内容可补充时会休眠，提及可以唤醒。上述响应设置是 Tag 的产品行为，不意味着本单也应使用同样的配置层级。[响应控制](https://claude.com/blog/claude-tag-now-reads-even-more-of-the-room)

## 工作状态如何延续

Thread 的会话记录可以跨空闲期保留，sandbox 会在空闲后释放，下一轮在新的 sandbox 中恢复工作。已推送或发布的产物与仅存在 sandbox 内的文件具有不同的持久性。[会话生命周期](https://claude.com/docs/claude-tag/concepts/how-it-works)

## 与 Raft 的区别及证据边界

[Raft](raft-reference.md) 明确以每个 Agent 的持续 Session 连接不同讨论；Tag 保留频道及工作 Thread 各自的会话，再通过记忆、检索和消息路由建立联系。

本轮材料未披露与 Raft 等价的收件箱主动拉取接口、确认协议、忙时精确读取时点、抢占规则或工作会话并发上限。不能将本单此前讨论的“忙时自主拉取、闲时唤醒”整体声称为 Tag 的既有实现。
