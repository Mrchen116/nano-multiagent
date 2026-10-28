# Verification Report: bugfix-674-skill-usage-statistics

> Validation snapshot: `ff326c351d104447028f4b185740ab6d6be55de6 → 28b205259d60017679f2844d1fa5280c3ebc8802`
> Modes: full implementation verification + corrected-delta reconciliation; independent full code review.
> Round 1, 2026-10-28. Shared worktree: `/Users/czj/.codex/worktrees/skill-usage-statistics/nano-multiagent`; branch `codex/bugfix-674-skill-usage-statistics`.

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 实现范围 1/1；真实 Web 对照、适用完整 CI 证据待交接，尚不宣布 milestone 完成 |
| Correctness | 6/6 delta scenarios 静态与最低层回归映射成立；尚不代替真实产品验收 |
| Coherence | Followed；直读 API 的离线 503 是已核实并记录的 current grounding 纠正 |
| Code review | 完整固定 diff 已审，无存活代码 finding：`[]` |
| Corrected delta | aligned（针对本固定实现；current spec 尚待主流程归并） |
| Verdict | pending_evidence；不能据本轮记录宣布 Ready for PR |

本轮只写本报告，没有修改实现、测试或设计，没有提交、启动服务、调用生产或真实外发。审查期间共享现场出现的 `apps/im-server/tests/e2e/control-work.test.ts` 未提交修改不属于固定快照，未纳入本轮结论且未改动。

## Completeness

- **实现：M1 1/1。** 覆盖存储、宿主归属、IM 两个公开入口、Web 和 iOS。没有发现遗漏实现或架构边界违反。
- **复用的执行证据：** `M1-statistics/evidence/validation.md:13-19` 记录 knowledge + knowledge-review 10 tests、IM 20 tests、Web 27 tests、build/typecheck/check:ios-runtime 与 Web production build 通过，以及 iOS 新统计数据契约通过。本轮检查对应测试代码与实际消费链，未重复执行已有效覆盖的测试。
- **尚待补齐：** design.md:66/74 要求的真实 Web 新统计/空态及桌面/390px 原型对照，和适用完整 CI/iOS 门禁结果。现有证据明确写明通用模拟器图片剪贴板失败尚待隔离基线复核，因此本轮不宣称 iOS 全量通过。
- **原型证据边界：** design.md:44-48 与 design-review.md 的 R2 证明设计原型已观察；它们不能证明最终产品的 must-match 已完成。本轮静态投影成立，实际产品对照仍 pending。

## Correctness

路径默认相对于仓库根；测试行号来自固定提交。

| Requirement / Scenario | 实现位置 | 测试覆盖与证据 | 状态 |
|---|---|---|---|
| 关闭自进化时统计正常使用，超过 60 次、重启、去重 | `packages/dsh-integration/src/knowledge/files.ts:124-140`；`runtime.ts:216-232` 使用宿主 `config.agentId`，调用记录位于自进化判断之前 | `packages/dsh-integration/tests/knowledge.test.ts:56-98` 覆盖 75 次、重开文件、去重；`:190-230` 的真实 DSH fixture 使用 `skill_creation:false`，公开 usage 与重启结果保持 1 | covered；真实 Web 旅程 pending |
| 共享 Skill 分别计数，样本淘汰不丢统计 | `files.ts:134-165` 按 Agent 聚合、仅筛自身引用，共享 root 无自身聚合时不展示 | `knowledge.test.ts:71-91` 先记 a 75 次，再记 b 65 次，a 引用为空但累计仍 75；b、unused 归属分别断言 | covered |
| 旧记录与新统计起点 | `files.ts:134,153-157,164-169` 首次有效新 use 才创建统计；旧 count 不进入输出，本地保留元信息和 null 起点 | `knowledge.test.ts:65-70,86-90` 构造旧 999 及旧引用，新投影为 0/null/空引用；原 count 保留 | covered |
| 两条公开统计入口及安全投影 | `apps/im-server/src/agent-settings.ts:120-127`；`control.ts:1050-1057` 共用显式投影，不透传 statistics | `apps/im-server/tests/agent-settings.test.ts:211-233` 比对两 API 并验证 other 聚合不泄漏；既有安全字段过滤测试保留 | covered |
| 离线旧缓存不可用、合法新缓存保留、在线旧形状拒绝 | `agent-settings.ts:16-19,82-94,120-127`；设置路由 `control.ts:831-853` 先成功投影再写快照，失败回读 | `agent-settings.test.ts:211-233` 覆盖 fresh offline、legacy offline/read_failed、legacy live 502 | covered |
| 累计超过窗口、UTC 日期、起点前未知与空态 | `files.ts:136-169`；Web `agent-detail-page.tsx:772-774,822-867,970-1090`；iOS `AgentModels.swift:151-169`、`AgentSkillsView.swift:27-34,54-59,76-94` | `knowledge.test.ts:91-98` 月切换清理不降低累计和 b 统计；Web `agent-detail-page.test.tsx:353-379` 固定服务端日期、76/4 分离、28 未纳入/2 已统计格；iOS `AgentContractsTests.swift:6-18` 累计/窗口、日期过滤与 nil 起点 | covered；真实布局对照 pending |

### Architecture and Agent Context scope

- 包依赖没有新增：统计写入仍只在 integration 内；Node `apps/node/src/main.ts:266-269` 通过既有 RPC 投影，IM 不读 workspace 或 import DSH；Web/iOS 只消费公开结果。
- 新 `statistics` 是产品显示聚合，不作为模型工具结果或维护 prompt 的输入。`KnowledgeRuntime.usage()` 的消费者经 `knowledge.usage` → Node relay → IM；不进入 Agent system/tool/messages。
- 检查了潜在间接影响：原始 `use_count`、`uses_since_last_B`、200 条去重和 60 条 `session_refs` 更新保留。`references()` (`files.ts:171-180`) 仍按 session ID 查找，compaction 恢复 (`runtime.ts:93-103`) 不读取新统计；`batchCandidate()` (`files.ts:203-212`) 仍返回旧计数/原始引用，`batchHistory()` (`runtime.ts:319-361`) 仍将引用选择为符合现有 owner/已结束规则的历史，最终 review context (`runtime.ts:289-299`) 不序列化新增聚合或引用 `agent_id`。
- 因此本次 diff 未改变模型消费、维护触发或恢复选择，不触发完整 agent-context-review。已有 knowledge-review 的 F4/维护回归作为该隔离的执行证据；没有新增真实模型行为验证要求。

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 单条 Usage 中按宿主产品 Agent ID 聚合，同一锁与 atomicWrite | 是 | `files.ts:124-140`；`runtime.ts:226` |
| 不回填旧数据，本地保留元信息，共享只显示自身新统计 | 是 | `files.ts:153-165` |
| 累计、30 UTC 日桶、60 引用、200 去重各自职责 | 是 | `files.ts:128-140,158-165`；测试月切换覆盖 |
| API 显式起点/窗口，两个入口同判定，旧形状不包装 | 是 | `agent-settings.ts:16-19,89,120-127`；`control.ts:1057` |
| Web 30 日实际窗口，起点前未知，六列/名称下起点和表内滚动 | 静态符合；真实布局待证据 | `agent-detail-page.tsx:937-961,975-989,1019-1090` |
| iOS 双计数、UTC 日轴、对应起点过滤、nil 空态 | 是 | `AgentModels.swift:154-163`；`AgentSkillsView.swift:27-34,54-59,84-94` |
| 维护与 Context 消费保持原职责 | 是 | 见上文共享链路检查 |

设计 `design.md:28` 曾写直读接口离线为 `node_online:false`；`M1-statistics/evidence/validation.md:21-23` 已记录真实既有 rpc helper 为 HTTP 503。最终 delta 只要求“保留离线不可用语义”，实现保留 503，没有新增行为偏离或兼容分支。

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 30 天实际窗口、UTC、累计与窗口标签分离 | design:35-38/74 | Web 与 iOS 日期/计数映射见上表 | 自动化测试通过记录位于 validation；最终真实页面对照尚待交接 | pending evidence |
| 六列表格、名称下起点、390px 表内横滚 | design:36/74 | Web 保留六列，起点在名称下，表外 `overflow-x-auto` | 设计原型已有 R2 记录；最终产品桌面/窄屏证据 pending | pending evidence |
| 起点前不称零、无新调用空态、热力图星期/周列和图例 | design:35-38/74 | Web coverage/unknown 分支、UTC week grid、nil 隐藏；iOS nil 返回空数据和空态 | Web/iOS 数据契约测试；最终产品观察 pending | pending evidence |

## Issues

### CRITICAL

无已确认实现缺陷。M1 的真实 Web 对照和完整适用门禁仍在执行，本轮为中间证据状态，不能作为 milestone 退出或提 PR 放行结论。

### WARNING

无静态发现。

### SUGGESTION

无。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Skill 使用统计 API 总体口径/关闭自进化 | `files.ts:124-169`；`runtime.ts:226-227` | knowledge 新存储回归和真实 runtime 关闭开关回归 | aligned |
| 共享 Skill 分别计数 | `files.ts:134-165` | 75/65 跨 Agent、引用挤出与 unused 测试 | aligned |
| 旧记录与新统计起点 | `files.ts:134,157,164` | 999 旧计数 fixture 及 nil 起点断言 | aligned |
| 查询统计，两入口公开字段 | `agent-settings.ts:120-127`；`control.ts:1057` | IM 双入口等值与安全投影测试 | aligned |
| 离线缓存/在线旧形状不得混入 | `agent-settings.ts:16-19,89,121`；`control.ts:831-853` | IM fresh/legacy/live/cached 回归 | aligned |
| 累计超过窗口，Web/iOS 日期和空态 | `files.ts:136-169`；Web/iOS 位置见 Correctness | 跨月、Web 固定 UTC、iOS 展示数据契约 | aligned |

### Uncovered Observable Behavior

None。新增 `archive_error` 与 `recent_call_keys` 的显式公开投影恢复既有客户端字段，且只来自当前 Agent 可见引用；不引入额外统计口径。`health.used_auto_total` 使用新统计 use_count，属于 delta 的“旧总数不回填”范围。原调用、去重、维护和归档生命周期没有改动。

Outcome: **aligned**。这是 corrected-delta 与固定实现的一致性结论；完整 full verification 放行仍等待上列运行/真实对照证据。
