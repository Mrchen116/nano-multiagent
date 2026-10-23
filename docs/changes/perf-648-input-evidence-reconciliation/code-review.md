# perf-648 Code Review

## Round 1

- reviewer: independent Codex subagent `/root/static_review`，未参与受审实现；按 caller 明确派发兼任 change-verifier。
- review_mode: `full`。
- executed_base: `1ef49808ffd2618c275b6e38683f93f74ff8455d`。
- validated_at: `2c4b06abcad6ab4af35d2fffdf0daeb6ba7788a1`。
- branch / worktree: `unit/perf-648` / `.worktrees/unit-perf-648`；开工及写报告前 HEAD 均为 validated_at，工作区原先干净。
- scope: 上述 base...head 的完整 5 文件差异，并向真实 runtime、Node 接线、交付恢复及 current specs 追踪；不代替独立产品验收。
- completed_at: `2026-10-23T23:28:07+08:00`（完成代码与窄验证的时间）。

### Verdict

**Pass；没有存活的 CONFIRMED / PLAUSIBLE 代码 finding。**

```json
[]
```

### Coverage 与证据

1. **真实接线。** `apps/node/src/main.ts:335-338` 构造本次修改的 SingleThread。公开 `recover` 在 `single-thread.ts:162-169` 恢复绑定、未接受输入并进入 reconcile；notification / receive 也进入相同串行 drain。修改的选择逻辑确实在实际调用链 `single-thread.ts:198-208`，不是仅供测试的旁路。
2. **最终证据判据。** `dsh-integration/src/index.ts:362-366` 的实际 lookup 先执行 session flush，再调用 fallback evidence；`model-fallback.ts:169-179` 映射 logical turn，只有 completed run 暴露 terminal。PA 额外要求 fresh accepted、明确 pending=false、非空 terminal，以及关联 logical/attempt run completed（`single-thread.ts:204-207`）；旧的物理 terminal、缺失 pending、running/switching 均不会固定。无关联 run 时保留旧会话和取消未消费的既有 lookup 语义。
3. **写入所有权。** `store.ts:191-194` 单 SQL 原子写证据和 final 标记；`recordEvents:225-230` 继续保存全部事件，但物理 turn/end 只更新未固定行。检索全部 inputs INSERT/UPDATE、inputEvidence 调用，未发现其他 terminal 写入者绕过保护。Global 的原调用 `global-agent.ts:535` 缺省 final=false，继续保持原对账行为。
4. **升级和回滚。** `store.ts:55-61` 对缺列旧库执行 additive migration，再建 `(session_id,evidence_final)` 索引。receive / runtimeInput 原有 INSERT 都显式列名（180、249），旧 terminal 不推断 final；旧版读取仍选择旧列。独立窄探针在旧 schema 中预存一行 accepted=1、turn=1、terminal=error，升级后确认其仍待查；fresh final 后补录失败/成功物理 end，再重开 DB，terminal 保持 completed、事件完整、待查列表为空。探针也确认 Global 缺省调用仍能恢复未固定状态和接受物理终态更新。
5. **delivery/receipt 独立恢复。** 优化只改变 lookup 循环，`single-thread.ts:211-310` 仍遍历全部输入、重建逻辑事件和复用 delivery 身份；已确认交付仍走 receipt（218-220），receipt 只在 ACK 成功后本地确认（386-391）。`input-reconciliation.test.ts:78-116` 以真实 SQLite 重开、模拟 receipt 中断证明终态已固定也会补 receipt、不会再完成第二条回复；现有 fallback 测试保留提示、正文、usage 和 receipt 断言。
6. **性能和测试边界。** 新测试从公开 recover、RPC、relay 和持久状态观察，分别保护此前缺失的筛选规模、重启恢复、延迟物理事件及 snapshot 滞后；既有 fallback 文件扩展其语义 owner。1000 历史完成输入在一次补证据后零 lookup，新增 3 待定输入只查 3 条；取消未消费可收敛，缺证据继续查。仍保留全量事件/交付遍历，因此没有把 RPC 缩减表述为整个 drain 的 O(K) 或生产性能比例。

### Validation

- 复用 `M1-pending-evidence/progress.md` 对产品提交 `95a8c00ea2835e1e8578b55725dabeec7281ef1d` 的证据，已实际读取 `/tmp/perf-648-pa-tests.log`、`/tmp/perf-648-build.log`、`/tmp/perf-648-typecheck.log`：PA 24 files / 171 tests，根构建和 typecheck 通过；产品提交后至 validated_at 只有 progress 文档变化。
- build 的 installer candidate metadata 显示 base `1ef49808...`；caller 确认构建发生于产品提交前且构建后源码未变化。该日志仅证明受审源码可构建，不证明部署版本。本轮未部署。
- 独立执行（Node v24.22.1）：`PATH=/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH pnpm exec vitest run packages/dsh-integration/tests/input-evidence.test.ts`，1 file / 3 tests passed，覆盖中断 claim、仍在队列、取消未消费的真实 evidence 函数。
- 独立临时 NodeStore 探针结果：`{"node":"v24.22.1","legacyRowEligible":true,"finalSurvivesDelayedEventsAndReopen":true,"globalDefaultUnchanged":true}`。用临时目录创建/迁移/重开 SQLite，finally 删除数据库；没有修改永久测试。
- `git diff --check <executed_base>...<validated_at>` 通过。未启动服务、未借用其他现场日志；required CI 与独立产品验收由 caller 完成。

## Round 2 — Final Main Sync Integration

- reviewer: independent Codex subagent `/root/static_review`；保留 Round 1 原始快照与证据，不改写其版本。
- review_mode: `patch`；范围为 main 增量 `1ef49808ffd2618c275b6e38683f93f74ff8455d..b78b263abc8249617906117f8f19eeb1e825fab3` 对本 unit 的集成影响，以及重放后本 unit 是否发生代码变化；不重新全审已合并 bugfix-647。
- effective / executed_base: `b78b263abc8249617906117f8f19eeb1e825fab3`。
- validated_at: `817f92040be5916e5abb42196948c1147009c399`。
- branch / worktree: `unit/perf-648` / `.worktrees/unit-perf-648`；核实 HEAD 等于 validated_at，写报告前工作区干净。
- completed_at: `2026-10-23T23:41:48+08:00`（完成静态复核时间）。

### Verdict

**Pass；Round 1 retained；没有本轮存活的 CONFIRMED / PLAUSIBLE 代码 finding。**

```json
[]
```

### Patch Coverage 与 retained 依据

1. **产品 patch 等价。** 对 R1 validated_at 与 R2 validated_at 的 `single-thread.ts`、`store.ts`、`input-reconciliation.test.ts`、`model-fallback.test.ts` 执行逐文件 Git diff，均为空。两源码 blob 分别仍为 `efd7e68b9cbf6193d9f8040c98d1a17008df1f79`、`9e6836601bf2d2c6e77c7c6badbc2fd99a2de43e`。R1 性能筛选、写入所有权、旧库与重开探针、receipt 恢复和 fallback 测试判断可直接保留。
2. **实际 runtime seam 未变。** main 增量只在 `index.ts` 增加 sessionPersistence 注入与 session.descendants 实现；实际 session.lookup（现 363-367）和 session.observe（377-382）函数体与 R1 相同。`input-evidence.ts`、`model-fallback.ts`、PA `presentation.ts` 和 `apps/node/src/main.ts` 的两快照 diff 同样为空，fallback 源码 blob 仍为 `808f309f942371786835b06088d577dc5c477d13`。本 unit 不调用新 descendants 协议，不依赖 bugfix-647 来使最终证据判据成立。
3. **共享 NodeStore writer 不受 Global 拆分影响。** 读取 Global main 增量：变化为 root/child drain 分离、busy/stop 等待子 drain、独立 childCursors/childModelVersions。`global-agent.ts:535-539` 的既有同群 lookup/inputEvidence 调用仍不传 final；新增 descendants reader 与投影路径不读写 inputs.evidence_final，不会绕过本 unit 的证据保护或把缓存证据当 receipt。
4. **依赖与隔离边界。** 新增依赖是 integration 已声明的公开 `@deepseek-ai/dsh-session-persistence` 0.2.1-alpha.1 根 export，lock 与该声明一致；没有让 PA / Node 引入 DSH。reader 的 metadata cache 只归 runtime descendants；新增测试保护冷历史、modelVersion 切换与 Global root source checks，均没有替换本 unit 的输入对账回归。新 runtime 注入后的真实启动/构建结果仍以 caller 同版本复跑为准。
5. **其它 main 增量。** feat-645、perf-650 及 bugfix-647 的文档/归档不改本 unit 需求或设计；main 的 IM current spec 小改属于节点能力 UI，与本 unit 内部输入对账无交集。同步后仍 no spec delta。

### Validation 与限制

- `git diff --check b78b263abc8249617906117f8f19eeb1e825fab3...817f92040be5916e5abb42196948c1147009c399` 通过；本轮按 patch 模式保留适用 R1 证据，不重复 PA 全审或窄探针。
- 已读取 `/tmp/perf-648-final-install.log`：lockfile 对齐、Already up to date，pnpm 11.7.0；读取 build 日志时仍在执行，**没有将进行中的 build 或尚未取得的测试宣称通过**。
- caller 正在同一 validated_at 重跑 build/typecheck、descendants/tool-presentation/global、完整 PA 及 native model-fallback，结果由 caller 归集 `/tmp/perf-648-final-*.log`。本轮结论是静态 patch 集成复核 pass，不代替这些运行门禁。
