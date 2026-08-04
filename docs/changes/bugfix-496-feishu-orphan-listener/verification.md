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
