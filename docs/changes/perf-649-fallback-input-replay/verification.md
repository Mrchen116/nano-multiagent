# Verification Report: perf-649

## Round 1

> Validation snapshot: `52b9a1ac831cc7f92709d12764cdd1a9410dea0f → 986cb0a237831795a2964e598112a501cd007d66`

- reviewer: `/root/static_review`，未参与实现；本轮按 `change-verifier` 独立裁决，与 code review 分别保留结论。
- verification_mode: `full`。
- branch/worktree: `unit/perf-649` / `.worktrees/unit-perf-649`。
- executed_base: `52b9a1ac831cc7f92709d12764cdd1a9410dea0f`。
- validated_at: `986cb0a237831795a2964e598112a501cd007d66`；现场 HEAD 已核对一致。
- completed_at: `2026-10-23T23:24:33+08:00`。
- requires_full_verification: `false`（本轮已为 full）。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 的实现、回归和性能退出标准满足；独立产品旅程由另一个 reviewer 负责 |
| Correctness | 首文档 4 个 Scenario 的实现与 runtime 回归映射完整，无发现偏离 |
| Coherence | Followed；no spec delta；无架构边界变化 |

**PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION。** 本结论为独立静态 verification；完整栈产品 acceptance 是单独门禁，此报告不代签其结论或据此宣称全部交付门禁已完成。

## Completeness

本 unit 只有 `design.md:55` 的 M1。其 worker 退出标准逐项核对如下：

| 退出标准 | 实现 / 直接证据 | 结果 |
|---|---|---|
| 替换全历史输入逐 ID 回放 | `src/input-evidence.ts:54` 单遍投影；`src/model-fallback.ts:260` 真实调用；保留 `inputEvidence` 与 session.lookup | 满足 |
| 差分语义 | `tests/input-evidence.test.ts:35` 双队列、负下标替换、重复 ID、claim 未消费、cancel、transcript-only/out-of-turn 和后续 turn 的逐前缀比较 | 满足 |
| runtime 回归 | `tests/model-fallback.test.ts:119` 新增成功/无备用/多 attempt；原有 prepare/finish/exhausted/context/published/tool/cancel/new-input/restart/pre-step 保留；`:98` 四个逻辑 run 输入隔离 | 满足 |
| 性能与状态边界 | `scripts/benchmarks/fallback-input-replay.ts:8` 合成 500/1000/2000 历史；`:44` 等价断言，`:45` 七次中位数，`:47` 单独计数，`:49` 95% 门槛；`M1-linear-replay/evidence.md` 记录时间目标与状态限制 | 满足 |
| typecheck / 相关检查 | 复用 2 文件 20 tests passed 与 `pnpm build`（含各包 tsc）的实际日志；不涉及 iOS、协议和 package manifest | 满足 |
| reviewer 用户旅程 | `design.md:43`–`:49` 给出真栈方法；caller 已单独派发产品 reviewer | 独立验收门禁，未冒认结果 |

Spec 覆盖以 `motivation.md:29`–`:43` 及 current `docs/specs/gateway/agent-capabilities.md:40` 的模型备用链为依据。未新增或删除公开行为。无前端与原型，Prototype / Reference 为 N/A。

## Correctness

下表路径除特别说明外相对 `packages/dsh-integration/`。

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 普通成功且历史输入不混入本轮 | `src/model-fallback.ts:260`；`src/input-evidence.ts:72` 最后归属过滤 | `tests/model-fallback.test.ts:120` success、no-fallback；`:98` 四个输入归属；`tests/input-evidence.test.ts:60` 差分 | covered |
| 无备用失败保持原失败 | `src/model-fallback.ts:274` 候选/错误判断保持原样，仅输入采集替换 | `tests/model-fallback.test.ts:122` no-fallback-error，`:253` error terminal 且 `:270` 无 backup | covered |
| 备用继续原请求、粘性与多 attempt | `src/model-fallback.ts:260` 排除合成输入并追加原输入；scheduleSuccess/schedule 及 ModelRun schema 无 diff | `tests/model-fallback.test.ts:10` 原请求一次消费、重启粘性；`:123` 三 attempt，`:275` 单逻辑 run/原输入/turns/模型默认档 | covered |
| 恢复/取消/新请求不抢占或复活 | `src/model-fallback.ts:130` attach 仍对完整快照调用 observe；新投影不依赖缓存，保留 claim/cancel 归属；interrupt/allowed 无 diff | `tests/input-evidence.test.ts:60` 每个恢复前缀；`tests/model-fallback.test.ts:130` cancel/new-input/restart/pre-step | covered |

代码对应关系：对任一已插入 ID，新 turns Map 的赋值事件恰为旧 inputEvidence 修改 inputTurn 的非 canceled removal 与 user/message。两者均逐事件更新并在 turn/end 清空当前 turn；重复 ID 共享最终值，Set 只限制首次插入输出顺序，因此新批量结果等价于旧逐 ID 归属筛选。terminal 细节仍由原 inputEvidence 负责，不因本 helper 忽略 terminal 而丢失 session.lookup 信息。

## Coherence

| design 决策 | 遵守 | 代码证据 |
|---|---|---|
| 双 inbox 原生 splice，claim 立即归属，cancel 不覆盖，最后归属/首次插入顺序 | 是 | `src/input-evidence.ts:55`–`:72`；旧 oracle `:5`–`:41` 不变 |
| 单次瞬时重放，无增量缓存/持久 schema，不强制其他 unit 消费新 API | 是 | helper 为局部变量；唯一产品消费者 `src/model-fallback.ts:260`；ModelRun domain 无 diff |
| inputEvidence/session.lookup 契约保留 | 是 | `src/input-evidence.ts:5` 无 diff；`src/index.ts:366` → `fallback.evidence` 调用及其逻辑 run 投影不变 |
| O(E+S+I) 时间与 O(I+U+Q) 临时状态 | 是 | 一轮事件扫描、两队列/Set/Map，包含 splice 移动；没有每历史 ID 内部回放 |
| 最低适合层扩展现有测试，时钟不成为 CI 抖动门槛 | 是 | 已有两个 test 文件扩展；事件读取计数永久回归，benchmark 仅记录七次中位数 |
| SPEC 架构与公开 DSH 接口边界 | 是 | diff 不改变包边界、依赖或 DSH 导入；新 helper 留在 integration，Node/PA/Channels/IM 不变 |

### Prototype / Reference Contract

N/A：内部归属回放优化，无前端、原型或必须对齐的视觉 reference。

### Evidence provenance and limits

已阅读 `M1-linear-replay/evidence.md` 及 `/tmp/perf649-environment/narrow.log`、`red.log`、`benchmark.jsonl`、`build.log`，复用 caller 的有效验证，不重复跑全量或启动产品服务。RED 明确为旧投影 5,005,000 visits > 10,000；GREEN 为 20 tests passed；build 含各包 TypeScript 编译成功。最大合成场景 20,030,010 → 10,005 visits（减少 99.95%），1276.196709ms → 0.984542ms（约 1296x），满足首文档 95%/5x 目标。2*(2000+1)=4002 entries、queue peak 1 是 fixture 的结构计数而非 heap 实测；瞬时状态可回收不代表常数内存或生产延迟占比。

日志的 build 版本戳指向实现提交前基线 `3814a7faae6617df3203fd58382ce7d53419090a`；验证在含本 unit 实现的工作树运行，来源由 caller 提供。本轮核对实现提交 `e5a381225` 至冻结版本只有其他 unit 文档 diff，源码、测试、benchmark 与冻结版一致；没有把日志当作干净基线或独立 reviewer 重跑结果。

### Contract delta

**no spec delta**。核对全 unit diff 没有遗漏新增可观察行为；只替换内部输入归属计算，返回行为、状态/数据格式和错误/恢复路径均保持，`design.md:24` 的裁决成立，无需 current spec 归并。

## Issues

- CRITICAL: 无。
- WARNING: 无。
- SUGGESTION: 无。

本轮仅新建本 unit 的 verification.md/code-review.md，未修改源码、测试、配置或设计，未提交。未自建 worktree 或启动进程；共享现场继续由 caller 持有和收尾。

## Round 2 — final-main integration delta

- reviewer: `/root/static_review`，按 `change-verifier` 独立复验；与同轮 code review 各自裁决。
- verification_mode: `delta`。
- executed_base: `b78b263abc8249617906117f8f19eeb1e825fab3`（git 已核实完整 SHA）。
- prior_validated_at: `986cb0a237831795a2964e598112a501cd007d66`。
- validated_at: `fd7acae2847451cda839652225267f8e3d3520aa`；现场 HEAD 已核对一致。
- fix_delta_range: `986cb0a237831795a2964e598112a501cd007d66..fd7acae2847451cda839652225267f8e3d3520aa`。
- scope: main #393 的共享 runtime / 子轨迹增量对本 unit 输入归属、ModelFallback 与 no spec delta 的影响；不重验整个 #393。
- completed_at: `2026-10-23T23:58:13+08:00`。
- requires_full_verification: `false`。

### Verdict

**PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION；no spec delta 继续成立。**

此为 delta 的静态实现/契约结论。新版 build 与产品启动/备用链局部观察由 caller 独立完成；旧版完整栈 PASS 与本轮静态结论不替代新版启动证据。报告不声称因静态 PASS 而完成所有 CI 或交付门禁。

### Delta reconciliation

| 影响面 | 本轮实际证据 | 原结论处理 |
|---|---|---|
| 输入归属算法与复杂度 | 本 unit `src/input-evidence.ts`、`src/model-fallback.ts`、两个 test 文件与 benchmark 自 `e5a381225` 至新 SHA 的 git diff 为空 | retained：Round 1 的等价性推导、差分/计数测试、合成性能指标保持有效；不重标其执行 SHA |
| fallback 输入、逻辑 run 与错误/恢复路径 | main 增量未改 turn/end、inputEvidence、session.lookup、attach、interrupt 或 ModelRun domain；新增 descendants 路径只读 `fallback.list` 克隆 | retained：输入归属/取消/多 attempt 回归边界未改变，无需重跑旧 narrow 或 benchmark |
| 共享 runtime 依赖与装配 | package/lock 新增已锁定同版本公开 `dsh-session-persistence`；`NanoRuntime.inject` 增加 sessionPersistence；相关使用局限 integration；无 DSH 版本变动 | 架构边界 aligned；构建/启动是新环境证据，不能将旧 build/启动 pass 直接重命名为新 SHA |
| 子轨迹观察 fallback 完成 | `index.ts:390` 在 observation cut 同步克隆 ModelRun 并比对 digest；`descendants.ts:74` 冷读必须同时匹配 metadata/cursor/model 版本；`:81` 在异步 observation 后重取版本；`global-agent.ts:672` 投影成功后确认双版本 | aligned：不影响输入归属本身，且保护同 cursor fallback completed 的可见终态；新增 `global-agent.test.ts` 的专门回归与真实 presenter 测试断言可定位 |
| 根与子 drain 分离 | `global-agent.ts:605` 根路径仍做 durable、logicalEvents、model notices/输入 completion；`:644` 子路径独立合并通知；busy/stop 覆盖新增 drain | aligned：分离子显示查询不会重置或消费本 unit 的输入归属状态；原 ModelFallback 门禁不失效 |
| current spec / no spec delta | 完整 unit 相对新 executed_base 的差异仍是本项内部归属优化及报告/验收记录；main 增量只影响其它已归档 unit 的既有轨迹恢复职责 | 本 unit no spec delta retained；没有新增输入、备用链或错误重试公开行为需要归并 |

### Evidence and limits

本轮只读 git、代码、现有报告和日志，未运行测试、benchmark 或服务。Round 1 的 20 tests、RED、性能与旧版 build 仍以原实际版本与来源解释；main #393 自有的历史测试证据保留在 `docs/changes/archive/bugfix-647-trajectory-sync/validation.md`，不将其当成新 SHA 的现场执行。检查时 `/tmp/perf649-environment/final-build.log` 仅显示串行 TypeScript 编译进行中，最终编译结果由 caller 补充；新版 startup/备用链观察同理。

未发现需要把本轮扩大为 full verification 的语义或架构变化。两个报告只追加本轮，不修改旧实际验证 SHA；未改产品、测试、配置、设计或其他 unit 报告，未提交或创建/启动新现场。现有机器过载下的全量测试未通过状态仍以 caller 的 evidence 记录为准，不被本 delta PASS 覆盖。
