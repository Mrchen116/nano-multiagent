# perf-458-M1: ci-fast-path — Tasks

> 对齐: ../design.md（2026-07-10）

## 目标

在不改变 Python/Frontend 门禁范围和产品行为的前提下，移除非 e2e Python 测试中的确定性等待，并让 GitHub Actions 以 6 个 xdist worker 和 setup-python pip cache 执行完整门禁，使常规成功 CI 的 required checks 在 runner 开始后 90 秒内完成。

## 退出标准

- [x] 五条 IM 慢测改用 `source=mirror` 读取持久化配置，不再等待 live-config 5 秒 fallback；专门 live-config 测试继续通过。
- [x] 两条 ShellRunner stop 负断言改为等待 monitor 清理 `_stopped` 的完成条件，保留“不触发失败回调”的行为断言。
- [x] 输出上限测试保留生产常量为 256 MiB 的断言，并以测试内小上限覆盖保留/截断行为，不再写满 256 MiB。
- [ ] Python job 保留 ruff、format 与完整 non-e2e pytest，改为 6 worker worksteal，输出慢用例摘要，并启用 setup-python pip cache。
- [ ] `.venv/bin/pytest -m "not e2e" -n 6 --dist worksteal` 连续两轮、完整串行 non-e2e、ruff 两门和 frontend vitest 全绿。
- [ ] 真实 GitHub Actions 至少三次成功 run 的 required checks 执行时间均不超过 90 秒；check 名称和失败阻断语义不变。
- [ ] `src/` 零修改，四包 no spec delta；性能证据和回滚结论记录在 `progress.md`。

## 测试策略

- 被测行为（来自退出标准）：IM 创建/配置同步旅程仍保留原创建、PATCH、`config.sync`、relay 断言但不额外验证 live-config；ShellRunner stop 后不触发 `on_fail` 且 `_stopped` 最终清理；Bash 输出上限内保留内容、越界仅写一次截断提示且生产上限仍为 256 MiB；CI 仍运行两门 lint、完整 non-e2e pytest 和完整 vitest。
- 已有测试在：`tests/im_service/integration/test_agent_create_flow.py`、`test_gateway_im_direct_chat.py`、`test_gateway_im_group_chat.py`、`test_heartbeat_config_sync_pipeline.py`、`test_gateway_im_roundtrip.py`、`test_agent_config_api.py`（改写/回归）；`tests/unit/agent/background_tasks/test_platform_adapters.py`（改写）。不新建测试文件。
- 落层/目录/marker：`tests/im_service/integration/` 与 `tests/unit/agent/background_tasks/`，marker：无；完整门禁继续以 `-m "not e2e"` 排除 e2e。
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

- 状态: DOING
- 步骤: 记录当前 workflow 缺少 cache/并行/slow-duration 输出的 Verify 证据；增加 dev 依赖和最小 workflow 配置；运行完整并行、串行、lint 与 frontend 门禁。
- 验证: 本地全部门禁全绿；unit PR 上至少三次常规成功 Actions run 的 required checks 执行时间均不超过 90 秒，Python/Frontend check 名称不变；通过一次真实失败 run 确认失败阻断语义。
