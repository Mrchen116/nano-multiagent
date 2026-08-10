# bugfix-525-M2: acceptance-closure — Tasks

> 对齐: ../design.md（2026-08-10 Changelog 与 Milestone 表）

## 目标

提供一条不依赖真实模型、生产飞书或用户配置的确定性真栈验收入口：从隔离 IM 的公开 HTTP/WebSocket（与 Web IM 相同 relay）驱动 production Gateway，证明 self-evolution no-save 原始输出保持私有，并证明 terminal 后真实 `skill_manage(create)` 经 persistent owner、transport reconnect/replay 与 config sync 生效。

## 退出标准

- [x] 受控 OpenAI-compatible fixture 只按显式 scenario state、请求序号、message role/tool-call 结构驱动，不匹配 self-evolution 私有 prompt 文案。
- [x] no-save 真栈旅程有 fixture-owned 正向执行事实，前台回答完成，IM 历史无 raw `Nothing to save.`、review prompt 或错误栈。
- [x] skill 真栈旅程在前台 terminal 后放行真实 `skill_manage(create)`，受控切断一次 persistent stream 并经 replay 恢复；IM 恰好一条 skills structured notice，workspace Skill 与 explicit allowlist 同步。
- [x] 后续全新 conversation/session 实际调用 `skill_view` 读取新 Skill 并完成可见回复。
- [x] reviewer 一条命令可运行两条旅程；IM/Gateway/LLM fixture 端口、配置、workspace、PID 与 fault state 都在 worktree-local runtime，teardown 后进程/监听端口/敏感生成文件已清理。
- [x] focused E2E、M1 routing cross-layer tests、全量非 E2E（按最终风险决定）、Ruff、docs-check 与 `git diff --check` 全绿。

## 测试策略

- 保护的回归风险与可观察 seam: R1-I1 通过 fixture control state 证明 no-save review 真执行，同时只从 IM 公开消息历史观察 raw 输出缺席；R1-I2 通过真 IM/Gateway、真实 tool call、persistent stream fault/replay、IM Agent config 与新 session tool timeline 观察最终产品状态。
- 已有保护与处置: M1 的 `tests/integration/test_self_evolution_output_visibility.py`、`test_self_evolution_gateway_skill_sync.py` 与 Gateway unit tests 保留为最低层分类/owner 保护；本 milestone 新风险是跨真进程装配与 reviewer 可重复性，只有 E2E 能暴露，不在低层重复其内部断言。
- 落层/目录/marker: `tests/e2e/critical_paths/`，marker: `e2e`；真实 IM/Gateway/HTTP LLM 进程和公开 relay 是最低能暴露 acceptance harness 失效的层。
- 文件归属: 新建语义 owner `test_self_evolution_visibility_critical_path.py`，扩展既有 `_im_gateway.py` / `_im_client.py` 仅复用 Gateway restart 与 explicit config API；fixture 归 `scripts/fixtures/`，reviewer 入口归 `scripts/e2e-self-evolution.sh`。
- 可选依赖 importorskip: 沿用 `_im_ws.py` 对 `websockets` 的模块级 `pytest.importorskip`；HTTP 使用仓库必需依赖 `httpx`。
- 本 milestone 产生的一次性验收证据(收尾删除,不进套件): worktree-local pytest basetemp runtime；最终只把命令、脱敏可观察摘要与清理结果写入 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| self-evolution raw privacy 与真实 memory/skill side effect | `tests/integration/test_self_evolution_output_visibility.py` | keep | 最低 Kernel seam 仍有效；E2E 只补真进程装配/产品入口风险 | focused integration + new E2E |
| terminal 后 persistent owner/config sync | `tests/integration/test_self_evolution_gateway_skill_sync.py` | keep | 继续快速定位 Gateway lifecycle failure；E2E 证明 production composition/public IM 结果 | focused integration + new E2E |
| subscriber reconnect/cursor 与 single owner | `tests/unit/personal_assistant/test_background_session_events.py`, `test_background_subscription_manager.py` | keep | 低层时序矩阵仍是稳定 owner；E2E 仅用一次受控 fault 证明真栈接线 | focused unit + new E2E |
| fake-LLM 真栈起停与 Gateway restart | `tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py`, `_im_gateway.py`, `_im_client.py` | keep | 复用成熟 fixture/lifecycle，不另造平行进程管理 | existing E2E + new E2E |

前端 UI：N/A。本 milestone 不改客户端；product entry 使用 Web IM 相同公开 relay，断言来自 IM REST/WS 的持久产品状态。

Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — controlled no-save 真栈

- 状态: DONE
- 步骤: 先写失败的 critical-path E2E；再实现 OpenAI-compatible fixture、隔离配置与 no-save scenario state/正向事实。
- 验证: 单条 E2E 红（fixture/能力缺失）→ 绿；既有 controlled-LLM E2E 继续通过。

### R2 — terminal 后 Skill create + replay + 新 session 使用

- 状态: DONE
- 步骤: 先扩失败旅程；再加入只作用于 fixture Gateway 进程的一次 stream fault，真实 `skill_manage(create)`、explicit config sync 与新 session `skill_view` 闭环。
- 验证: skill E2E 红→绿；M1 subscriber/manager/config-sync focused suites 通过。

### R3 — reviewer 入口、清理与质量门禁

- 状态: DONE
- 步骤: 增加 worktree-local 一键 runner 与 fixture 文档/critical-path catalog；亲自运行两条旅程，核对进程/端口/生成文件清理并回填 durable evidence。
- 验证: runner all 通过；Ruff、docs-check、diff-check、相关跨层测试及按风险选择的 non-E2E suite 全绿。
