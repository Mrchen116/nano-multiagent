# bugfix-533-M1: 恢复 Feishu worker 轻量冷启动 seam — Tasks

> 对齐: ../fix.md

## 目标

恢复 spawn 子进程在 `ready_event` 前只加载轻量 worker 模块的既有边界，使配置了飞书 channel 的 Gateway 在生产默认启动 budget 内稳定初始化；保留 parent-sentinel、正常 stop/join、crash status、IPC 顺序和消息语义。

## 退出标准

- [ ] 隔离导入 `personal_assistant.channels.feishu.worker` 不加载 `feishu.client` 或 `lark_oapi`。
- [ ] 真实 `spawn` worker 使用生产默认 ready budget 初始化成功，不复用测试专用 30 秒 wrapper。
- [ ] 现有 Feishu worker lifecycle、消息与 Gateway composition 覆盖通过，完整 non-E2E 门禁通过。
- [ ] 专用非 default Feishu E2E profile 连续两次无预热 clean start 成功，并完成真实 user → Bot → Gateway → 唯一 IM shadow 旅程；本次进程和敏感 runtime 产物均已清理。

## 测试策略

- 保护的回归风险与可观察 seam: fresh interpreter 导入 worker 时的 `sys.modules` 边界，以及真实 `multiprocessing.get_context("spawn")` 下 `FeishuWorkerRuntime.start()` 使用生产默认 5 秒 ready budget 的成功结果。
- 已有保护与处置: `tests/unit/personal_assistant/test_feishu_worker_runtime.py`（keep）与 `tests/unit/personal_assistant/test_channel_lifecycle_failures.py`（keep）；前者保护 parent-sentinel、stop/join、crash/IPC，后者保护 ChannelManager lifecycle，但二者的 30 秒测试 wrapper 未保护生产启动 seam。
- 落层/目录/marker: `tests/unit/personal_assistant/`，marker: 无；fresh interpreter import 与单个真实 spawn runtime 是暴露同一启动失败原因的最低层，外部平台旅程作为一次性 live 验收而非默认测试。
- 文件归属: 新建 `tests/unit/personal_assistant/test_feishu_worker_startup.py`；现有 runtime 文件已超过 400 行，且启动 import/budget 是独立语义 owner，不继续向超长 lifecycle 文件堆行为。
- 可选依赖 importorskip: 无；`lark_oapi` 是项目正式依赖，但本回归正是断言 worker bootstrap 前不加载它。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）: `e2e-up.sh --feishu` 两轮 clean-start 运行日志定位、`e2e-feishu-probe.py` 真消息结果、IM shadow API/数据库脱敏核对与清理证据；摘要写入 `progress.md`，凭据、完整日志、数据库和 runtime config 不提交。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| parent-sentinel、正常 stop/join、crash status 与 IPC | `tests/unit/personal_assistant/test_feishu_worker_runtime.py` | keep | 修复不改 worker bootstrap/lifecycle；保留原最低层行为保护 | focused pytest |
| ChannelManager retry、reap 与生产 lifecycle 接线 | `tests/unit/personal_assistant/test_channel_lifecycle_failures.py` | keep | 修复只收窄导入边界，不改 lifecycle owner 或 timeout | focused pytest |
| Gateway 两个 Feishu composition 入口 | 相关 Gateway unit/contract suite | keep | package re-export 调用方改为正式 adapter 子模块后，现有 composition 覆盖继续验证接线 | related + full non-E2E |

前端 UI: N/A。

## Roadpoints

### R1 — 固定轻量 import 与生产 spawn budget

- 状态: DONE
- 步骤: 先加入 fresh-interpreter import contract 与未包装的真实 spawn 回归并确认 deterministic red；再移除包级 eager re-export，让两个 Gateway 调用方直接从正式 adapter 模块导入。
- 验证: 新测试先红后绿；确认 `worker.py`、`client.py` 的 bootstrap target、parent-sentinel、status/IPC 逻辑无修改。

### R2 — 验证 Feishu lifecycle 与仓库门禁

- 状态: DOING
- 步骤: 跑新启动回归、现有 worker/lifecycle、相关 Feishu/Gateway tests、Ruff、format、diff、docs gates 与完整 non-E2E。
- 验证: 所有相关门禁绿；记录初始 full-suite heartbeat shared-host timing flake、串行 exact 复证和最终 full-suite 结果，不修改 out-of-scope timeout。

### R3 — 两轮 clean start 与真实飞书旅程

- 状态: TODO
- 步骤: 按 worktree runtime 契约使用专用非 default Feishu E2E profile，连续两次无预热 clean start；最终从测试用户向 Bot 发消息，核对 Bot 回复、Gateway 接收与 IM 唯一 shadow；执行配对 down 和端口/进程/敏感产物清理。
- 验证: 两轮启动均未出现 `feishu worker did not initialize`；最终 probe 与 shadow 唯一性成立；回填 `fix.md` 修复/验证和本 progress。
