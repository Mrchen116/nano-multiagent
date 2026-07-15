# refactor-463-M4: 验证闭环与 owner 竞态修复 — Tasks

> 对齐: ../design.md（post-acceptance fix, round 1）
> 输入: `../verification.md`、`../acceptance.md` 与 change-code-review Round 1 独立 verifier 结论

## 目标

以已批准的 concrete owner 边界为修复位置，闭合 Round 1 暴露的 revision/run-control、权限、shutdown resource graph、internal-dispatch readiness 与真实重连问题；不为现象在调用方堆补丁，不恢复已废弃的 `system_prompt` 覆盖语义。

## 合并去重后的问题与正确 owner

### A. Revision、session provenance 与权限

- active marker 只有 `run_id`，配置 publish/invalidate 后 stop/steer 会重新 resolve 新 session。修复应让 coordinator 持有不可变 run-control handle（至少原 `kernel_session_id`、`run_id` 与完成控制/历史所需的原 snapshot/binding 事实），active stop/steer 只控制该 handle；新 revision 只影响旧 run terminal 后的 normal admission。
- internal dispatch 在旧 revision run 发起工具调用时不能把 origin kernel session 重新标成当前 revision；fork 的 source binding lookup 与 snapshot/guard 也必须是同一 binder 语义操作。来源 provenance 的捕获、await 后校验与 semantic bind 都归 binder，不由调用方拼装。
- `tool_allowlist=[]` 是显式零权限，不能在 `Kernel.create_session()` 中因 truthiness 退化为 `None`/产品默认工具。修复契约源头并补 Gateway→Kernel→Runtime 集成回归。
- heartbeat 的 canonical/专用 session cache 必须带 revision 或由 binder 唯一失效；配置更新后不得继续用旧 prompt/tools，也不得因 binder miss 绕过 busy gate。cron isolated run 仍读 live catalog，awareness 只能写当前 canonical binding。
- 旧 revision 已建立的 background subscriber 可以完整结束；self-evolution/session event 投递使用 subscriber 已捕获的原 reply context/provenance，不能因 binding row 已 eager invalidation 而静默丢失。

### B. Shutdown resource graph 与 accepted-work 终态

- subscriber manager seal 不能让已存在 subscriber 的 terminal `ensure()` 失败；background subscriber 收到 stop 请求后仍须消费已缓冲 terminal event，不能先看 stop flag 直接退出。
- manual cron admission 的 sealed 检查与 pending/current 注册必须线性化；shutdown seal/drain 不得观察零任务后让已接纳请求在 drain 之后启动。
- `InboundDispatcher` 对 `run_coroutine_threadsafe()` 的 proxy cancellation 必须等待底层 loop task 接收取消并完成 async cleanup；不能只等待 wrapper future。
- 用真 IM/Gateway 两条 accepted 用户消息复现 SIGTERM，定位并根治 conversation 永久 `running` 与空 provisional bubbles；在 IM transport 关闭前，每个 active/queued item 都必须落 completed/failed/cancelled 的明确可见终态。
- admission settle timeout 必须包含具体 `session_key` 与稳定 item id；单资源 timeout/异常仍不跳过其余 shutdown owner。

### C. Internal dispatch、reconnect 与 inbound 边界

- internal dispatch listener 绑定失败不能被吞后仍设置 Gateway ready。endpoint 必须由实际监听地址产生并与每个 session metadata 一致；两个 Gateway/worktree 并存不能因固定 `127.0.0.1:8089` 冲突。`send_message` 无监听端点时必须 fail-fast，而不是运行时 connection refused。
- 在隔离真栈复现“Gateway pid 存活但 node offline 90 秒、用户发送 503”，从连接 supervisor/生命周期 owner 定位根因并修复；不得用放宽等待时间或测试重试掩盖。启动、IM kill/restart、正常群消息后的连接都必须恢复。
- WebRelay 的 IM shadow 入站（`trigger_source == "im"`）不得再次进入 external shadow sync；恢复 typed identity guard，并覆盖当前 `RuntimeProtocolFacts` 形态，既无 JSON 序列化 warning 也不重复 POST 用户消息。
- `IMAgentConfigSync.on_agent_created` 改为构造期显式 dependency/只读 provider，删除 mutable post-wiring；config-sync 测试删除 `_ownership(pipeline)` 兼容 shim，直接使用 concrete catalog+binder，覆盖 v1→v2 publish、真实 revision、旧 binding invalidation 与后续 v2 resolve。
- 动态 prompt 真栈复验使用当前公开字段 `custom_prompt`；`system_prompt` 是废弃兼容字段，不得为 Round 1 的错误验收驱动恢复旧覆盖语义。

### D. Deep module closure 与低风险同文件清理

- 把 `main.py` 内 cron accepted→running→terminal、stream delivery、canonical awareness 链收回 `CronExecutionService`/公开 `CronRunner` collaborator，复用 service 自己的 stores；composition root 只构造与注册，不调用 `CronRunner` 私有方法。
- `sync_agent()` 与 `reconcile_all_agents()` 复用同一个纯 mirror payload decoder；create 路径只复用无策略归一化 helper，不用 mode flag 合成巨型 decoder。
- 同步修复稳态 reconnect 的无变化整份 YAML 重写：分别比较 durable local 与 live catalog，local 不同才 persist、catalog 不同才 publish/invalidate，保持 persist-before-publish 与本地修复语义。
- 清理 `verification.md` 指出的 trailing whitespace/EOF whitespace；新增或拆分测试文件继续满足 400 行 contract。

## 不在修复范围

- 不引入共享长生命周期 HTTP client：独立 verifier 确认当前 client 均正确关闭，缺少值得阻塞本 unit 的性能证据。
- 不把 create/sync/reconcile 三条高层配置路径强行合成一个 mode-driven decoder。
- 不改变 SQLite binding schema、session key、reply-context serialization、IM API 或外部 channel 协议。

## 退出标准

- [ ] 上述 A/B/C 的每个 confirmed correctness finding 都有先失败后通过的永久回归；不得仅靠 mock 内部调用次数证明。
- [ ] Round 1 verifier 的 CRITICAL 与两条 WARNING 关闭；`git diff --check` 全绿。
- [ ] Round 1 reviewer 的 `send_message`、accepted-work shutdown、offline reconnect 三条真用户旅程关闭；动态配置用 `custom_prompt` 重跑并通过。
- [ ] Cron lifecycle 只有一个 production owner，`main.py` 不构造 cron stores、不调用 `CronRunner` 私有方法；config-sync 无 `_ownership(pipeline)` 测试 shim和 mutable callback post-wiring。
- [ ] 最窄测试、相关 contract、`ruff check src tests`、`pytest -m "not e2e" -n 4 --dist worksteal` 全绿。
- [ ] 通过 `scripts/e2e-up.sh` / `e2e-down.sh` 的隔离高位端口真栈落 durable evidence：动态 `custom_prompt`、真 `send_message`、并发 accepted-work SIGTERM、IM 断开重连；所有自启服务和运行时文件清理完成。

## 测试策略

- owner/concurrency 回归落现有 catalog/binder/coordinator/shutdown/dispatcher/cron/subscriber 测试；必要时新建语义单一文件，但每个文件不超过 400 行。
- internal dispatch 端口冲突必须使用两个真实 listener 或真实占端口方式验证 readiness 与 endpoint，不只 fake `TCPSite.start()`。
- reconnect 与 shutdown 用户终态必须走真 Gateway 进程、真 IM API/SQLite 对账；LLM 可用仓库 controllable upstream fixture 保证确定性。
- `custom_prompt` 动态配置按公开 IM PATCH/live GET → 下一轮与新会话执行，不使用 `system_prompt`。
- 真栈命令与对账写入 `M4-fix-validation-closure/evidence/`；临时脚本不进永久 suite。

## Roadpoints

### R1 — 闭合 revision/run-control 与权限 provenance

- 状态: DONE
- 步骤: 先落 active publish/invalidate→steer/stop、internal-dispatch/fork provenance、empty allowlist、heartbeat revision、旧 subscriber context 红测，再在 coordinator/binder/Kernel source owner 修复。
- 验证: catalog/binder/coordinator/internal-dispatch/fork/heartbeat/background 聚焦测试与权限集成回归。

### R2 — 闭合 shutdown task graph 与 terminal delivery

- 状态: DONE
- 步骤: 先落 subscriber seal/buffer、cron admission、threadsafe root cancellation、具名 timeout 与真 SIGTERM 悬空回复红测，再修 owner 顺序和 cancellation acknowledgement。
- 验证: shutdown/queue/dispatcher/subscriber/cron 聚焦测试；真 IM/Gateway 两条 accepted work 终态对账。

### R3 — 根治 dispatch readiness、reconnect 与 shadow/config 边界

- 状态: TODO
- 步骤: 先落端口冲突 fail-fast/实际 endpoint、offline supervisor、IM shadow typed guard、concrete config-sync ownership 红测；再修 composition/transport owner，并以 `custom_prompt` 真栈重验。
- 验证: internal-dispatch/config-sync/shadow/reconnect/build-runtime/architecture 测试；真 `send_message` 与 IM kill/restart。

### R4 — 收深 cron/config owner 并完成全量与真栈签收

- 状态: TODO
- 步骤: 收回 cron execute/deliver/awareness、提取 mirror decoder、避免无变化整份持久化；清 whitespace；跑全量门禁与隔离真栈，落 durable evidence 并清理服务。
- 验证: 最窄测试 + contract；`git diff --check`; `ruff check src tests`; `pytest -m "not e2e" -n 4 --dist worksteal`; M4 四条真栈旅程。
