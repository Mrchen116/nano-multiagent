# perf-666 Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review`（独立于 design author）
- reviewer target: `docs/changes/perf-666-im-hot-paths/design.md`、`motivation.md`、`M1-hot-paths/.gitkeep`
- review_mode: `full`
- mode_reason: 首轮 Gate 2，完整核对三条热点及验收接线。
- baseline: `main` / `63f58270ccb4d87de7f5abcad754c87633561742`；design 与 M1 骨架为冻结的未提交文件。
- started_at: `2026-10-27T11:49:00+08:00`（分钟级近似）
- completed_at: `2026-10-27T11:51:32+08:00`
- duration: 约 3 分钟

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING**。

三个技术方向均有当前代码依据，职责与接口可闭合；需补齐真实验收的 `single_thread` 前置，当前 daily 阵容不能命中最主要的受改路径。本轮未实现或运行候选代码，不把设计可行性等同于性能目标已达成。

### Coverage 与证据

1. **现状与真实组装。** `apps/node/src/main.ts:377-391` 实际创建 `SingleThread` 并接入 `model.check`；`single-thread.ts:40-48,433-459` 只消费普通模式通知，并为每片文本追加串行 ACK Promise。`apps/im-server/src/server.ts:89,173,315-346` 实际组装 Gateway、消息路由和定时 watchdog；`gateway.ts:870-894` 的 delta 在完整 `message()` 后追加正文；`messaging.ts:797-833` 的联系人先全量查询、逐项资格查库，再过滤与分页。现状断言成立。
2. **流式决定与行为保真。** 50ms/4096 作为 flush 触发、单 stream 单在途、ACK 后继续合并，有能力消除每片一次往返的排队放大。设计明确 end/stop/modelCheck flush、每批重新核对投递资格、失败保留现有处理、停用清理、completed 等最后 ACK，覆盖 `single-thread.ts:309-340,350-359,433-460` 的终态与发布约束。沿用 `message_delta` 与原幂等表符合 `docs/specs/im/gateway-relay.md:61-78`。实施仍须验证缓冲尚未到阈值时的 modelCheck 与 end，及在途失败/停用；设计已将对应 flush、权限与最终完整性纳入退出标准。
3. **服务端 delta。** 当前分支只需要消息身份、会话、sender、lifecycle 和状态来校验及写入；完整正文、工具/思考投影留给非 delta 分支即可。`gateway.ts:870-894` 中节点 Agent 归属、双 lifecycle、PA ownerConversation、会话 write 权限都必须保留，设计明确保留。未发现需要新公开 API 或跨包依赖的理由。
4. **watchdog。** `server.ts:322-342` 的 `MAX(created_at)` 对 NOT NULL 文本时间列可由同列倒序 LIMIT 1 等价替代；无事件沿用消息时间及严格 `< cutoff`。`schema.sql:163-172` 与 `db.ts:22` 支持新增幂等索引，不必增加 last_activity 状态及迁移程序。running partial index 加 message/time 索引直接对应当前筛选，不要求全历史聚合。50 万事件 <20% 的目标须在实施后以同机同数据和 EXPLAIN 证明，本轮未复跑基准。
5. **联系人。** 有界候选 + 51 条可见结果的前瞻分页，能够保留 50 条响应及第 50 条 cursor；过滤稀疏时继续取候选是保真所需。当前 `identity.ts:49-65` 区分 owner 的空间资格、active PA 公共联系资格；`messaging.ts:797-809` 还区分 PA 展示裁剪与 `owner.id` 展示名关联。设计明确复用这些语义，且保留 JS Unicode 搜索，未把 SQLite lower/LIKE 的不同语义引入。列表和定向详情共享窄装配模块属于合理职责划分，批量读取资格资料可避免逐人查询；没有必要引入缓存或第二套身份权威。
6. **需求、delta 与范围。** motivation 的顺序、消息完整性、群聊/显式发送抑制、超时和联系人权限均被设计覆盖；无客户端布局/交互变化，`no spec delta` 合理。对照 current `auth-tenancy.md:126`、`agents-nodes.md:741-755` 及 `gateway-relay.md:61-78`，没有批准改变公开权限或协议。无部署、包发布或生产数据操作授权，设计未扩大这些范围。新增索引是现有 schema 初始化能力，无另行历史数据转换，缺省不需 deployment-prompt。
7. **Milestone 与验证。** 单 M1 串行覆盖三条热点，与用户顺序一致；`.gitkeep` 骨架及 worker/reviewer 两轨退出标准齐备。已有 `packages/personal-assistant/tests/model-fallback.test.ts:131-215` 使用延迟 ACK 验证 final 顺序，`apps/im-server/tests/tenancy.test.ts:44-47` 覆盖私人联系人拒绝，适合作为扩展 seam。性能、Unicode、多页、批量查询数与 SQL 等价均进入 worker 退出标准。真栈 runbook 的 Agent 模式有 R1-W1 缺口。
8. **Context 影响判断。** 依 `agent-context-review` 的 Design Review 影响规则检查 `model.check` 及群聊 revalidation 周边：本方案改变用户输出传输粒度，不改变 runtime 输入、工具/Skill、历史选择或 revalidation 注入文本。modelCheck 的 pending/confirmed 发布事实是宿主 fallback 判断，设计要求先 flush，未发现新增模型上下文表面，故不扩展成全量 Context 审查。未捕获真实 provider 请求或运行模型，不声称模型行为已验收。

### 历史问题闭环

首轮，无历史问题。

### Issues

#### R1-W1 — daily 默认全部为 Global，runbook 未准备受改的普通流式 Agent

- 严重度：WARNING；证据状态：CONFIRMED（验收设计缺口，非候选代码缺陷）。
- 位置：`design.md:56-58`，关联 M1 reviewer 退出标准 `design.md:64`。
- 证据：`docs/development/worktree-runtime.md:49` 明确 daily 四个角色均为 Global；`scripts/e2e_daily.py:53-76` 从 `e2e-global` 复制并替换全部 Agent 配置，`config/e2e/daily/team.yaml` 未覆盖 `work_mode`。真实消费入口 `packages/personal-assistant/src/single-thread.ts:43` 对非 `single_thread` 直接返回。
- 后果：按现有 runbook 向 P/E/Q 或 PA 发较长私聊，只能验到 Global/显式发送路径；即使回复完整也不能证明本次普通流式合并、最终 flush 或群聊草稿抑制没有回归。设计又限定测试配置仅来自 daily，未给 reviewer 可命中目标的场景增量。
- 修订要求：保留 daily 隔离基线，在当前副本通过正常产品配置入口准备至少一个 `work_mode=single_thread` 的普通 Agent，明确私聊、群聊、显式发送所使用的对象及可用真实模型；在交接中记录其 Agent ID、工作模式、会话 ID 与配置差异。普通私聊验收需确认确实观察到该 Agent 的 `message.delta` 和最终 `message.completed`，不能以仅有显式发送完成消息的 Global 成功替代。无需修改全局 daily 模板或扩展产品范围。

### Recommendations

无。

### Author Resolutions

- R1-W1: accepted。daily 默认 Global 无法命中普通流式，已在 design Runbook 明确通过产品接口创建 single_thread Agent，交接身份/会话/配置，并观察实际 delta/completed；不改 daily 模板。请求独立复核此验收前置修订及其影响。

## Round 2

### Metadata

- reviewer: `/root/design_review`（沿用 Round 1 独立 reviewer）
- reviewer target: `design.md:52-64` 及 Round 1 Author Resolutions
- review_mode: `closure`
- mode_reason: 唯一修订为 R1-W1 的验收 Agent 前置与输出证据；核心方案、需求、接口、milestone 和代码均未变化，适合定向核实闭环。
- baseline: `main` / `63f58270ccb4d87de7f5abcad754c87633561742`；受审文件仍为未提交设计产物，未见产品代码修改。
- started_at: `2026-10-27T11:53:37+08:00`
- completed_at: `2026-10-27T11:53:50+08:00`
- duration: 13 秒

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**。

### Coverage 与证据

- `retained_from: Round 1`：现状、三条技术方案、架构职责、消息与权限保真、no spec delta、索引初始化及 Context 影响判断不变，沿用 Round 1 的实际代码与 current spec 证据。本轮不重复全量审查。
- 新 Runbook 明确 daily 全部为 Global，要求在本次隔离实例新增普通 `single_thread` Agent；普通长回复和群聊使用该对象，并交接 Agent ID、模式、会话与配置增量，要求普通私聊观察 `message.delta` 和 `message.completed`。这与 `single-thread.ts:43` 的实际选择条件一致。
- 产品配置链支持显式创建工作模式：`apps/im-server/src/control.ts:518-519` 验证合法模式，创建参数在 `control.ts:741` 接纳 `work_mode`；因此不需要修改 daily 模板或绕过产品运行时。新增验收资料留在隔离副本，符合 `worktree-runtime.md` 的场景增量规则。
- Global 显式发送是真栈兼容回归；普通模式的显式发送哨兵抑制继续由设计保留的 `packages/personal-assistant/tests/interactive-replies.test.ts:43-61` 覆盖，不能用 Global 成功声明该内部回归已验证。R1 的 worker 回归与最终 flush 退出标准继续生效。
- 本轮只验证验收方案可命中目标链路；尚未实施、跑测试或运行真实模型，不提前宣称验收通过。

### 历史问题闭环

- **R1-W1 — closed。** Author Resolution 接受问题并补充普通 Agent。当前 `design.md:58` 已明确模式、对象、隔离配置增量及实际 delta/completed 证据；普通流式不再依赖 Global 阵容替代。未发现此局部修订引入新的实质问题。

### Issues

无。

### Recommendations

无。

### Author Resolutions

Round 2 已核实：R1-W1 修订覆盖实际 single_thread 前置，无未解决实质问题；接受 Approved，设计冻结进入实施。
