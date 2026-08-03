# refactor-489-M19: fix-frontend-ci — Tasks

> 对齐: 已归档 unit 的受限 post-PR 小修；只关闭 PR #227 frontend CI 的 user-stream Vitest 时序失败，不修改 `design.md`、产品代码或 current spec。

## 目标

让 `user-stream` runtime 的 ping、resync-failure reconnect 与 reconnect 后 recovery 三个既有行为用例，在 CI 的干净 Node 20 依赖树中稳定驱动自身的 fake-timer 队列；保留原有 transport、cursor、recovery 和 malformed-event 风险断言。

## 退出标准

- [x] 在干净 worktree、Node `v20.20.2`、`npm ci` 后，定向 user-stream suite 连续三次复现同一 3 个失败，而不是把它们当作偶发 flaky。
- [x] 证明单次 `advanceTimersToNextTimerAsync()` 先消费 Vitest/jsdom worker 已有 timer，而非 runtime 创建的 ping/retry timer；产品 runtime 的 socket/ping/reconnect 顺序无需修改。
- [x] 只在测试 harness 的 `setup()` 边界清除继承 timer；原有“推进下一项 runtime timer”的测试动作和三个行为断言均保留。
- [x] 在最终 milestone HEAD 上连续运行定向 suite、完整 `npm run test`、docs/scope/whitespace 检查，并只推送 milestone branch。

## 测试策略

- 被测行为（来自退出标准）：已打开 socket 的 ping；resync 同步失败后的 retry socket；正常 reconnect recovery 结束后再次触发 corruption recovery。
- 已有测试在：`src/IM/frontend/src/realtime/user-stream/user-stream.test.ts`；不新增测试文件、不删除断言、不触及 `user-stream-runtime.ts` 或生产 adapter。
- 落层/目录/marker：Vitest/jsdom runtime test；fake socket 的 `sent`、实例数、resume cursor、recovery 回调和 subscriber event 是公开 transport/state seam。
- 可选依赖 import or skip：无；按 `.github/workflows/ci.yml` 使用 Node 20、lockfile 的 `npm ci` 与 `npm run test`。
- 本 milestone 产生的一次性诊断证据：临时 timer-count tracing 已在修复前运行后移除；命令、结果和因果链记录在 `progress.md`，不提交 debug logging 或 runtime residue。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| live socket ping 与 close 后 reconnect/recovery | `user-stream.test.ts` 的 ping/reconnect case | rewrite-merge | `advanceTimersToNextTimerAsync()` 仍驱动下一项 socket-owned timer；只在创建 runtime 前清除 runner 遗留 timer，避免它吞掉队列推进。保留 `ping`、第二 socket、resume 与 recovery 断言。 | clean Node 20 定向 Vitest ×3 + full frontend Vitest |
| epoch resync 失败后的 retry 与低游标 replacement | `user-stream.test.ts` 的 epoch-resync failure case | rewrite-merge | 保留 sync error、closed first socket、retry-created second socket、旧 cursor resume、lower authoritative cursor、新 epoch event 全链路；不把缺失 socket 以可选断言掩盖。 | clean Node 20 定向 Vitest ×3 + full frontend Vitest |
| reconnect recovery 完成后，later corruption 再次触发 recovery | `user-stream.test.ts` 的 later corruption case | rewrite-merge | 保留 pending first recovery、second socket open、release 后 second corruption 与第二次 recovery；修复只确保队列推进到 retry timer。 | clean Node 20 定向 Vitest ×3 + full frontend Vitest |

## Roadpoints

### R1 — 固定 CI 基线与时序因果链

- 状态: DONE
- 步骤: 读取 CI workflow、M16 history、runtime 与相邻用例；在 clean Node 20 `npm ci` 环境连续运行定向 suite 三次，并用临时 timer-count trace 观察 queue advance。
- 验证: 三次均为 15 tests 中相同 3 failures；trace 显示 runtime 建立前已有 1 timer、socket open 后为 2，首次 advance 后 clock 未前进、仅余 1 timer 且没有 ping。

### R2 — 在 runtime harness 边界隔离继承 timer

- 状态: DONE
- 步骤: 仅在 `setup()`、开始订阅/创建 runtime 之前调用 `vi.clearAllTimers()`，使后续 queue advance 只观察该 test 创建的 runtime timer；不改 production runtime 或行为断言。
- 验证: clean Node 20 定向 suite `15 passed`；R3 在最终 HEAD 上重复并扩大全量门禁。

### R3 — 最终 CI 等价验证与交付

- 状态: DONE
- 步骤: 用 Node 20 在最终文档/测试 HEAD 连续定向验证、运行完整 frontend command、docs/scope/whitespace 检查，提交并只推送 milestone branch。
- 验证: `npm run test`、`scripts/docs_check.py`、`git diff --check`、changed-path audit；`node_modules` 为 `npm ci` 产生的 ignored dependency tree，未提交。
