# Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_570`，独立于 design author；继承模型。
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖职责边界、实际生产接线、current specs、全部 milestone 和验收前置。
- started_at: `2026-09-22T17:22:00+08:00`（开始时间按分钟估计）
- completed_at: `2026-09-22T17:26:00+08:00`（按分钟记录）
- duration: 约 4 分钟。
- baseline: main `363eefc5d9cf228e8ef4c8a9dc9e72051fae0377`；受审 motivation/design/M1 目录冻结；未修改代码或设计，保留其他 dirty/untracked。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING**。

核心提取方案可兑现目标，当前阻断集中在真实验收入口尚未落实及 readiness 路径错误。需补齐 runbook 后 closure 复审；不要求扩大产品范围。

### Coverage 与证据

- **现状断言**：`message_delivery.py:725-856` 确认两条 shadow 发布路径读取 sync 的 token、HTTP 配置、store、before/after hooks。`shadow_sync.py:328-347,405-465` 确认 live/recovery 都把自身传回 delivery。痛点真实存在；`_project_images` 仅剩定义，可删除这一未使用投影入口。
- **实际组装**：`composition.py:487-504,643-665,755-773` 确认生产 `compose_gateway` 使用共享 runtime context 的 admission/release，以 lazy provider 接入稍后构造的 MessageDelivery。design 明确先构造同一个 store 与 publisher，再同时注入 sync/delivery，保留 lazy provider，不引入恢复专用旁路。optional publisher 对应无 IM 配置分支，范围合理。
- **职责与复用**：sync 继续负责用户 anchor、durable facts、恢复调度；delivery 继续负责冻结内容投影与 ledger；新增具体 publisher 负责两种 HTTP 协议与成功/拒绝回执。publisher 复用既有 saga store、headers/base URL helper、runtime hooks，不接管 ReplyImages 或 ledger。相比公开 sync 私有 getters，这个边界移走了实际协议责任；相比把完整交付移回 sync，它保留既有回复 owner。未发现需要新增泛化 transport、schema 或兼容机制的理由。
- **行为顺序**：现有 POST 与 PUT 均在 projection 后取 token，admission 拒绝 discard 而不 release，HTTP 在 finally release 后才校验 id 并记 saga receipt，最后写 ledger。design:48-61 保留这些顺序和错误语义；PUT 仍使用 shadow_message_id，POST 保留 caller idempotency key 与 suppress_relay。sync 提前解析 saga/无 anchor 返回与原 reconcile 行为一致。
- **用户约束与 delta**：motivation 的用户消息/正文/工具状态镜像、文本与冻结图片恢复、停止后不晚发均映射到 M1。`docs/specs/gateway/external-channels.md:129-150,207-254,371-407` 与 `routing-delivery.md:14-46` 支持保持现有路由、镜像、控制确认和图片恢复语义。内部责任移动无需修改消费者契约，`no spec delta` 合理；无前端改动，原型与 must-match 不适用。
- **测试与 milestone**：单 M1、无并行文件冲突；既有 shadow sync/relay/auth/images 测试可重写 fixture 保留行为断言。`tests/unit/personal_assistant/test_shadow_auth.py:22` 覆盖 runtime token 更新，`tests/integration/test_shadow_reply_images.py:151` 覆盖恢复先上传冻结图片再发布。真实 composition 共用 store/hook、真实 stop/恢复与 history 结果仍应由独立产品验收覆盖，不能以这些静态回归替代。退出标准本身完整，执行资源见 R1-W1。

### 历史问题闭环

首轮，无历史问题。

### Issues

#### R1-W1 — Runbook 尚不能驱动必验的外部 shadow 链路

- 位置：`design.md:73-81`。
- 证据：文档称通过“现有测试 channel 或外部 ingress”进入隔离 Gateway，但只给默认 `e2e-up.sh`。`config/e2e/gateway.yaml` 仅启用 web_relay，feishu:e2e 禁用；`composition.py:1144` 的 registry 构造没有文档所称的合成测试 channel。仅从 Web IM 发消息不能替代 external-triggered shadow publication。另表中 `/im/v1/health` 不存在；`scripts/e2e-up.sh:257-263` 明确 IM readiness 使用 `/openapi.json`。
- 后果：照文档启动只能得到 web relay 栈，无法独立执行 motivation 的 shadow POST/PUT、失败重放、冻结图片和取消旅程；health 命令也无法通过。把入口选择推迟到实施交接，会使 Gate 2 的必验前置未收口。
- 修正要求：在 design 明确具体可执行驱动入口、启动/停止/readiness 与各必验场景触发方法，说明替换边界和真实保留部分。可用一次性 driver 经真实 `compose_gateway` 构造、经 `ChannelAdapter.start(on_inbound)` 捕获真实入站回调，再注入合成 provider identity；只替换外部 provider 边界，保留内核、shadow、SQLite、IM HTTP，并经客户端 REST history 观察。需说明与 e2e-up 已启动 Gateway 的关系，避免双节点/同配置并存；故障恢复与 stop 应通过真实入口触发，不能直接调用 delivery/publisher 冒充产品验收。无需新增产品 API 或永久测试框架。
- 依据：design-author 的 `references/prototype-and-runbook.md` 要求落实真实入口驱动方式及必验资源，未落实前置阻塞 Gate 2。

### Recommendations

无额外建议；范围保持本次 shadow 发布边界。

### Author Resolutions

- R1-W1 — accepted。核对 scripts/e2e-up.sh 默认只启用 web_relay 且健康入口为 /openapi.json。design Runbook 修正 health，并落实 /tmp/refactor-570-channel-driver.py、具体启动/停止/POST入口、真实内核与 IM 观测范围及失败恢复方式；driver py_compile 通过。该临时 fixture 只替换外部 provider 边界，不进入永久 tests。请求独立复审修改及影响。

## Round 2

### Metadata

- reviewer target: `/root/design_570`，与 R1 同一独立 reviewer。
- review_mode: `closure`
- mode_reason: author 仅落实 R1-W1 的运行资源及局部命令，未改变产品接口、责任归属、delta 或 milestone；无需重开 full。
- started_at: `2026-09-22T17:28:00+08:00`（按分钟记录）
- completed_at: `2026-09-22T17:29:02+08:00`
- duration: 约 1 分钟。
- baseline: main `363eefc5d9cf228e8ef4c8a9dc9e72051fae0377`，修订后的 design 与 `/tmp/refactor-570-channel-driver.py`。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**。

### Coverage 与证据

- retained_from: Round 1。产品方案、owner 划分、协议/回执顺序、current spec 的 no-delta 判断和 M1 覆盖未改变，保留 R1 的源码证据；本轮仅核对真实驱动入口、隔离生命周期及 readiness 修正。
- 已读取 driver 全文并独立执行 repo `.venv/bin/python -m py_compile /tmp/refactor-570-channel-driver.py`，成功。该脚本通过 registry 注册合成 ChannelAdapter，并运行 `personal_assistant.main --foreground`。`process_lifecycle.py:1010-1012` 在实际构造时引用 compose_gateway，故 registry 替换落在真实产品组装入口，不替换发布实现。
- driver 的同步 `start(on_inbound)`、规范 InboundIngress、`prepare_images` 回执与 `send_prepared` admission/release 参数符合 `channels/base.py`、`outbound_router.py:92-113` 的契约。HTTP handler 从线程调用真实入口由 `InboundDispatcher.__call__` 跨线程转入运行 loop；没有直接调用 delivery/publisher。
- 新 runbook 明确先停 e2e-up 启动的唯一 Gateway，保留隔离 IM/数据，再用相同配置启动 fixture Gateway；明确 PID、日志、node/cwd 和最终 e2e-down 清理。unit worktree 路径是实施阶段拟创建路径，执行前按交接确认被测 checkout，不视为已有实现或已通过产品验收。
- `/openapi.json` 与 `e2e-up.sh:257-263` 一致；合成 POST、同入口 `/stop`、真实 IMClient history、隔离故障/专用代理及冻结图片后删除源再恢复的操作边界均已明确。端口和故障时点在真实实施交接时记录，属于执行参数，不再把选择哪种产品入口留空。

### 历史问题闭环

- **R1-W1**
  - Author Resolution: accepted；补齐临时 channel driver、运行命令、替换边界、隔离进程管理，修正 health。
  - 本轮证据: 上述源码/fixture 契约核对及独立 py_compile；design Runbook 不再依赖不存在的默认外部 channel。
  - 状态: **closed**。Gate 2 确认可执行方案与资源，真实文本/图片恢复和 stop 用户结果仍由后续独立产品 reviewer 实测，不在本轮伪称通过。

### Issues

无。

### Recommendations

无。

### Author Resolutions

- R2: 已核实闭环证据，无实质异议。Gate 2 Approved；实现前受审设计无进一步语义变化。
