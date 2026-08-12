# bugfix-535: 外部回复并发去重竞态

## Relations

- Related: feat-447

## 原始报告

> 现在代码肯定有bug，看下为啥每句话都重复两遍

> 那你帮我开一个Unit去修复这个问题。

## 现象 / 复现

从飞书触发一次正常 Agent 运行时，Bot 可能把同一条最终回复作为两条独立消息发送到原聊天。用户可见为每句/每个最终回答重复两遍，而不是同一飞书气泡内的文本重复。

复现前提是该轮同时经过现有两条最终回复投递路径：

- runtime observer 在最终 assistant 气泡的 `turn_end` 事件为外部 channel 排队 `reply_phase=final` 的镜像；
- `SessionRunCoordinator` 在 run 终态仍执行 terminal final fallback。

两条路径应以同一 run 与正文的语义去重，用户应只收到一条最终回复；保留中间 assistant 气泡的正常镜像，且 IM 触发的运行仍不得回写外部 channel。

## 根因

`feat-447` 的外部可见投递设计有意保留两条路径：observer 是唯一知道每个用户可见 assistant 气泡完成边界的位置，因而负责完整气泡镜像；terminal 路径只掌握最终 `reply_text`，保留为 observer/mirror 不可用时的兜底。该意图记录在 `docs/changes/archive/feat-447-feishu-channel/design.md` 的“决策 14”，其中明确要求“terminal 阶段如果最后一个气泡已镜像，不得再用 `reply_text` 发送一次；如果 observer/mirror 不可用，terminal final send 可作为兜底保留”。修复必须保住这个双路径容灾语义，而不是删除 observer 镜像、删除 terminal fallback，或把外部回复退化为只发送整轮最后文本。

当前 `OutboundRouter.send_text()` 的进程内去重不是原子的：它先检查 `_sent_dedupe_keys`，调用同步 `channel.send()` 成功返回后才记录 key（`src/personal_assistant/gateway/outbound_router.py:44-55`）。observer 的发送经异步任务和 `asyncio.to_thread()` 执行，terminal fallback 也经 `asyncio.to_thread()` 执行；它们不共享同一个覆盖 Router 检查到登记区间的锁。因此两者可能在任一飞书发送返回前都观察到 key 缺失，各自向 provider 发出一条相同的最终消息。

现有终态语义 key 是正确的：observer 使用 `run_id + bubble` 的物理 key，terminal fallback 使用 `run_id + text` 的物理 key；对于 `reply_phase=final`，Router 还从二者派生相同的 `run_id:final_text:<正文>` key。问题不在 key 不一致，而在检查与占用之间存在并发窗口。

这一缺陷进入代码，是因为 feat-447 M11 R3 的回归测试只顺序调用两条路径并断言第二次被已记录 key 拦截；测试 adapter 立即返回，未模拟两次 `send_text()` 在线程中重叠、首个 provider send 尚未返回的实际时序。该去重逻辑由 `cf42770fb`（`fix(feat-447): close Feishu channel review gaps`）引入，随后 `f566f3d395` 将缓存改为有界 `OrderedDict`，但两版都在 provider send 后才记录 key，未覆盖并发性。

这不是已有 `bugfix-497` 所修复的 IM shadow live/reconcile 双 writer 身份问题：本问题发生在外部 adapter 的 provider send 之前，影响飞书可见的重复最终文本；该修复不改变 shadow saga、IM 富时间线或既有外部-at-least-once 恢复边界。

## 修复

待实施。

## 验证

待实施。
