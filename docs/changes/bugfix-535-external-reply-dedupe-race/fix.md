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

在 `OutboundRouter.send_text()` 中为每次带去重 key 的出站投递增加进程内原子多 key reservation：在调用 provider 前，于同一锁内检查并占用物理 key 与 final semantic key；任一 key 已完成或正在发送时，该调用不再投递。provider 成功后 reservation 进入既有有界 `OrderedDict` 完成缓存；provider 抛异常则释放所有 reservation 并重新抛出，使后续投递可以重试。未携带 dedupe key 的普通发送不进入 reservation/cache。

回归测试保留在既有语义 owner `tests/unit/personal_assistant/test_gateway_web_relay_adapter.py`：阻塞 observer-like provider send 后并发发起 terminal-like final fallback，断言只发生一次物理发送；另保护 provider failure 后的 retry。实现提交：`40ed2199c`。

## 验证

自动化验证已通过：

- `pytest -q tests/unit/personal_assistant/test_gateway_web_relay_adapter.py`：12 passed。
- `pytest -q tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`：50 passed（unit 合入 `origin/main@bf8b3cb10` 后重跑）。
- `ruff check src/personal_assistant/gateway/outbound_router.py tests/unit/personal_assistant/test_gateway_web_relay_adapter.py`：通过。
- `ruff format --check src/personal_assistant/gateway/outbound_router.py tests/unit/personal_assistant/test_gateway_web_relay_adapter.py`：通过。

真实入口验证已在 `adffefdb4` 基线上完成。按 `docs/development/worktree-runtime.md` 核验权限为 `0600` 的私有环境、专用非 default CLI profile，以及匹配的测试 App/Bot/user 身份后，在 milestone worktree 运行 `scripts/e2e-up.sh --feishu` 和 `scripts/e2e-feishu-probe.py`。真实 probe `nano-e2e-feishu-probe-bb1084b16753b3bb` 经飞书进入隔离 Gateway 并完成 Agent run；同一飞书 P2P 窗口中有一条中间 Bot 消息，唯一 final suffix `bb1084b16753b3bb` 只出现在一条 Bot 消息中，IM shadow 也只有一条对应最终气泡，因此用户可见最终回复恰好一次。随后 `e2e-down.sh` 已停止两个进程并确认高位端口 `65315`、listener lock、PID、临时 config 与 secrets 全部清理。精确 message id、进程与清理证据见 `M1-fix/progress.md`。
