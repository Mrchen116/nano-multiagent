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
