# Code Review: perf-649

## Round 1

- reviewer: `/root/static_review`，未参与本 unit 的实现；本轮按 `change-code-review` 独立裁决。
- review_mode: `full`。
- executed_base: `52b9a1ac831cc7f92709d12764cdd1a9410dea0f`。
- validated_at: `986cb0a237831795a2964e598112a501cd007d66`。
- diff: `52b9a1ac831cc7f92709d12764cdd1a9410dea0f...986cb0a237831795a2964e598112a501cd007d66`。
- checkout: `.worktrees/unit-perf-649`，branch `unit/perf-649`；受审前 HEAD 与 validated_at 一致且工作区干净。
- completed_at: `2026-10-23T23:24:33+08:00`。

## Verdict

**PASS — 无存活代码问题。**

```json
[]
```

## Coverage and reasoning

完整阅读 6 个 diff 文件，并回查 `inputEvidence`、ModelFallback 的 attach/observe/evidence/schedule、ModelPolicy 装配和 `session.lookup` 的真实调用方。

- `packages/dsh-integration/src/input-evidence.ts:54` 的新投影保持两条独立 inbox 队列，以原生 splice 处理默认 removedCount、负下标、替换和重复 ID。旧单 ID 投影在非 canceled removal 或 user/message 时更新 turn；新 Map 对每个 ID 执行同样更新，canceled removal 不改旧归属。两者均在 turn/end 后清空当前 turn，因此 out-of-turn 消息、claim 未消费、后续 attempt 和完整历史恢复保持最后归属语义。
- 首次插入 Set 的顺序与旧 flatMap 后逐个筛选并去重的输出顺序相同；仅 transcript 出现的 ID 被排除。消费者 `model-fallback.ts:260` 保留 nano-fallback 前缀过滤与 run.inputs 去重，不变更逻辑 run、状态机、失败重试、粘性或通知。
- 新函数仅在 turn/end 使用；attach 对持久 terminal 的重放仍读完整快照。`inputEvidence` 原实现与 `session.lookup` 投影未修改；没有用当前 turn 前缀替代最终归属。跨包依赖、公开 DSH exports、持久 schema 均未变化。
- 运行代价为 O(E+S+I)，其中 S 包含队列 splice 工作；临时 Set/Map/队列为 O(I+U+Q)，函数返回后无常驻索引。未将此界限错误扩大为整个 ModelFallback 或故障 schedule 的界限。现有 run.inputs.includes 和故障路径查询保留在授权范围内。
- 差分测试覆盖逐前缀语义；计数回归能让旧乘积回放实际变红。RuntimeClient 测试扩展原有文件，新增主模型成功、无备用成功/失败、三 attempt，并对四个前后输入的逻辑 run 归属作隔离断言；保留原有恢复/取消/pre-step 等边界，无重复平行套件。

## Validation evidence reused

核读 `M1-linear-replay/evidence.md` 与 caller 指定的 `/tmp/perf649-environment/{narrow.log,red.log,benchmark.jsonl,build.log}`。20 tests passed、旧算法 5,005,000 visits 超限的 RED、全仓 build 成功与 500/1000/2000 合成实验均有实际日志。2000 历史输入为 20,030,010 → 10,005 次访问，访问减少 99.95%，同机中位耗时改善约 1296x。时延结果仅适用于该合成 fixture，不外推生产占比。

这些日志在代码提交前生成，build 版本戳为基线 `3814a7faae6617df3203fd58382ce7d53419090a`，不能解读为干净基线代码的测试。caller 提供该工作树验证来源；实际实现提交为 `e5a381225`，本轮独立 `git diff e5a381..validated_at` 确认其后仅其他 unit 的设计文档变化，受审源码/测试/benchmark 未改变。未发现需要重复运行已有效覆盖测试的关键缺证；本轮未启动服务或修改实现。

本报告只给代码门禁结论；独立产品 reviewer 的完整栈旅程结论另行记录。

## Round 2 — final-main integration patch

- reviewer: `/root/static_review`，独立于本 unit 实现及 main 增量实现。
- review_mode: `patch`。
- executed_base: `b78b263abc8249617906117f8f19eeb1e825fab3`（已用 git 核实完整 SHA）。
- prior_validated_at: `986cb0a237831795a2964e598112a501cd007d66`。
- validated_at: `fd7acae2847451cda839652225267f8e3d3520aa`；受审前 HEAD 相同且工作区干净。
- diff_range: `986cb0a237831795a2964e598112a501cd007d66..fd7acae2847451cda839652225267f8e3d3520aa`。
- scope: 仅 main 集成增量对 perf-649 输入归属、ModelFallback 与共享 runtime 门禁的影响；不替代 #393 的完整审查。
- completed_at: `2026-10-23T23:58:13+08:00`。

### Verdict

**PASS — patch 范围无存活代码问题，无需扩大 full review。**

```json
[]
```

### Delta coverage and retained basis

- `git diff --exit-code e5a381225..fd7acae2847451cda839652225267f8e3d3520aa --` 明确核对本 unit 两个源码、两个测试及 benchmark，退出 0。因此 Round 1 的算法语义、复杂度、差分/RED/计数回归和合成性能结论继续适用于相同源码；原报告的实际验证 SHA 与执行结果保留，不改写成新版实跑。
- main #393 引入 `DescendantReader`、公开同版本 `dsh-session-persistence` 直接依赖、`index.ts:384` 的 session.descendants 接线及 GlobalAgent 子轨迹 drain。本轮读新 helper 与其调用方、新增 descendants/tool-presentation/global-agent 测试，以及对应 package/lock diff；lock 只新增已存在锁图版本的 importer，未升级 DSH/runtime 版本。新增公开 dependency 在 integration 内，manifest 声明与 package exports 对应，无 private import 或 runtime patch。
- `index.ts:390` 仅同步 `structuredClone(fallback.list(id))` 并生成模型投影 digest；`DescendantReader` 执行 flush/stat/observe，只输出目录与自有事件，未写 inbox、原生事件、ModelRun、输入归属或 ModelFallback 状态。旧 `session.observe`/`session.lookup` 及 turn/end 到新 helper 的接线未改变。
- reader 在获取 observation 后同步捕获模型版本，ModelRun 在同 cursor 从 switching 变 completed 时触发自有事件重放；消费者在投影成功后确认 cursor/modelVersion。它保护子轨迹显示对异步 fallback 终态的观察，不对本 unit 的最终 turn 归属投影引入缓存或额外过滤。
- `global-agent.ts:600` 的 root/child drain 分离未改变 root 对 durable、input completion、logicalEvents 和 model notices 的处理；通知/恢复仍等待双方，业务入口只等待 root，busy/stop 覆盖新增 child drain。新测试明确覆盖 same-cursor fallback completion 和挂起 child 不阻塞发送/任务入口。

### Validation limits

未重复旧 narrow tests、benchmark 或全量测试，未启动任何进程；遵守 caller 关于全机过载与串行构建的安排。检查时 `/tmp/perf649-environment/final-build.log` 仍在 TypeScript 构建阶段，不能据旧 build 宣称本次最终依赖/注入环境已实跑通过；caller 负责新版 build 与产品启动/备用链局部观察。主干 #393 的既有验证见其归档报告，但不冒称在本冻结版重跑。旧版完整产品 acceptance 的实际 SHA 继续保留，新增 runtime 启动契约由新版局部观察补齐。无关键语义缺证要求重跑已覆盖的旧算法测试。

## Round 3 — perf-650 main integration patch

- reviewer: `/root/static_review`，未参与受审实现。
- review_mode: `patch`。
- executed_base: `4bb02455b1d072a899a54bf62cdf2927c4069a99`（git 已核实完整 SHA）。
- prior_validated_at: `fd7acae2847451cda839652225267f8e3d3520aa`。
- validated_at: `9b95fea3b7a577674ffbdd2c9882ab6ee3e97fa2`；现场 HEAD 相同，开审时工作区干净。
- diff_range: `fd7acae2847451cda839652225267f8e3d3520aa..9b95fea3b7a577674ffbdd2c9882ab6ee3e97fa2`。
- scope: perf-650 usage/index/PA/type 增量对 perf-649 输入归属、fallback turn/end、既有门禁与前端证据保留的影响；不代替 perf-650 全量审查。
- completed_at: `2026-10-24T00:02:56+08:00`。

### Verdict

**PASS — patch 范围无存活代码问题；无须扩大 full review。**

```json
[]
```

### Coverage and retained evidence

1. 本轮 `git diff --exit-code e5a381225..9b95fea3b7a577674ffbdd2c9882ab6ee3e97fa2 --` 对本 unit 两个源码、两个 test 文件及 benchmark 退出 0。输入归属、最后 turn、claim/cancel、恢复、逻辑 run、多 attempt 和性能计数的旧代码与原测试结论 retained；旧报告的实际执行 SHA 保留。
2. `dsh-integration/src/usage.ts:31` 新 listener 仅读取 own event 并追加到独立 pending/dirty 状态，`:145` consume 维护独立 usage turn 缓冲。flush/observe 与 token derive 不改 Session 原始事件、inbox、ModelRun 或 inputEvidence。UsageReader 对自身读取串行，不接管 ModelFallback observe/schedule，也不在 inputIdsForTurn 中引入调用或常驻缓存。
3. `index.ts:193` 的 usageRoot 回退仅为已发现且祖先卸载的子事件补全 rootSessionId；原 sessionId/event 不变。`:369` 的 usage.read 新分页结果与 PA usage.ts 的同步消费者一起更新；原 session.lookup/session.observe 和 fallback turn/end 接线未变。PA `usage.ts:23` 仍在 turn/end 后异步独立 recover，`:45` 保存所有 reports 后推进 cursor，node.report outbox 与 fallback 控制状态分离。store 新增 pending 索引不改变输入持久状态或既有 run identity。
4. 阅读新增 usage 回归与 workflow-native 的真实接线断言，覆盖冷恢复、flush 时事件、父子结束、child 卸载、ACK/保存失败/重试及 restart；参考 perf-650 自有验证记录的实际版本和 final-sync 3 files / 11 tests 结果。它们是上游共享证据，本轮没有执行这些检查，也不据此宣称本冻结版 backend 全套通过。
5. 前端树仍为 `0432845539bbcf3bc413b54e081c5f866c033271`；本次增量对 frontend（含 package-lock）、根 package/lock、前端生成脚本及 product-contracts 的 interactive/catalog/trajectory 运行时源均无变化。product-contracts 唯一变化为导出 `UsageReadResult` interface，无值、schema 或序列化实现变化，类型在构建中擦除。因此此前共享 perf-648 前端 suite + 未改文件局部重试的证据继续 retained，不需要因新增该 interface 重跑前端；最初单项 timeout 与实际共享执行 SHA 仍保留，不重写为本轮执行或一次全绿运行。

### Limits

未运行任何测试、benchmark、构建或服务。旧 unit 窄测/性能与前端共享证据可保留；变更后的完整 backend build 及新版真栈启动/备用链观察仍由 caller 完成，本报告不预填成功。未对旧后端全量 incomplete 状态改判，也没有把 perf-650 改动纳入本 unit 的性能收益或增加公开行为承诺。本轮仅追加本报告和 verification.md，未修改实现或提交。
