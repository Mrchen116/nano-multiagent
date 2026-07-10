# perf-458-M1: ci-fast-path — Tasks

> 对齐: ../design.md（2026-07-10）

## 目标

在不改变 Python/Frontend 门禁范围和产品行为的前提下，移除非 e2e Python 测试中的确定性等待，并让 GitHub Actions 以稳定的 4 个 xdist worker 和 setup-python pip cache 执行完整门禁，大幅缩短反馈时间；90 秒目标按用户最终决策接受验收例外。

## 退出标准

- [x] 五条 IM 慢测改用 `source=mirror` 读取持久化配置，不再等待 live-config 5 秒 fallback；专门 live-config 测试继续通过。
- [x] 两条 ShellRunner stop 负断言通过 stopper `wait()` 等待 monitor 线程真正结束，再验证“不触发失败回调”和 `_stopped` 清理。
- [x] connected-but-silent Gateway 的 live-config timeout fallback 由零等待 unit test 独立守护，删除 fallback 时测试稳定转红。
- [x] 输出上限测试保留生产常量为 256 MiB 的断言，并以测试内小上限覆盖保留/截断行为，不再写满 256 MiB。
- [x] Python job 保留 ruff、format 与完整 non-e2e pytest，改为 4 worker worksteal，输出慢用例摘要，并启用 setup-python pip cache。
- [x] `.venv/bin/pytest -m "not e2e" -n 4 --dist worksteal`、完整串行 non-e2e、ruff 两门和 frontend vitest 全绿。
- [x] 真实 GitHub Actions 三次 success 为 94/91/96 秒，check 名称不变；n8 真实失败证明 Python check 红会阻断。三次全部 ≤90 秒未满足，按用户明确决策停止调参并接受验收例外。
- [x] 仅在内部 ShellRunner stopper 增加 monitor `wait()` testability seam；不改变 `stop()`、生产 timeout 或消费者可观察行为，四包 no spec delta。

## 测试策略

- 被测行为（来自退出标准）：IM 创建/配置同步旅程保留原创建、PATCH、`config.sync`、relay 断言；connected-but-silent Gateway 仍走 live-config timeout fallback；ShellRunner stop 后 monitor 完成且不触发 `on_fail`、`_stopped` 最终清理；Bash 输出上限内保留内容、越界仅写一次截断提示且生产上限仍为 256 MiB；CI 仍运行两门 lint、完整 non-e2e pytest 和完整 vitest。
- 已有测试在：`tests/im_service/integration/test_agent_create_flow.py`、`test_gateway_im_direct_chat.py`、`test_gateway_im_group_chat.py`、`test_heartbeat_config_sync_pipeline.py`、`test_gateway_im_roundtrip.py`、`test_agent_config_api.py`（改写/回归）；`tests/im_service/unit/test_gateway_handler.py`（扩展 timeout fallback）；`tests/unit/agent/background_tasks/test_platform_adapters.py`（改写）。不新建测试文件。
- 落层/目录/marker：`tests/im_service/integration/`、`tests/im_service/unit/` 与 `tests/unit/agent/background_tasks/`，marker：无；完整门禁继续以 `-m "not e2e"` 排除 e2e。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无一次性脚本；本地与 GitHub Actions timing 命令/结果直接记录在 `progress.md`。
- 前端 UI 状态矩阵、用户路径分类、测试与验收映射、Prototype / Reference Contract：N/A（不改前端源码或 UI，Frontend job 仅回归验证）。

## Roadpoints

### R1 — 移除 IM integration 的 live-config 固定等待

- 状态: DONE
- 步骤: 先量取五个目标测试的耗时并记录 Verify 证据；把仅需持久化版本的 GET 改为 `source=mirror`，删除无关的 `agent.config.get/agent.config` 往返；保留原创建、PATCH、同步与 relay 行为断言。
- 验证: 五个目标测试全绿且耗时显著下降；`tests/im_service/integration/test_agent_config_api.py` 全绿，证明专门 live-config 协议覆盖未丢失。

### R2 — 消除 ShellRunner 与输出上限测试的确定性成本

- 状态: DONE
- 步骤: 先量取三条目标测试的耗时并记录 Verify 证据；stop 测试改为条件轮询 monitor 完成；输出上限测试断言 256 MiB 生产常量并 monkeypatch 小上限覆盖边界。
- 验证: `test_platform_adapters.py` 全绿；目标三条耗时显著下降；stop 失败回调/清理语义和截断行为保持。

### R3 — 接入 xdist、pip cache 与完整门禁

- 状态: DONE
- 步骤: 记录当前 workflow 缺少 cache/并行/slow-duration 输出的 Verify 证据；增加 dev 依赖和最小 workflow 配置；运行完整并行、串行、lint 与 frontend 门禁。
- 验证: 本地全部门禁全绿；4-worker 远端三次 Actions run 均 success，required checks 为 94/91/96 秒，Python/Frontend check 名称不变；n8 探索中的真实失败 run 确认失败阻断语义。用户接受未达到 90 秒的最终结果。

### R4 — 关闭 code-review 测试信号缺口

- 状态: DONE
- 步骤: 用 base/head mutation 对照确认两处假绿后，增加零等待 live timeout unit 回归；让 shell stopper 暴露 monitor 线程完成等待，并以 join 后断言替代 `_stopped` 中间状态轮询。
- 验证: 删除 timeout fallback、或在 marker 清理后错误触发 `on_fail` 时，两条修复后测试均稳定转红；恢复实现后定向、完整串行与 n4 门禁全绿。
