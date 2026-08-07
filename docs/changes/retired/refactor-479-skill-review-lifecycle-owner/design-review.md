# Design 评审：refactor-479-skill-review-lifecycle-owner

**结论**：Issues Found

本轮按 v2 重新从生产装配入口、canonical spec、首文档、delta-spec 与本地 Claude Code
源码独立取证，不沿用 v1 结论。v2 已实质修复上一轮的 cross-thread admission、SDK seam、
Gateway live catalog 与 auxiliary primitive 选型；但 exact-root authority 和
cancel-settle 仍各有一个更底层的可绕过边界，且 SDK delta 中有三条 Scenario 把内部实现写成
canonical 可观察契约，因此尚不能进入实施。

## v1 问题复核

| v1 问题 | v2 结论 | 证据 |
|---|---|---|
| CRITICAL：同步 tool worker 无 owner-loop admission 契约 | ✓ 已修 | D1 明确 condition lock、`NEW/OPEN/CLOSING/CLOSED/FAILED`、入队与 wake 同一临界区、失败回滚和 `enqueue -> accepted` 后才 reset（`design.md:86-103`）；这与真实 `asyncio.to_thread` 入口和 counter reset 点一致（`src/agent/core/tools/registry.py:348-350`；`src/agent/platform/tools/builtins/skill_view.py:166-179`）。 |
| CRITICAL：`writable_skill_root` 没有约束实际 writer | ✗ 方案方向已改对，但 authority 仍可被同名 tool override 绕过 | D4 已把 exact root/name/action 放进 internal capability（`design.md:169-195`），但 D5 继续使用共享 ToolRegistry；生产装配允许 consumer、workspace 和 deployment tool 以同名覆盖 built-in（`src/agent/sdk/kernel.py:721-762,825-841`）。见 Issue 1。 |
| CRITICAL：30 秒 timeout 后先 release、底层 run 可能仍活着 | ✗ carrier 顺序已补齐，但 `cleanup_ack` 的实际作用域不足 | D5/D6 已正确处理“successful result 可早于 ack”并要求成功/失败都等 ack（`design.md:197-236`）；然而现有 ack 只覆盖 asyncio carrier，不覆盖被取消后仍运行的 `to_thread` worker。见 Issue 2。 |
| CRITICAL：产品 seam 泄漏 core trigger 且 no delta | ✓ 已修 | D2 选择 build-time SDK-owned DTO/Protocol，并明确 internal↔SDK 映射及不新增 configure/drain 方法（`design.md:105-143`）；delta 用 MODIFIED 锚定 canonical 两条既有 Requirement（`specs/kernel/sdk-boundary.md:6-106`）。 |
| WARNING：Gateway catalog snapshot 更新 owner 未定 | ✓ 已修 | D3 选定 build 前创建 `LiveAgentCatalog`，policy 每次 `values_snapshot()`、不缓存/替换（`design.md:157-167`）；现有 catalog 是锁保护 copy-on-write snapshot，config sync 会 republish（`src/personal_assistant/gateway/agent_catalog.py:70-105`；`src/personal_assistant/gateway/agent_config_sync.py:549-563`）。 |
| WARNING：重造 normal RunRegistry/EventHub terminal waiter | ✓ 已修 | D5 明确复用 `KernelExecutor.start_auxiliary` / `AuxiliaryHandle`，不经 normal `Kernel.submit` / EventHub（`design.md:197-211`）；现有 handle 已提供 result/cancel/ack（`src/agent/core/runs/executor.py:90-120`）。 |

## 核实台账

### 现状断言、既有约束与可复用能力

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状：`skill_view` 在同步 worker 内 bump usage，enqueue 接受后才 reset | 从 ToolRegistry 正向追到 built-in | ✓ Registry 以 `asyncio.to_thread(tool.run, ...)` 执行同步工具（`src/agent/core/tools/registry.py:145-169,348-350`）；`skill_view` 只在 callback 返回 truthy 后 reset（`src/agent/platform/tools/builtins/skill_view.py:141-179`）。 |
| 现状：queue/dedupe/running/scheduler 在 AgentEngine | 追当前 enqueue→pop→finish | ✓ 四类状态和 callback 都在 `AgentEngine`（`src/agent/core/agent/runtime.py:861-930`），identity 为 normalized root + name（同文件 `:2193-2208`）。 |
| 现状：SDK 拥有 drain/runner/finally finish | 追 Kernel 产品可见方法 | ✓ `run_queued_skill_batch_reviews` pop 后逐 trigger 调 platform，并在 finally finish；scheduler setter 也公开在 Kernel（`src/agent/sdk/kernel.py:1749-1785`）。 |
| 现状：platform 拥有 evidence/prompt/mark-reviewed | 追完整 review 事务 | ✓ evidence 与 curator state 都从 trigger root 派生，analysis 后 mark reviewed（`src/agent/platform/background/skill_batch_review.py:57-112,122-162`），prompt 与 allowlist也在该模块（同文件 `:15-16,165-190`）。 |
| 现状：CLI/Gateway 重复 create-session→submit→300×0.1s polling | 分别追两产品 production helper | ✓ CLI 为 `src/coding_cli/product.py:239-266`，Gateway 为 `src/personal_assistant/gateway/runtime.py:86-113`；两边 scheduler 均直接 `asyncio.create_task`（CLI `:183-196`；Gateway `:526-548`）。 |
| 现状：KernelExecutor/AuxiliaryHandle 已有 admission/result/cancel/ack/shutdown owner | 追 auxiliary handle 与 executor finally | ✓ handle 提供 cancel/result/cleanup event（`src/agent/core/runs/executor.py:90-120`），executor finally 移除 target 后置 ack（同文件 `:443-480`），RunsRegistry shutdown 统一调 executor（`src/agent/core/runs/registry.py:146-166`）。但 ack 只证明 carrier unwind，不证明嵌套 `to_thread` worker 结束，见 Issue 2。 |
| 现状：当前 `writable_skill_root` 只是 equality guard | 追 review 到 `skill_manage` writer | ✓ platform 仅比较 root（`src/agent/platform/background/skill_batch_review.py:66-75`）；正常 `skill_manage` 仍按 scope 选 writer（`src/agent/platform/tools/builtins/skill_manage.py:403-423`；`src/agent/core/skills/root_resolver.py:27-39`）。 |
| 约束：产品只能经 `agent.sdk` 注入事实 | 核顶层架构与 SDK canonical | ✓ `SPEC.md:124-131,163-168` 与 `docs/specs/kernel/sdk-boundary.md:14-54` 都逐字要求产品只依赖 SDK、core 不反向依赖 platform/product。 |
| 约束：产品拥有 `.nanocode` / `.nanoassistant`、global/compat roots | 核两产品工厂 | ✓ CLI roots 在 `src/coding_cli/product.py:30-43`，Gateway roots 在 `src/personal_assistant/product.py:39-55`；内核只接收 consumer-supplied roots（`docs/specs/kernel/sdk-boundary.md:56-70,134-138`）。 |
| 约束：Gateway workspace catalog 是 live fact | 从 composition 追 config sync | ✓ 当前 composition 先 build kernel、后建 catalog（`src/personal_assistant/gateway/composition.py:206-214`），catalog 本身支持原子 snapshot（`agent_catalog.py:70-105`），config sync 运行中 republish（`agent_config_sync.py:549-563`）；因此 D3 的构造顺序确实需要调整且可实现。 |
| 约束：identity 是 owning root + skill name | 追当前 key | ✓ `_skill_batch_review_key` 规范化 root 后与 name 组合（`src/agent/core/agent/runtime.py:2193-2208`）；canonical 也要求 skill_view 返回真实命中 location（`docs/specs/kernel/skills.md:43-74`）。 |
| 约束：enqueue 同步、快速、best-effort，当前 turn 不等待 | 追调用返回值与 spec | ✓ `skill_view.run` 只同步调用 callback 并继续返回内容（`src/agent/platform/tools/builtins/skill_view.py:166-188`）；首文档要求异步且不阻塞（`motivation.md:49-57`）。 |
| 约束：deadline 30 秒，cancel/close 后先 settle 再重试 | 追现有边界与首文档 | ✓ 两产品现状确为 300×0.1s（CLI `product.py:257-266`；Gateway `runtime.py:104-113`），首文档把“30 秒后 cancel+确认 cleanup，再 release”写成验收约束（`motivation.md:69-74`）。 |
| 约束：evidence/read/write/curator state 必须 exact-root，不 fallback | 核首文档同名与 compat Scenario | ✓ `motivation.md:59-67` 要求三类副作用同根、read-only compat 明确 skip；现有 platform 已让 evidence/state 走 trigger root（`skill_batch_review.py:66-83,104-107`），缺口只在 write authority。 |
| 约束：allowlist 仅 `skill_view` / `skill_manage`，prompt/threshold 不变 | 核当前实现与非目标 | ✓ 当前 allowlist/prompt 在 `skill_batch_review.py:15-16,165-190`，threshold 为 20 且只对 auto sources触发（`src/agent/core/skills/usage.py:18-20`）；首文档非目标在 `motivation.md:43`。 |
| 可复用：platform review 深化为 queue→finish owner | 做删除测试与分层核对 | ✓ evidence/prompt/update/state 已在一个 platform 事务；补 lifecycle 会集中而非搬运复杂度，SDK 装配仍保持 `platform → core`、`sdk → core + platform`（`SPEC.md:126-131,163-168`）。 |
| 可复用：复用 AuxiliaryHandle，不造 EventHub waiter | 搜已有同类 primitive | ✓ `AuxiliaryHandle` 已有 typed result/cancel/cleanup（`executor.py:90-120`），design 已选它（`design.md:197-211`）；但其 ack 语义须深化到真实 tool worker，见 Issue 2。 |
| 可复用：internal capability 随 TurnRequest→ToolContext | 核当前装配可插入点 | ✓ 当前 build 先造 engine/executor/directory，再注册 tool 并 bind registry（`src/agent/sdk/kernel.py:600-684,700-794`），有真实 composition seam；但若检查只存在可替换 built-in 内，authority 可绕过，见 Issue 1。 |
| 可复用：产品 policy 改为 build-time SDK Protocol | 核 SDK boundary 与产品工厂 | ✓ canonical 允许 build-time consumer-supplied extension（`docs/specs/kernel/sdk-boundary.md:56-84,95-114`），两产品已各自经工厂调用 build_kernel（CLI `src/coding_cli/product.py:121-145`；Gateway `src/personal_assistant/product.py:410-434`）。 |
| 删除目标：engine queue + SDK/product polling glue | 搜所有当前 owner | ✓ design 枚举的删除面覆盖当前四处 owner（`design.md:251-259`；当前实现见 `runtime.py:861-930`、`kernel.py:1749-1785`、CLI `product.py:183-266`、Gateway `runtime.py:526-590`）。 |
| 相关历史/relations：476/477 无逻辑前置，热点集成序列化 | 对首文档与 milestone 计划 | ✓ 首文档 Relations 无 Depends/Blocks（`motivation.md:5-9`），design 明确开发并行、kernel/CLI lane 串行（`design.md:328-336`），没有虚构逻辑依赖。 |
| Claude Code 对照：setup 一次，observer 内部闭环 | 直接读本地 CC 源码 | ✓ `initSkillLearning` 一次注册 hook/maintenance（`/Users/czj/Repos/opensource-hub/claude-code/src/services/skillLearning/runtimeObserver.ts:75-104`），observer 自己完成 ingestion、throttle、backend、upsert/evolve（同文件 `:117-253`），production setup 只初始化一次（`/Users/czj/Repos/opensource-hub/claude-code/src/setup.ts:281-297`）。design 只借鉴 owner 形态，未误宣称语义等价。 |
| canonical 与代码是否存在未上报 drift | 对相关 `skills.md` 与真实 schema/root resolver | ✗ canonical 写 `scope: "agent" | "pa"`（`docs/specs/kernel/skills.md:84-96`），生产 schema/resolver 写 `"agent" | "global"`（`src/agent/platform/tools/builtins/skill_manage.py:234-237`；`src/agent/core/skills/root_resolver.py:27-39`）。本 unit 触及 `skill_manage` 与 global-root 权威却未在现状分析上报，见 Issue 4。 |

### 编号决策

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| D1：lifecycle 自有 coordinator、任意线程同步 admission | 核状态、失败回滚、counter 与 read-only terminal | ✓ 状态机、单 lock/condition、dead coordinator 回滚、仅 accepted reset 都已拍死（`design.md:86-103`）；read-only/unresolved 接受后 terminal skip 并 release，counter 已 reset，下一批达到 threshold 才再解析，避免 hot-loop。 |
| D2：build-time SDK policy 是唯一产品 seam | 核 ownership、映射、调用时机和替换语义 | ✓ 四个 frozen SDK DTO/Protocol、internal↔SDK adapter、exact root 校验、`None` 行为、同步线程安全要求和“不新增 configure/drain”均明确（`design.md:105-143`），与 SDK 硬边界一致。 |
| D3：CLI/Gateway 封闭 root 分类与 live catalog | 逐类核 writable/read-only 与动态更新 owner | ✓ CLI workspace/global/compat 四格和 Gateway live snapshot 策略均无 fallback（`design.md:145-167`）；Gateway 明确 build 前 catalog、每次 resolve 读 snapshot，不再有 v1 的两种实现。 |
| D4：capability 是真实 exact-root tool authority | 攻实际 registry precedence 与 dispatch | ✗ capability 只由具体 built-in 检查，但共享 registry 按 name dispatch（`src/agent/core/tools/registry.py:129-169`），而后注册层合法 replace 同名 built-in（`src/agent/sdk/kernel.py:721-762`）。allowlist 仍可选中不检查 capability 的 override，见 Issue 1。 |
| D5：复用 AuxiliaryHandle，结果后等 cleanup ack | 核 result/ack 顺序、normal run 可见性和 session owner | ✗ 不经 normal RunRegistry/EventHub 的选择正确，且成功 result 早于 executor finally/ack 的事实已被正确处理（`src/agent/core/runs/executor.py:451-476`）；但 existing ack 不涵盖被取消的 `to_thread` worker，不能支撑“carrier/tool cleanup 都完成”的结论，见 Issue 2。 |
| D6：timeout/cancel/close 先 cancel-settle 再 release | 追 force cancel 到最深执行单元 | ✗ lifecycle/executor/identity 顺序写清了（`design.md:213-236`），但 force cancel 只取消 carrier task；`asyncio.to_thread` 的底层线程不会被取消或 join（`registry.py:348-350`；`tool_executor.py:215-229,330-345`）。现有 ack 后 release 仍可能与旧 writer 重叠，见 Issue 2。 |
| D7：两阶段构造 NEW→bind tools→start→return | 对当前 build 顺序和 production admission 窗口 | ✓ 当前真实 cycle 是 registry 在 engine/directory/executor 后构造并 bind（`src/agent/sdk/kernel.py:600-684,700-794`）；D7 规定 start 成功才返回、失败清理 executor/resources，且 build 返回前无 production tool caller（`design.md:238-249`），两个 worker不会猜出不同 post-configure seam。 |
| D8：maintenance 保留，产品 drain/scheduler 全删 | 区分 deterministic maintenance 与即时 batch queue | ✓ `run_skill_maintenance` 当前是独立 deterministic scan（`src/agent/sdk/kernel.py:1725-1747`）；D8 删除的正是 engine/SDK/product 四处 batch owner（`design.md:251-259`），不会保留双 queue。 |

### 首文档约束

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 澄清 Q1：中途不逐项找用户确认 | 查是否遗留待用户拍板项 | ✓ D1-D8 均给唯一选择，无 TBD/A-or-B（`design.md:84-259`）。 |
| 澄清 Q2：产品 workspace 规则不下沉为 kernel 常量 | 核 D2/D3 分层 | ✓ SDK只持中立 DTO/Protocol，路径分类全部留在 CLI/Gateway policy（`design.md:105-167`）。 |
| 澄清 Q3：产品不注入 asyncio scheduler/drain | 核 lifecycle owner 与删除面 | ✓ D1 自有 coordinator，D8 删除产品 scheduler/drain（`design.md:86-103,251-259`）。 |
| 目标：单 lifecycle 拥有 admission→finish，产品仅 build-time policy | 对 D1-D8 数据流 | ✗ owner 图和接口已覆盖，但 D4 authority 可绕过且 D6 settle 未到最深 worker，故“exact-root + cancel-settle”两项尚未真正成立（`motivation.md:35-41`；Issues 1-2）。 |
| 非目标：threshold 不变 | 搜新阈值/计数语义 | ✓ 没有新增阈值；D1 只规定 accepted 时 reset（`design.md:92-103`），沿用 `usage.py:18-20`。 |
| 非目标：review prompt 不变 | 对现 prompt 与 capability mode | ✓ D4 明确保留 `scope="agent"` 字面、在 capability mode 解释为已绑定 target（`design.md:184-191`），与现 prompt `skill_batch_review.py:177-190` 对齐。 |
| 非目标：自动演进规则不变 | 搜 selection/review completed 规则 | ✓ 只移动 review owner；completed 才 mark reviewed，未增加演进判据（`design.md:197-211`）。 |
| 非目标：目录约定不变 | 对产品 root 表 | ✓ D3 沿用 `.nanocode/.nanoassistant/.codex/.claude` 既有目录（`design.md:145-164`；产品常量见 CLI `product.py:30-43`、PA `product.py:39-55`）。 |
| 非目标：用户启停方式不变 | 核 SDK/Runbook | ✓ build-time policy 不新增用户命令/UI，Runbook 继续使用既有 e2e 起停（`design.md:312-326`）。 |
| Req 自动复盘：达到阈值异步触发且不阻塞 | 追真实入口到 D1 | ✓ `skill_view` 只做同步快速 enqueue，coordinator 承担 policy/I/O/analysis（`design.md:92-103`），覆盖 `motivation.md:49-54`。 |
| Scenario：同步 tool worker 不依赖 asyncio loop | 从 `to_thread` 入口攻击 | ✓ condition notify 不要求 worker loop；NEW/closing/failure 返回 False并不 reset（`design.md:86-103`），覆盖 `motivation.md:55-57`。 |
| Req 产品工作区隔离：同名 skill 三类副作用同根 | 追 evidence→tool→state | ✗ evidence/state 设计同根，builtin capability 也意图同根（`design.md:181-195`），但同名 tool override 可绕过 write authority，故该用户结果仍不可证明，见 Issue 1。 |
| Scenario：compat read-only 不 fallback | 核 selection、counter 与 run admission | ✓ D3 分类 compat 为 read-only，D1 把它作为 accepted terminal skip，D4 明确不创建 auxiliary run且不 fallback（`design.md:101-103,145-164,193-195`）。counter 在 accepted 时 reset，下一批才重试，语义完整。 |
| Req/Scenario 失败隔离：失败/取消/30 秒 timeout 先 cleanup 后 release | 追 cancellation 到同步工具线程 | ✗ D5/D6 正确覆盖 successful-result-before-ack 和 carrier ack 顺序，但 ack 不证明底层 sync tool结束，故 `motivation.md:69-74` 的 cleanup 不变量仍不成立，见 Issue 2。 |
| 影响范围 | 对生产调用链逐项查落点 | ✓ engine、SDK、platform、TurnRequest/ToolContext、CLI、Gateway、策略测试和 SDK delta 都在 M1 范围（`motivation.md:76-85`；`design.md:334-336`），未漏明显生产 owner。 |
| 迁移/回滚：先锁契约，再单 owner，最后删旧 glue；不得双 scheduler | 核 D7/D8与风险矩阵 | ✓ start 成功才返回、整体 rollback、明确禁止 EventHub waiter/双 queue（`design.md:238-259,299-310`）。但测试矩阵还须加入 override bypass 与底层 worker completion，见 Issues 1-2。 |

### delta-spec

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| MODIFIED「内核只经 agent.sdk 暴露」 | 锚 canonical 标题、检查是否保留原 Scenario | ✓ 精确锚定 canonical 同名 Requirement（`docs/specs/kernel/sdk-boundary.md:14-54`），保留原 6 类 Scenario并新增 policy ownership（delta `specs/kernel/sdk-boundary.md:8-51`），用 MODIFIED 正确。 |
| Scenario：产品越界 import 被拦 | 对 canonical/contract 语义 | ✓ 忠实保留原 Scenario，THEN 是产品源码 contract 可观察结果（delta `:21-24`）。 |
| Scenario：SDK 不上行依赖产品 | 对依赖硬规则 | ✓ 与 `SPEC.md:163-168` 及 canonical `sdk-boundary.md:28-30` 一致（delta `:26-28`）。 |
| Scenario：core 不依赖 platform/product | 对依赖硬规则 | ✓ 忠实保留且未借机放宽（delta `:30-32`）。 |
| Scenario：policy 类型由 SDK 拥有 | 核消费者视角与 internal 泄漏 | ✓ `__module__` 与产品源码 import 是 SDK consumer/contract 可观察结果（delta `:34-37`），四类型 ownership 与 D2一致。 |
| Scenario：新增/缺失导出被 allowlist 拦 | 对现精确表面规则 | ✓ 忠实保留并把四个新增名字纳入（delta `:39-41`；canonical `:37-44`）。 |
| Scenario：既有豁免逐字受控 | 核是否静默删旧豁免 | ✓ 五个既有豁免完整保留（delta `:43-47`；canonical `:46-49`）。 |
| Scenario：typing alias 不计入豁免 | 核新 Protocol 归类 | ✓ 保留 `CanUseToolFn` 并把 SDK-owned Protocol纳入同一 ownership 规则（delta `:49-51`）。 |
| MODIFIED「装配与会话分两层，内核产品中立」 | 锚 canonical、检查旧 Scenario | ✓ 精确锚定 canonical `docs/specs/kernel/sdk-boundary.md:56-93`；原“零前置/三应用/共享 catalog/稳定方法集”四个 Scenario均保留，新增 build-time policy 行为（delta `:53-106`）。 |
| Scenario：应用零前置调用直接装配 | 核消费者可观察结果 | ✓ 返回 Kernel 可立即创建 session、无需后置 scheduler/drain，是 SDK consumer 可观察行为（delta `:73-77`）。 |
| Scenario：三类应用对内核同构 | 核产品分支与 ownership | ✓ 忠实保留 canonical 语义，产品差异仅来自传入对象/policy（delta `:79-82`）。 |
| Scenario：工具目录共享、会话选子集 | 核是否静默删旧行为 | ✓ 原 Scenario 完整保留（delta `:84-86`）。 |
| Scenario：policy 在 Kernel 返回前可用 | 检查 THEN 是否只写 SDK consumer 可观察结果 | ✗ `enqueue`、`NEW/unbound lifecycle` 是内部协议/状态，不是 SDK consumer 可观察结果（delta `:88-92`），违反 canonical spec 层纪律，见 Issue 3。 |
| Scenario：policy 不能重定向同名 root | 检查 THEN 是否只写外部结果 | ✗ “adapter 校验”“不创建 exact-root capability”把内部类和实现动作写进 Scenario（delta `:94-97`）；应只钉死“不在 R2 读取/写入/标记且本轮 skip”，见 Issue 3。 |
| Scenario：未提供 policy 时不新增后台 owner | 检查 THEN 是否只写外部结果 | ✗ “不启动 coordinator、ToolContext 无 callback”是内部实现（delta `:99-101`）；应描述消费者能观察到的无自动 review 副作用，见 Issue 3。 |
| Scenario：Kernel 稳定方法集不扩张 | 核既有公开方法 | ✓ 不新增 configure/drain/scheduler，忠实保留 canonical 稳定表面（delta `:103-106`；canonical `:86-93`）。 |
| IM no spec delta | 查 IM 是否进数据流 | ✓ IM 不调用 kernel且本 unit 无 IM 数据/交互变化（`SPEC.md:147-151,163-168`；`design.md:292-297`）。 |
| Gateway no spec delta | 查终端用户行为是否变化 | ✓ D3 是维持动态 workspace/异步 review不变量，未新增 Gateway 对外行为；内部装配变化可明确 no delta（`design.md:145-167,292-297`）。 |
| CLI no spec delta | 查终端用户行为是否变化 | ✓ CLI入口、目录、阈值、prompt不变，仅移除内部 polling/scheduler（`design.md:145-155,251-259,292-297`）。 |

### Milestone、整体与验收

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| M1：单一 queue→cleanup 垂直切片 | 核拆分理由、范围交集和两轨退出 | ✗ 单 M1 的选择正确且 `[reviewer]`/`[worker]` 两轨齐全（`design.md:328-336`），但当前退出标准只要求 action/name guard 与 executor/lifecycle 计数归零；它没有钉死“同名 override 仍不能绕过 capability”及“cleanup_ack 时真实 `to_thread` worker 已结束”。按现标准实现可全绿仍违反两条核心 Scenario，见 Issues 1-2。 |
| Runbook 与验收前置 | 核常驻服务起停、健康检查和真实 fixture | ✓ 给出标准 e2e 起停/health、真 CLI/Web IM入口、workspace/global/compat/同名 root 与可控 timeout fixture（`design.md:312-326`）；补 Issues 1-2 的攻击断言后可直接用于 reviewer。 |
| 上层综述/图 | 退到人类 reviewer 视角通读 | ✓ Before/After、总览图和 D1-D8 能直接看出 owner/policy/auxiliary/capability 数据流（`design.md:66-83`），未被 grounding 细节淹没。 |
| 接口与数据流闭合 | 对每个来源/出口/调用方 | ✗ trigger→lifecycle→policy→port→executor 主链闭合（`design.md:261-290`），但图把 capability→tools 画成 authority，实际共享 registry precedence 允许绕过；cleanup_ack→release 也缺 nested worker completion，见 Issues 1-2。 |
| 风险与回退 | 核风险是否有可验证应对 | ✗ cross-thread/catalog/build-failure/整体回退具体；但“root capability 漂移”矩阵未覆盖 same-name tool override，“carrier orphan”只断言 executor target/lifecycle running 为零，无法发现 thread worker 仍活着（`design.md:299-310`）。 |

## 架构进攻

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | platform lifecycle + SDK adapter + 产品 policy | ✓ 走完无存活发现。platform 拥有 evidence/update/finish，SDK只做边界映射，产品只拥有路径/catalog事实，组合后仍是 `platform → core`、`sdk → core + platform`，没有反向依赖（`SPEC.md:124-131,163-168`）。 |
| 该不该存在 | lifecycle、policy Protocol、auxiliary port、capability | ✓ 走完无多余抽象。删 lifecycle 会把 queue/run/finish 重新散回产品；删 policy会迫使 kernel 内置产品路径；auxiliary port是在 SDK composition 把既有 executor适配给 platform事务；capability承担真实隔离需求。 |
| 深还是浅 | `AuxiliaryHandle.cleanup_ack` 被当成完整 cancel-settle | ✗ 现 handle 隐藏的是 carrier task，不是其内部 `to_thread` worker；直接把 ack 当“tool cleanup完成”是浅复用。长期代价是 executor指标显示零 target、lifecycle也 release identity，而旧同步 writer仍能在后台落盘，形成最难复现的同根并发写与 shutdown 后副作用。见 Issue 2。 |
| 治本还是补丁 | 在可替换 built-in 内检查 `SkillReviewCapability` | ✗ 检查落在可以被同名覆盖的叶子工具，而不在不可绕过的 dispatch/trusted-registry边界，是对正常路径的补丁。长期代价是任何 consumer/workspace tool precedence 调整都会重新打开 exact-root漏洞，allowlist 名称被误当成安全边界。见 Issue 1。 |

## Issues

- [CRITICAL] [D4/D5；产品工作区隔离 Requirement；风险矩阵] **`SkillReviewCapability`
  不是不可绕过的 authority：共享 ToolRegistry 允许同名工具替换受信 built-in。** D4 只规定
  `SkillViewTool` / `SkillManageTool` 在 capability mode 检查 exact root/name/action
  （`design.md:181-195`），D5 又明确 auxiliary session 复用现有 engine/tool registry并只按
  名字 allowlist（`:197-205`）。生产先注册这两个 built-in（`src/agent/sdk/kernel.py:825-841`），
  随后 consumer tools、workspace `.nano/tools`、deployment tool roots 都以 `replace=True`
  覆盖同名条目（同文件 `:721-762`）；`ToolRegistry.execute` 最终只按 name 取当前实例
  （`src/agent/core/tools/registry.py:129-169`）。同名 override 不必读取 capability，便可写任意
  root/action；same-name override 还是仓库明确支持并有回归测试的行为
  （`tests/unit/agent/test_kernel_nano_tools_override.py:1-8,35-53`）。不改时，evidence/curator state
  在 R1，模型实际调用的 `skill_manage` 却可写 R2，核心同名隔离 Scenario仍会复发。design 必须拍死
  不可绕过的边界：例如 auxiliary review 使用固定的 trusted built-in registry/实例，或在不可被
  tool override 替换的 registry/dispatch 层强制 capability；单靠 tool name allowlist 不构成权限。
  M1 必须加入 consumer/workspace/deployment 三层同名 `skill_view` / `skill_manage` override 攻击测试。

- [CRITICAL] [D5/D6；失败隔离 Requirement；shutdown] **现有
  `AuxiliaryHandle.cleanup_ack` 只确认 asyncio carrier 已 unwind，不确认被取消的同步工具线程
  已结束。** Executor 在 `submit_turn` 的 task 被取消后，会在 finally 里移除 target并立即 set
  ack（`src/agent/core/runs/executor.py:443-476`）；但同步工具实际由
  `asyncio.to_thread` 执行（`src/agent/core/tools/registry.py:348-350`），取消 await 它的 task
  不会终止或 join 已运行的 thread。`StreamingToolExecutor` 的 cancel/discard 也只取消 child task
  并标记完成（`src/agent/core/agent/tool_executor.py:215-229,330-345`）。用现有
  `KernelExecutor` + 一个阻塞 `to_thread` tool 做只读 probe，可稳定得到
  `cleanup_ack=True, tool_worker_finished=False, active_target_count=0`。因此 v2 对
  successful-result-before-ack 的处理是正确的，但 timeout/force-cancel 路径仍会在旧 writer可能继续
  落盘时 release identity并允许新 review，直接违反 `motivation.md:71-74`。design 必须把 settle
  定义延伸到真实同步 tool future/thread：ack 只有在嵌套工具执行已完成/被可证明终止后才能解封
  identity；若需要新一层 tracked tool future、shield+join 或 auxiliary 专用可取消执行 owner，
  要在 design 拍板，而不能把现有 carrier ack 重新命名为 tool cleanup。M1/风险断言须直接检查
  worker finished 与无 shutdown 后写入，不能只看 executor/lifecycle计数为零。

- [CRITICAL] [kernel delta-spec；Scenario 可观察性红线] **三条新增 SDK Scenario 把内部实现
  机制写成 canonical THEN。** `policy 在 Kernel 返回前可用` 钉了 internal enqueue 与
  `NEW/unbound lifecycle`（delta `specs/kernel/sdk-boundary.md:88-92`），root mismatch Scenario
  钉了 adapter 与“不创建 exact-root capability”（`:94-97`），`policy=None` Scenario 钉了
  coordinator 和 ToolContext callback（`:99-101`）。这些不是 SDK consumer 可观察结果；收尾照此
  归并会把内部类/状态永久冻结成对外契约，下一次无行为变化的 owner 重构也会被误判 breaking change，
  worker还会写实现耦合 contract test。保留 MODIFIED target 与行为意图，但把 THEN 改成消费者结果：
  build 返回后第一条 threshold 无需后置调用即可异步复盘；R1→R2 mismatch 不在 R2
  读/写/标记且本轮 skip；`policy=None` 时不产生自动 review副作用。内部 NEW/coordinator/
  ToolContext/capability只留在 design 与 worker test。

- [WARNING] [现状分析；canonical grounding] **相关 `skill_manage` scope 契约与生产代码已漂移，
  design 未上报。** canonical 仍写 `scope: "agent" | "pa"` 及 PA root
  （`docs/specs/kernel/skills.md:84-96`），生产 schema和 resolver 已是
  `"agent" | "global"`（`src/agent/platform/tools/builtins/skill_manage.py:234-237`；
  `src/agent/core/skills/root_resolver.py:27-39`）。本 unit 正在改 `skill_manage` capability mode、
  product-global root 与相关 contract；不说明 authority 时，worker可能按 canonical恢复 `pa`，
  也可能按代码继续 `global`，最终 review、普通交互和收尾 spec各用一套词。design 应在现状分析明确
  drift，并拍板“本 unit 一并归并修正”或“现状代码为实施基线、另 unit 修 canonical”，避免静默带入。

## Recommendations

- 保留 v2 的 D1、D2、D3、D7、D8；它们已经把上一轮的线程入口、SDK seam、动态 catalog 与构造时序
  拍清，无需换回产品 scheduler 或 normal EventHub waiter。
- 修订 D4/D5/D6 后，把风险矩阵从“正常 built-in + carrier计数”升级成两类 adversarial
  proof：同名 override 不能绕过 authority；timeout/close 的 cleanup ack 时真实同步工具 worker
  已结束且之后无文件副作用。
- delta 只需把三条 internal THEN 改写为 SDK consumer 可观察结果，不需要扩写更多实现步骤。
