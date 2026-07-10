# Verification Report: perf-458

## Summary

Mode: full  
Delta range: N/A  
Focus issues: N/A  
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 7/7 tasks；3/3 requirements |
| Correctness | 4/4 scenarios |
| Coherence | Followed |

本 unit 的首文档是 `motivation.md`，无独立 `spec.md`；以下以其 3 条 Requirement、4 个 Scenario 为 WHAT 合约。最终合约已在 `design.md:9,83-89,176-183,185-203` 和 `M1-ci-fast-path/tasks.md:5-17` 明确收口为稳定的 4-worker 方案，并按用户决策接受三次 required checks 94/91/96 秒的 90 秒验收例外。废弃的 n6/n8 探索不作为实现要求。

All checks passed. Ready for PR.

## Completeness

- Tasks: 7/7 complete（`M1-ci-fast-path/tasks.md:9-17`），逐项代码、测试与远端证据均已核对，不存在仅勾选未实现项。
- Requirement 1「常规代码 PR 获得显著更快的完整反馈」：`.github/workflows/ci.yml:18-34` 启用 pip cache、固定 n4 worksteal 和 durations；真实 Actions run `29097094967` attempts 1/2/3 均 success，`Python checks` 分别 94/91/96 秒，相比 motivation 约 3分34秒基线大幅缩短。该 run 的 head `6236644b` 与当前 HEAD 在 `.github/workflows/ci.yml`、`pyproject.toml`、`tests/` 上无差异。
- Requirement 2「CI 质量信号保持不变」：`.github/workflows/ci.yml:27-34,36-57` 保留 ruff、format、完整 non-e2e pytest 与完整 vitest；run `29097895298` attempt 2 中 pytest 失败使 `Python checks` 和 workflow 均为 failure。当前 HEAD 的并行、串行、前端与 lint 门禁全部通过。
- Requirement 3「优化后的门禁不增加日常运维负担」：`.github/workflows/ci.yml:12-25,36-53` 继续使用 `ubuntu-latest`、setup-python/setup-node、pip/npm 与标准 PR workflow，无专用 runner、额外服务或人工准备步骤。
- Prototype / Reference 覆盖：N/A（不改 UI、无原型/reference contract；`M1-ci-fast-path/tasks.md:19-26`）。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 合法代码变更通过全部门禁 | `.github/workflows/ci.yml:12-34,36-57`；`pyproject.toml:32-44` | Actions run `29097094967` attempts 1/2/3 全部 success；当前 HEAD n4 全量 3444 passed, 2 skipped | covered（90 秒按最终合约例外） |
| 代码违反现有检查要求 | `.github/workflows/ci.yml:27-34,52-57` | Actions run `29097895298` attempt 2：pytest step、`Python checks`、workflow 均 failure | covered |
| 产品既有行为回归 | 产品 `src/` 零修改；旅程断言保留于 `test_agent_create_flow.py:120-220`、`test_gateway_im_direct_chat.py:221-290`、`test_gateway_im_group_chat.py:124-170`、`test_gateway_im_roundtrip.py:190-214`、`test_heartbeat_config_sync_pipeline.py:203-249` | 当前 HEAD：n4/串行 non-e2e 均 3444 passed, 2 skipped；目标与 live-config 守护 51 passed；Frontend 63 files / 615 tests passed | covered |
| 贡献者在普通托管 runner 重跑 CI | `.github/workflows/ci.yml:14-25,38-53` | 同一标准 PR run 三次 rerun success，无自建服务或机器 | covered |

慢测改写与原行为的逐项核对：

- 五条 IM 旅程只把持久化版本读取改成 `source=mirror`（`test_agent_create_flow.py:170-195`、`test_gateway_im_direct_chat.py:236-253`、`test_gateway_im_group_chat.py:124-144`、`test_gateway_im_roundtrip.py:190-211`、`test_heartbeat_config_sync_pipeline.py:203-233`）；创建、PATCH、`config.sync`、relay 与下游状态断言仍在。live 协议由 `test_agent_config_api.py:161-248` 独立覆盖。
- ShellRunner 两条负断言改为等待 monitor 消费 `_stopped` 的真实终态，再断言不触发 failure（`test_platform_adapters.py:293-341,344-390`），未缩短生产 timeout 或修改 `src/`。
- 输出上限测试先锁定生产常量 256 MiB，再以测试内 1 KiB 上限覆盖上限内保留、越界丢弃及截断提示只写一次（`test_platform_adapters.py:171-190`）。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1 只消除测试确定性等待，不改生产 timeout | 是 | 仅测试改写；`test_agent_create_flow.py:170-195`、`test_platform_adapters.py:171-190,293-390`；`src/` diff 为空 |
| D2 单一 Python job，固定 n4 worksteal，不拆 matrix | 是 | `.github/workflows/ci.yml:12-34` |
| D3 沿用 pip，仅启用 setup-python 原生缓存 | 是 | `.github/workflows/ci.yml:18-25`；`pyproject.toml:32-44` |
| D4 Frontend job 保持不变 | 是 | `.github/workflows/ci.yml:36-57`；相对基线 frontend job 无 diff |
| D5 用 Actions 时间戳与 pytest durations 验收 | 是 | `.github/workflows/ci.yml:33-34`；`M1-ci-fast-path/progress.md:48-80` |

- 架构自洽：改动限于 CI、dev dependency 与既有测试文件；没有 `src/`、产品契约或跨包 import 变化，也没有新增平行门禁、跨机假设或复杂调度机制。
- 测试规范：沿用既有最低有效层与测试文件，没有新增一次性脚本、skip/xfail 或重复测试；性能 timing 作为验收证据记录在 progress，而非永久测试逻辑（符合 `docs/TESTING_GUIDE.md:7-14,31-47,58-75`）。
- 项目规范：`git diff --check`、ruff check、ruff format 均通过；无新增 public API/TODO/FIXME，注释与模块边界无偏离。

### Prototype / Reference Contract

N/A（design 无前端原型/reference artifact，本 unit 不改前端源码或 UI）。

## Verification Evidence

- Targeted regression: 51 passed in 9.19s（五条 IM 旅程、live-config 守护、platform adapters；n4 worksteal）。
- Full Python parallel: 3444 passed, 2 skipped in 32.77s。
- Full Python serial: 3444 passed, 2 skipped, 22 deselected in 97.69s。
- Python lint/format: `ruff check .` 全绿；769 files already formatted。
- Frontend: `npm ci && npm run test` → 63 files / 615 tests passed in 10.40s。
- Remote success: run `29097094967` attempts 1/2/3，`Python checks` 94/91/96 秒，`Frontend checks` 57/67/71 秒，三次 workflow 均 success。
- Failure blocking: run `29097895298` attempt 2 的 pytest、`Python checks` 与 workflow 均 failure；该 n8 run 仅用于验证失败阻断语义，不属于最终 n4 实现。

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（应该修）

- None.

### SUGGESTION（可以修）

- None.
