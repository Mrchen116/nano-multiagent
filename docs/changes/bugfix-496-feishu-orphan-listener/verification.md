# Verification Report: bugfix-496

> Validation snapshot: `e79b5d1a12204c077188f3646f741c8648d66cc9 → d0331f25b6edc8d5baa5e25a146eb7896345a69a`

## Summary

- Mode: `full`
- Delta range: N/A
- Focus issues: N/A
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 4/7 milestone exits complete；E5/E6/E7 的永久测试证据仍有阻塞 |
| Correctness | 5/5 incident scenarios 有实现映射；2 个 scenario 的测试证据不合格 |
| Coherence | Followed |

## Completeness

- `M1-E1`：正常 stop 路径仍由 `FeishuWorkerRuntime.stop()` 执行 stop-event、join、terminate/kill，既有双 Bot/真实 stop 回归通过；真实 Gateway stop/restart 旅程由独立 product reviewer 判定，不在 verifier 中重复验收。
- `M1-E2`：owner-death watcher 与 3 秒 PID+birth 回归均已落地；但新增回归在本轮相同快照上一次未能建立前置状态、一次通过，尚不能作为稳定退出证据。
- `M1-E3`：unit diff 未改飞书消息、回复镜像或 shadow 路径；真实三 nonce 旅程由独立 product reviewer 判定。
- `M1-E4`：unit diff 未改 IM offline/last-known 投影；现有前端测试继续覆盖 stale connected 的 last-known 呈现。worker 实现没有 idle timer，但设计要求的 parent-alive idle 永久断言缺失。
- `M1-E5`：真实 spawn owner → `FeishuWorkerRuntime` → listener 的 PID+birth 测试存在，但建桩阶段不稳定，未完成可靠退出证据。
- `M1-E6`：正常 stop/join、双 Bot、背压、drain/drop、card RPC、worker crash 与 SDK 日志用例分别通过；parent-alive idle 断言缺失，因此该退出项未全部满足。
- `M1-E7`：Ruff、format check、docs-check 与 `git diff --check` 通过；`progress.md` 明确记录整文件单次全绿仍待取得，本轮整文件/分组执行也出现失败或未正常收口，因此未满足。
- Prototype / Reference：N/A；`design.md` 无前端 prototype/reference contract，离线页面仅复用 current behavior。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 正常停止 Gateway 后旧 listener 消失 | `src/personal_assistant/channels/feishu/worker.py:331`；`src/personal_assistant/channels/feishu/worker.py:342` | `tests/unit/personal_assistant/test_feishu_worker_runtime.py:146` | covered |
| Gateway 无法清理便异常死亡后，listener 原 process birth 在 3 秒内消失 | `src/personal_assistant/channels/feishu/worker.py:200`；`src/personal_assistant/channels/feishu/worker.py:210` | `tests/unit/personal_assistant/test_feishu_worker_runtime.py:109`，但建桩 flaky | covered；测试阻塞见 R1-C1 |
| 异常退出后重启保持飞书回复与 shadow 消息稳定 | 本 unit 不改 `src/personal_assistant/channels/feishu/client.py:205` 之后的现有消息路径；旧 worker 由 watcher 释放 | 独立 product reviewer 真栈旅程 | covered；产品结论由 reviewer 持有 |
| Gateway 离线时页面显示 offline/last-known | 本 unit 无 IM/frontend delta；current `src/IM/frontend/src/features/settings/agents/agent-channels-panel.tsx:179` 继续以 node offline 覆盖 observed 状态 | `src/IM/frontend/src/features/settings/agents/agent-channels-panel.test.tsx:274` | covered |
| parent 存活且无入站消息时 listener 不退出、降级或重连 | `src/personal_assistant/channels/feishu/worker.py:200` 只等待 parent sentinel，没有 idle timer | 无明确的 parent-alive idle 永久断言 | covered；缺测试见 R1-W1 |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1：child bootstrap 在 listener target 前等待 multiprocessing parent sentinel | 是 | `src/personal_assistant/channels/feishu/worker.py:210-220` |
| D2：owner 消失时进程级立即退出；正常关闭仍走现有有序 stop | 是 | `src/personal_assistant/channels/feishu/worker.py:200-202`；`src/personal_assistant/channels/feishu/worker.py:331-350` |
| D3：从现有 worker interface 做两级真实 spawn 回归，不增产品测试开关 | 是 | `tests/unit/personal_assistant/test_feishu_worker_runtime.py:87-143` |
| D4：只扩充 Gateway external-channel 生命周期契约 | 是 | unit 产品 diff 仅修改 `src/personal_assistant/channels/feishu/worker.py`；无 IM/kernel/CLI/frontend/public API/config/schema 变更 |

- 架构自洽：未新增跨包依赖、Gateway/ChannelManager interface、配置、持久状态、启动扫描、进程组假设或 idle watchdog；实现复用既有 `FeishuWorkerRuntime` 深模块，未形成平行生命周期机制。
- 表层一致性：新增代码通过 Ruff 与 format check；并发意图由函数和 thread name 清楚表达，没有无 issue 的 TODO/FIXME 或吞错 fallback。

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL（提 PR 前必须修）

- **[R1-C1] `M1-E5/M1-E7` 的 owner-death 永久回归没有稳定建立测试前置状态。** `progress.md:30-34` 已明确整文件单次全绿尚未取得；本轮执行 `test_listener_exits_when_its_owner_dies_without_cleanup` 时，一次在 `worker_info_recv.poll(10)` 失败（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:123`），同一快照重跑才通过。根因边界是两级 spawn 建桩与现有 child-ready 时间预算竞争：inner `runtime.start()` 受 `src/personal_assistant/channels/feishu/worker.py:317-318` 的 ready 上界约束，而 outer test 只等待一个无错误通道的 10 秒 success frame，无法区分 owner 尚未调度、inner startup timeout 与真正的 owner-death 行为失败。请把测试 setup 与“owner 已死亡后的 3 秒契约”分离：让 owner IPC 明确回传 ready 或 startup error，给 setup 使用独立且适配 CI spawn 负载的条件等待/启动预算；只有 ready 后才触发 `os._exit` 并开始既有 3 秒 PID+birth 断言。修复后必须在当前完整 unit tree 上取得 `pytest -q tests/unit/personal_assistant/test_feishu_worker_runtime.py` 单次全绿并更新 `progress.md`，不能用失败后的重跑代替门禁。

### WARNING（提 PR 前必须修）

- **[R1-W1] 设计要求的 parent-alive idle 永久断言没有落地。** `design.md:80-82` 与 `design.md:344` 明确要求保留“parent 存活但无入站事件时 worker 持续存活”的断言，但新增测试在收到 listener 身份后立即触发 owner 退出（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:123-130`）；现有双 Bot 测试也没有在正常 stop 前明确断言 idle listener 仍 alive（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:163-174`）。请在现有 worker test 文件中扩展最低层行为保护：保持 owner 存活、让 listener 进入无入站等待态，明确断言同一 worker process birth 仍存活且未自行重启，再走正常 `stop()` 回收；不要把 reviewer 的一次性 10 秒真栈观察冒充永久回归测试。

### SUGGESTION（可以修）

- 无。

1 critical issue(s), 1 warning(s) found. Fix before PR.

# Round 2

> Validation snapshot: `e79b5d1a12204c077188f3646f741c8648d66cc9 → dc1ac46b3c1db2509fd2cdfb521a3a73001b89c1`

## Summary

- Mode: `targeted-closure`
- Delta range: `e834f561c5f84525b9c6d688099dc7c718db2a97..dc1ac46b3c1db2509fd2cdfb521a3a73001b89c1`
- Focus issues: `R1-C1`, `R1-W1`
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 2/2 focus issues closed；M1-E5/E6/E7 证据已补齐 |
| Correctness | 2/2 targeted scenarios 有稳定永久回归 |
| Coherence | Followed；fix delta 仅修改既有 worker 测试与 progress evidence |

## Targeted Closure

| Focus issue | 修复与代码证据 | 独立验证 | 状态 |
|---|---|---|---|
| `R1-C1` owner-death setup/3-second budget separation and single-run full-file green | owner probe 移入独立 Python subprocess，避免异常 owner 与 pytest 共享 resource tracker（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:171-180`）；inner startup 通过 `ready` / `startup_error` outcome 明确结算（`:88-108`），使用 30 秒 child-ready 与 45 秒 outer setup 预算（`:90-95,144-147`）；先确认 owner 原 PID+birth 消失，再进入默认 3 秒 worker birth 条件等待（`:149-153`）。 | 完整文件一次执行 `8 passed, 2 warnings in 20.34s`；pytest 输出只有既有 lark SDK deprecation warnings，没有 resource-tracker semaphore warning，结束后无本轮 pytest/spawn 残留进程。`progress.md:29-33` 已记录同一整文件命令和结果。 | closed |
| `R1-W1` parent-alive idle permanent assertion | 新增 test 从现有 `FeishuWorkerRuntime` interface 启动 listener，等待初始事件后冻结 PID+birth；owner 存活且无后续入站期间持续断言 runtime alive、birth 不变，最后走 `stop(drain=True)` 并断言 joined（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:183-202`）。 | 该用例包含在同一次完整文件 `8 passed` 中；既有双 Bot正常 stop 继续断言无需 terminate（`:205-233`）。 | closed |

## Scope and Retained Conclusions

- fix delta 只有 `tests/unit/personal_assistant/test_feishu_worker_runtime.py` 与 `M1-parent-liveness/progress.md`；没有修改 production worker、incident、design、delta-spec、public interface、配置、持久状态或用户可观察行为。
- Round 1 对 D1-D4、正常 stop、多 Bot、背压、drain/drop、worker crash、offline/last-known 与消息路径的实现映射未被该测试 delta 触及，结论 retained。
- delta 没有触及依赖方向、跨机边界或平行机制，不需要升级 full verification。

## Validation

- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_feishu_worker_runtime.py` → `8 passed, 2 warnings in 20.34s`。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check tests/unit/personal_assistant/test_feishu_worker_runtime.py` → passed。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff format --check tests/unit/personal_assistant/test_feishu_worker_runtime.py` → already formatted。
- `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` → `documentation integrity passed`。
- `git diff --check e834f561c5f84525b9c6d688099dc7c718db2a97..dc1ac46b3c1db2509fd2cdfb521a3a73001b89c1` → passed。

## Issues

### CRITICAL（提 PR 前必须修）

- 无。

### WARNING（提 PR 前必须修）

- 无。

### SUGGESTION（可以修）

- 无。

All checks passed. Ready for PR.

# Round 3

> Validation snapshot: `e79b5d1a12204c077188f3646f741c8648d66cc9 → d8d6d84724c4884bec824259a12698acca581c1b`

## Summary

- Mode: `targeted-closure`
- Delta range: `9ec7b0bc6cffa8d195990f284d768ad01ddbcb9f..d8d6d84724c4884bec824259a12698acca581c1b`
- Focus issues: probe child must load unit-worktree `src`; timeout/interrupt must reap the complete probe process group
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 2/2 patch-review issues closed |
| Correctness | 2/2 test-infrastructure failure paths independently exercised |
| Coherence | Followed；delta remains inside the existing owner-death regression harness |

## Targeted Closure

| Focus issue | 修复与代码证据 | 独立验证 | 状态 |
|---|---|---|---|
| probe 子解释器固定加载 unit worktree `src` | test 从自身绝对路径解析 repo root，把 `<unit-worktree>/src` 放在既有 `PYTHONPATH` 之前，并把该环境显式传给 probe（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:174-186`）。 | 验证进程故意把环境 `PYTHONPATH` 指向不含 parent-sentinel 修复的主仓 `src`，同时从 verify worktree 加载 test；owner-death probe 仍通过。若 child 未使用新前置路径，该探针会加载主仓旧 worker 并在 3 秒断言失败。 | closed |
| timeout / 中断清理 probe 整个进程组 | probe 使用 `start_new_session=True` 成为独立 process-group leader；`communicate` 的任意 `BaseException` 都向该确切 PGID 发 `SIGKILL`，随后再次 `communicate()` reap leader（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:180-197`）。 | 两次只读故障注入都先等待 group 内出现 probe、resource tracker、owner 和 listener：① 向 pytest PID 发 `SIGINT`，pytest 以 2 退出且 probe PGID 在 3 秒内无成员；② 首次 `communicate` 注入 `TimeoutExpired`，同一 cleanup 分支执行后 PGID 无成员。两次结束后均无 owner/listener 残留。 | closed |

## Scope and Retained Conclusions

- 本轮 delta 仅修改 `tests/unit/personal_assistant/test_feishu_worker_runtime.py` 的 probe launcher；production code、incident、design、delta-spec、progress evidence 与用户可观察行为均未改变。
- Round 2 对 R1-C1/R1-W1、M1-E5/E6/E7 和其余 Round 1 full 映射的结论继续有效；本轮完整 worker 文件再次单次全绿，pytest 仍无 resource-tracker semaphore warning。
- delta 没有触及架构边界、跨机契约、public interface 或产品旅程，因此不需要 full verification，也不需要重新派 product reviewer。

## Validation

- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_feishu_worker_runtime.py` → `8 passed, 2 warnings in 18.31s`；仅既有 lark SDK deprecation warnings。
- 冲突源码路径探针：外部 `PYTHONPATH=/Users/czj/Repos/nano-multiagent/src`，verify test module 显式加载后调用 owner-death test → passed。
- `KeyboardInterrupt` 注入：probe group 已含 owner/listener 后向 pytest PID 发 `SIGINT` → pytest exit 2；probe PGID 无残留。
- `TimeoutExpired` 注入：probe group 已含 owner/listener 后让首次 `communicate` 抛超时 → cleanup re-raise；probe PGID 无残留。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check tests/unit/personal_assistant/test_feishu_worker_runtime.py` → passed。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff format --check tests/unit/personal_assistant/test_feishu_worker_runtime.py` → already formatted。
- `git diff --check 9ec7b0bc6cffa8d195990f284d768ad01ddbcb9f..d8d6d84724c4884bec824259a12698acca581c1b` → passed。

## Issues

### CRITICAL（提 PR 前必须修）

- 无。

### WARNING（提 PR 前必须修）

- 无。

### SUGGESTION（可以修）

- 无。

All checks passed. Ready for PR.

# Corrected Delta Reconciliation

> Validation snapshot: `202949e2fb81ee3ed33443e5e1985a7b9ba49562 → 55d3a5c268a7a500de2dc186480074b07590a64f`

## Summary

- Mode: `corrected-delta`
- Outcome: `aligned`
- requires_full_verification: `false`
- Reconciled delta: `specs/gateway/external-channels.md`

## Requirement and Scenario Reconciliation

| Delta item | Final implementation evidence | Final test / product evidence | Outcome |
|---|---|---|---|
| Requirement: listener 与创建它的 Gateway 共享退出生命周期，重启只保留当前 listener，空闲不触发退出或重连 | worker bootstrap 在 listener target 前启动只等待 multiprocessing parent sentinel 的 watcher，sentinel 就绪后立即结束 worker（`src/personal_assistant/channels/feishu/worker.py:200-220`）；正常关闭仍使用既有 stop/join/terminate/kill（`:331-350`） | Round 2 真栈同时覆盖正常 stop/start、异常 owner death、逐条恢复消息与 10 秒 idle（`regression.md:148-176`）；最终完整 worker 文件为 `8 passed, 2 warnings in 38.13s` | aligned |
| Scenario: 正常停止或重启时回收旧 listener | parent 存活时 sentinel 不触发；`stop()` 设置 stop event 并完整 reap worker（`src/personal_assistant/channels/feishu/worker.py:331-375`） | 永久回归断言两个真实 spawn listener 均被正常 stop/join，且无需 terminate（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:222-250`）；Round 2 证明旧 identity 消失且新 Gateway 只有一个 current listener（`regression.md:150-150,162-163`） | aligned |
| Scenario: owner 未执行清理便消失后 3 秒内回收 listener | watcher 等待创建者 sentinel，并以进程级退出让 OS 回收 listener 持有的连接与 IPC（`src/personal_assistant/channels/feishu/worker.py:200-220`） | 两级真实 spawn 回归先确认 owner 原 process birth 消失，再以默认 3 秒上限等待 worker 原 birth 消失（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:126-165`）；Round 2 真栈测得 `0.004s` 且无超时清理参与（`regression.md:163-163`） | aligned |
| Scenario: 异常退出后按顺序恢复稳定消息路径 | 当前 listener 仍复用既有消息、回复和 shadow 路径；本 unit 只消除旧 listener 的存活与抢占条件，未修改消息语义 | Round 2 在确认唯一 current listener 后按“发一条、等待 exact reply、再发下一条”发送 A/B/C；三条飞书消息均恰有一次回复（`regression.md:152-152,169-170,188-190`） | aligned |
| Scenario: parent 存活时空闲不改变 listener 状态 | watcher 只等待 parent sentinel，没有消息空闲计时器、健康轮询或主动重连逻辑（`src/personal_assistant/channels/feishu/worker.py:200-218`） | 永久回归冻结 worker PID + birth，在 owner 存活且无入站期间持续断言同一 worker 存活（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:200-219`）；Round 2 真栈空闲 10 秒时同一 Gateway/worker birth、唯一 listener 与 `connected + fresh` 均保持不变（`regression.md:176-176`） | aligned |

## Uncovered Observable Behavior

无。最终产品/测试 delta 只引入并验证上述 owner-liveness 行为；没有新增未写入 delta-spec 的用户可观察变化。Round 2 记录的 #234 状态投影与 #231 shadow 双写已由同 fixture 的 origin/main 基线和独立 issue 证明为单元外既有行为（`regression.md:178-208`），不属于 bugfix-496 的 corrected delta，也不要求在本 unit 内修复。

## Conclusion

`external-channels.md` 与最终实现、永久回归和 Round 2 产品证据一致；无需重新执行 full verification。

# Round 5

> Validation snapshot: `d5a5fcfc3a800f154d9f8da0b7dbfbd5605565f7 → 85d89d9326534bfe451c912acc294f2b9d9bbc14`

## Summary

- Mode: `targeted-closure`
- Delta range: `d5a5fcfc3a800f154d9f8da0b7dbfbd5605565f7..85d89d9326534bfe451c912acc294f2b9d9bbc14`
- Focus issues: loaded-CI spawn setup budgets; separation from 3-second owner-death and 0.2-second forced-stop budgets; closed-process-safe restart assertions
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 4/4 focus areas closed |
| Correctness | 3/3 xdist focus nodes and 14/14 affected-file tests passed under CI-shaped load |
| Coherence | Followed；final delta remains test-only and preserves behavioral budgets |

## Targeted Closure

| Focus area | Final evidence | Outcome |
|---|---|---|
| 高负载 spawn setup 预算覆盖完整 worker 测试面 | d5 的完整 xdist 运行暴露 `test_stop_can_drain_or_drop_invalidated_generation` 仍从 `_runtime` 继承 5 秒启动上限。85d 将 `_runtime` 默认 join/setup 预算与两个直接 runtime 构造统一为 30 秒（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:112-123,260-283,301-331`）；最终两文件 xdist 完整运行 14/14 通过。 | closed |
| setup 与行为预算没有错误混合 | owner-death 仍在确认 owner process birth 消失后使用 `_wait_until` 默认 3 秒断言（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:25-31,150-165`）。backpressure adapter 只在启动期使用 30 秒，`stop` / `stop_invalidated` 调用前都将强制回收预算恢复为 0.2 秒（`tests/unit/personal_assistant/test_channel_lifecycle_failures.py:127-165`）。其余放宽路径的 worker 均会协作处理 stop event 或在 stop 前自行终止，不改变原行为断言。 | closed |
| restart-once 断言不再读取已 close 的 `multiprocessing.Process.pid` | 用例不再保留/读取 first runtime PID；它等待 first runtime dead、registry 精确指向第二个 adapter，并断言 `len(adapters) == 2`（`tests/unit/personal_assistant/test_channel_lifecycle_failures.py:177-216`）。这仍证明旧 listener 被回收、新 listener 已接管且只重启一次。 | closed |
| backpressure/status/restart 观测适应高负载 | terminal backpressure status 与 registry 接管均有 20 秒观测窗口（`tests/unit/personal_assistant/test_channel_lifecycle_failures.py:202-214`）；窗口只容纳 CI 调度/冷启动延迟，不改变 status code、旧 runtime dead、registry identity 和精确 adapter 数量断言。 | closed |

## Scope and Retained Conclusions

- `d5a5fcfc3..85d89d932` 只修改两个既有测试文件；没有 production code、incident、design、delta-spec、public interface、配置或用户可观察行为变化。
- corrected-delta 的 `aligned` 结论与 Round 2 产品证据继续有效；本轮不需要 full verification，也不需要 product re-review。

## Validation

- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q -n 4 --dist worksteal <idle> <two-listener> <backpressure-restart>` → `3 passed, 8 warnings in 44.80s`。
- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q -n 4 --dist worksteal tests/unit/personal_assistant/test_feishu_worker_runtime.py tests/unit/personal_assistant/test_channel_lifecycle_failures.py` → `14 passed, 8 warnings in 95.19s`。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check tests/unit/personal_assistant/test_feishu_worker_runtime.py tests/unit/personal_assistant/test_channel_lifecycle_failures.py` → passed。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff format --check tests/unit/personal_assistant/test_feishu_worker_runtime.py tests/unit/personal_assistant/test_channel_lifecycle_failures.py` → already formatted。
- `git diff --check d5a5fcfc3a800f154d9f8da0b7dbfbd5605565f7..85d89d9326534bfe451c912acc294f2b9d9bbc14` → passed。

## Issues

### CRITICAL（提 PR 前必须修）

- 无。

### WARNING（提 PR 前必须修）

- 无。

### SUGGESTION（可以修）

- 无。

All checks passed. Ready for PR.

# Round 6

> Validated code tree: `7dcc8088c5c083f2bd7d2d16d6b590d5214659f5`
>
> Fix delta: `85d89d9326534bfe451c912acc294f2b9d9bbc14..7dcc8088c5c083f2bd7d2d16d6b590d5214659f5`

## Summary

- Mode: `targeted-closure`
- Focus issues: parent-only startup wrapper; independent setup/graceful/forced-stop/owner-death budgets; non-additive terminal predicates; loaded normal-stop false termination
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 4/4 focus areas closed |
| Correctness | 4/4 xdist focus nodes and 14/14 affected-file tests passed under CI-shaped load |
| Coherence | Followed；final changes remain test-only and do not weaken lifecycle assertions |

## Targeted Closure

| Focus area | Final evidence | Outcome |
|---|---|---|
| 30 秒 startup wrapper 只位于 parent test runtime，不进入 child/pickle | production runtime 先用原始 multiprocessing Event 构造 child context 与 `Process` args（`src/personal_assistant/channels/feishu/worker.py:261-279`）；测试随后才仅替换 parent runtime 的 `_ready_event.wait` 入口（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:112-132`；`tests/unit/personal_assistant/test_channel_lifecycle_failures.py:138-157`）。独立身份探针确认 child args 仍持有原始 Event，wrapper 与 child Event 不是同一对象；所有真实 spawn 用例通过，因此 lambda/SimpleNamespace 没有进入 child pickle。 | closed |
| setup、normal graceful stop、forced stop 与 owner-death 预算彼此独立 | parent ready wait 为 30 秒；worker runtime 测试 helper 的 5 秒只用于正常 cooperative stop（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:112-132`）；noncooperative pressure adapter 仍为 0.2 秒（`tests/unit/personal_assistant/test_channel_lifecycle_failures.py:128-168`）。owner 原 process birth 消失后的 listener 断言仍使用 `_wait_until` 默认 3 秒（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:25-31,150-174`）。 | closed |
| backpressure restart 观测不再叠加局部超时 | first restart 在单一 45 秒 predicate 内同时要求 terminal status、精确两个 adapter、first runtime dead 和 registry 指向 second（`tests/unit/personal_assistant/test_channel_lifecycle_failures.py:180-218`）。sequential retry 在单一 80 秒 predicate 内同时要求四次尝试结算、registry 为空且全部 runtime dead，稳定后仍断言没有第五次自动重启（`:221-264`）。 | closed |
| 高负载正常 stop 不再被 1 秒调度窗口误判为需强制 terminate | d7 在本轮四节点聚焦和两文件完整运行中均复现 dual-listener `terminated=True`。7dcc 仅将测试 helper 的 normal graceful-stop 预算改为 5 秒（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:112-124`）；最终同等负载下用例仍断言两个 worker 均 `joined` 且均未 `terminated`（`:235-263`），聚焦与完整门禁全绿。 | closed |

## Scope and Retained Conclusions

- 最终 validated code tree 为 `7dcc8088c`；该 tree 通过 `bc8e80e36` 继承 Round 5 报告，本轮产品/test 变更仍只涉及两个既有测试文件。production code、incident、design、delta-spec、public interface、配置与用户可观察行为均未变。
- corrected-delta 的 `aligned` 结论与 Round 2 产品证据继续有效；无需 product re-review，也无需 full verification。

## Validation

- parent/child ready-event 身份探针 → parent wrapper 与 child args 中的原始 Event 分离，test helper graceful `join_timeout=5`。
- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q -n 4 --dist worksteal <idle> <two-listener> <backpressure-restart> <backpressure-retry>` → `4 passed, 8 warnings in 83.16s`。
- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q -n 4 --dist worksteal tests/unit/personal_assistant/test_feishu_worker_runtime.py tests/unit/personal_assistant/test_channel_lifecycle_failures.py` → `14 passed, 8 warnings in 74.06s`。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check tests/unit/personal_assistant/test_feishu_worker_runtime.py tests/unit/personal_assistant/test_channel_lifecycle_failures.py` → passed。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff format --check tests/unit/personal_assistant/test_feishu_worker_runtime.py tests/unit/personal_assistant/test_channel_lifecycle_failures.py` → already formatted。
- `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` → `documentation integrity passed`。
- `git diff --check 85d89d9326534bfe451c912acc294f2b9d9bbc14..7dcc8088c5c083f2bd7d2d16d6b590d5214659f5` → passed。

## Issues

### CRITICAL（提 PR 前必须修）

- 无。

### WARNING（提 PR 前必须修）

- 无。

### SUGGESTION（可以修）

- 无。

All checks passed. Ready for PR.

# Round 7

> Validated code tree: `49003be13f94210f35e09a819e34d253f0a2710f`
>
> Fix delta: `7dcc8088c5c083f2bd7d2d16d6b590d5214659f5..49003be13f94210f35e09a819e34d253f0a2710f`

## Summary

- Mode: `targeted-closure`
- Focus issue: sequential retry terminal wait must leave cleanup headroom inside pytest's 90-second hard timeout
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 focus issue closed |
| Correctness | Exact xdist retry test passed with the final 45-second terminal window |
| Coherence | Followed；delta only shortens a test observation ceiling |

## Targeted Closure

| Focus area | Final evidence | Outcome |
|---|---|---|
| terminal wait 与 hard timeout / cleanup 预算一致 | pytest 全局 hard timeout 为 90 秒（`pyproject.toml:82-90`）。sequential retry 仍使用单一终态 predicate，同时要求四次尝试结算、registry 为空且全部 runtime dead；唯一行为变化是最终等待上限从 55 秒收紧为 45 秒（`tests/unit/personal_assistant/test_channel_lifecycle_failures.py:247-258`）。45 秒最多占用 hard timeout 的一半，比 55 秒方案多留 10 秒清理余量；`finally` 仍调用 `manager.close()`，pressure adapter 的强制 stop 预算仍为 0.2 秒（`:128-168,263-264`）。精确 xdist 用例在 22.91 秒内完成。 | closed |

## Scope and Retained Conclusions

- 相对 Round 6 validated tree，唯一新的实质代码变化是上述测试 timeout 常量；其余 diff 是 Round 6 报告与 merge 历史。没有 production code、spec、design、public interface、配置或用户可观察行为变化。
- Round 6 对 parent-only startup wrapper、5 秒 normal graceful stop、0.2 秒 pressure forced stop、3 秒 owner-death 以及 45 秒 first-restart predicate 的结论均未被触及；corrected-delta 仍为 `aligned`。
- 无需 product re-review，也无需 full verification。

## Validation

- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q -n 4 --dist worksteal tests/unit/personal_assistant/test_channel_lifecycle_failures.py::test_backpressure_retry_budget_reaps_final_listener_and_allows_manual_retry` → `1 passed, 8 warnings in 22.91s`。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check tests/unit/personal_assistant/test_channel_lifecycle_failures.py` → passed。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff format --check tests/unit/personal_assistant/test_channel_lifecycle_failures.py` → already formatted。
- `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` → `documentation integrity passed`。
- `git diff --check 7dcc8088c5c083f2bd7d2d16d6b590d5214659f5..49003be13f94210f35e09a819e34d253f0a2710f` → passed。

## Issues

### CRITICAL（提 PR 前必须修）

- 无。

### WARNING（提 PR 前必须修）

- 无。

### SUGGESTION（可以修）

- 无。

All checks passed. Ready for PR.
