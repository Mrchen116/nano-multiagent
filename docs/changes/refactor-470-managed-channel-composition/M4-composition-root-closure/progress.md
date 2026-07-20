# refactor-470-M4 — Progress

## 启动记录

- 测试基线根因：M4 worktree 没有独立 `.venv`，因此 `.venv/bin/pytest` 为不存在路径（exit 127）；仓库根的共享 `.venv` 存在。后续以 `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest` 在 M4 worktree 运行，不改环境或产品代码。
- Design 修订：无。

## R1 — 固化 composition root 边界与对账基线

- Context: M4 的成功不是仅移动 `main.py`，而是删除 test-only service locator 并保证 38 个基线引用逐一可审计。
- Decision: 以 `rg -l 'personal_assistant\\.main|from personal_assistant import main' src tests scripts` 的 38 文件作为基线，按真实 owner、入口保留、命令字符串/测试说明三类对账；contract 只守用户可观察的入口边界，不测试私有实现。
- Rationale: owner migration 可保持现有行为回归价值，并避免把一次性迁移路径做成脆弱测试。
- Evidence:
  - Tests: 基线运行中；共享 `.venv` 已定位。
  - Entry: R3 完成前待验。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: R2/R3 完成前待验。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 删除本 milestone 分支的 R1 变更。
- Commits: C1=pending, C2=pending, C3=pending。
- Next: 基线完成后写入 C1 contract 与 38-file 对账结论。

## R1 — composition root 边界与 38-file 对账

- Context: `main.py` 曾同时是 CLI、composition root 和测试 service locator；M4 必须在不保留 private alias 的前提下完成真实 owner 迁移。
- Decision: `personal_assistant.main` 保留唯一公开 `main()` 和 CLI 命令字符串；`gateway.composition.compose_gateway()` 成为唯一 runtime factory。测试依赖具体职责 owner，不依赖入口模块。
- Rationale: CLI 命令仍需要稳定模块路径，而 runtime、delivery、session、heartbeat 等职责已有具名 owner；将它们混在入口会重新形成事实 re-export。
- Evidence:
  - Tests: `tests/contract/test_personal_assistant_main_contract.py` 的旧入口表面 Red，确认当时尚无 `composition` 模块（C1=`c67f05fb2`）；最终 architecture contracts 23 passed。
  - Entry: `scripts/e2e-critical.sh -k 'gateway_im_resilience or restart_session_continuity'` 为真 IM + 真 Gateway 进程，3 passed，40.90s。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 见 R3；cron path 因本机持久配置不含该测试固定模型而无法注册 LLM provider，非本次迁移回归。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `2f23bad9b`。
- Commits: C1=`c67f05fb2`，C2=`2f23bad9b`，C3=本次 progress commit。

### 38-file baseline 对账

基线命令为 `git grep -lE 'personal_assistant\\.main|from personal_assistant import main|import personal_assistant\\.main' origin/unit/refactor-470 -- src tests scripts`。以下逐项列出结论；“保留”仅表示 CLI 模块名是用户/子进程入口，不表示测试或生产代码从 `main` 获得内部实现。

| Baseline file | 结论 | 迁移后 owner / 理由 |
|---|---|---|
| `src/personal_assistant/main.py` | 保留 | 唯一 CLI entry，`__all__ = ["main"]`。 |
| `src/personal_assistant/gateway/process_lifecycle.py` | 保留并迁移 | 子进程继续执行 `-m personal_assistant.main`；runtime config/factory lazy import 改至 `gateway.composition`。 |
| `scripts/e2e-resilience.sh` | 保留 | 真 Gateway CLI 启动命令。 |
| `scripts/e2e-up.sh` | 保留 | worktree 真 Gateway CLI 启动命令。 |
| `scripts/fixtures/README.md` | 保留 | fixture 操作说明中的 CLI 命令。 |
| `scripts/fixtures/anthropic_sse_error.py` | 保留 | fixture 启动真实 CLI entry。 |
| `scripts/fixtures/channel_cache_commit_failure.py` | 保留 | `runpy` 执行真实 CLI entry。 |
| `tests/contract/test_personal_assistant_main_contract.py` | 保留 | 入口 public surface contract。 |
| `tests/e2e/conftest.py` | 保留 | 仅以 CLI process needle 清理泄漏子进程。 |
| `tests/e2e/critical_paths/_im_gateway.py` | 保留 | 真 Gateway subprocess argv。 |
| `tests/unit/personal_assistant/_main_helpers.py` | 删除引用 | helper 改名为中性 Gateway helper 文案，无 `main` 引用。 |
| `tests/unit/personal_assistant/test_agent_features_cron_json.py` | 迁移 | `gateway.agent_config_sync._parse_heartbeat_from_im_payload`。 |
| `tests/unit/personal_assistant/test_cron_delivery_chain.py` | 迁移 | `gateway.composition.compose_gateway`。 |
| `tests/unit/personal_assistant/test_external_visible_delivery.py` | 迁移 | `gateway.runtime_delivery.background` / `observer`。 |
| `tests/unit/personal_assistant/test_gateway_build_runtime.py` | 迁移 | `gateway.composition`、`session_keys`、`session_run_coordinator`。 |
| `tests/unit/personal_assistant/test_gateway_dispatch_url_injection.py` | 迁移 | `gateway.composition.compose_gateway` 与现有 domain owners。 |
| `tests/unit/personal_assistant/test_gateway_feishu_bot_open_id.py` | 迁移 | `gateway.composition` 的无状态 config projection。 |
| `tests/unit/personal_assistant/test_gateway_launch.py` | 保留并迁移 | CLI argv 保留；lifecycle API 由 `gateway.process_lifecycle` 提供。 |
| `tests/unit/personal_assistant/test_gateway_main_command.py` | 保留 | CLI 参数解析、用户反馈和命令分派的唯一入口测试。 |
| `tests/unit/personal_assistant/test_gateway_pid_lifecycle.py` | 保留 | 断言 detached child 使用稳定 CLI argv。 |
| `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py` | 迁移 | `gateway.runtime`、`process_lifecycle`、`composition` 与 runtime delivery owners。 |
| `tests/unit/personal_assistant/test_gateway_runtime_watchdog.py` | 迁移 | `gateway.runtime`。 |
| `tests/unit/personal_assistant/test_gateway_shutdown_order.py` | 迁移 | `gateway.runtime` 与 `composition.compose_gateway`。 |
| `tests/unit/personal_assistant/test_heartbeat_cron_vars_injection.py` | 迁移 | `gateway.composition._make_prompt_preview_provider`。 |
| `tests/unit/personal_assistant/test_heartbeat_im_delivery.py` | 迁移 | `gateway.runtime_delivery.observer`。 |
| `tests/unit/personal_assistant/test_heartbeat_session_binding.py` | 迁移 | `gateway.agent_config_sync`。 |
| `tests/unit/personal_assistant/test_permission_pipeline.py` | 迁移 | `gateway.runtime_delivery.observer`。 |
| `tests/unit/personal_assistant/test_permission_response_handler.py` | 迁移 | `gateway.composition._build_permission_response_handler`。 |
| `tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py` | 迁移 | `gateway.runtime_delivery.observer`。 |
| `tests/unit/personal_assistant/test_relay_kernel_message_id.py` | 迁移 | `gateway.runtime_delivery.observer`。 |
| `tests/unit/personal_assistant/test_session_fork_handler.py` | 迁移 | `gateway.composition._build_session_fork_handler`。 |
| `tests/unit/personal_assistant/test_steer_bubble_roll.py` | 迁移 | `gateway.runtime_delivery.observer`。 |
| `tests/unit/personal_assistant/test_steer_reply_relay_regression.py` | 迁移 | `gateway.runtime_delivery.observer`。 |
| `tests/unit/personal_assistant/test_tool_end_detail_passthrough.py` | 迁移 | `gateway.runtime_delivery.observer`。 |
| `tests/unit/test_e2e_conftest_finalizer.py` | 保留 | 仅验证 CLI process needle 的 cleanup 行为。 |
| `tests/unit/test_feishu_integration.py` | 迁移 | `gateway.composition._build_channel_registry`。 |
| `tests/unit/test_inbound_pipeline_streaming.py` | 迁移 | `gateway.runtime_delivery.lifecycle` / `observer`。 |
| `tests/unit/test_permission_decision_loop.py` | 迁移 | `gateway.composition._build_permission_response_handler`。 |

## R2 — 迁移 composition 与真实 owner imports

- Context: 直接搬移旧 `main.py` 会把 CLI feedback 与 process lifecycle 反向带进 composition，违反设计的 caller-first boundary。
- Decision: 新增 `gateway.composition`，以 `compose_gateway(config)` 装配完整 `GatewayRuntime`；`main.py` 仅解析 argv 并模块限定调用 `process_lifecycle`。进一步删除 composition 中未使用的 `process_lifecycle` import、CLI reachability probe 和 startup output helpers。
- Rationale: composition 仅组装对象图，不能成为 process lifecycle 或 operator output 的第二 owner；真正的 CLI 行为仍留在入口。
- Evidence:
  - Tests: 新增 contract 先失败：`test_composition_does_not_depend_on_cli_lifecycle_owner` 在 `process_lifecycle` 出现在 composition 时稳定失败（C1=`c0eb08144`）；修复后 `test_personal_assistant_main_contract.py` 8 passed，相关 build/runtime/entry tests 29 passed。
  - Regression: managed-channel suite 24 passed；Gateway lifecycle suite 49 passed；architecture/test-size contracts 23 passed。
  - Static: `ruff check src/personal_assistant tests/contract tests/unit/personal_assistant` 通过；`ruff format --check` 报 262 files already formatted。
  - Full suite: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q -m "not e2e"`：3618 passed, 1 skipped, 20 deselected。
  - Frontend State Matrix / Browser QA / Visual / Prototype Comparison: N/A。
- Rollback: revert `5a4feb68f` 后再 revert `2f23bad9b`。
- Commits: C1=`c0eb08144`，C2=`5a4feb68f`，C3=本次 progress commit。

## R3 — 真实入口与 Feishu 收口验证

- Context: M4 需要验证真 Gateway process 的 IM resilience、restart session continuity、cron auto-push，以及真实 Feishu online/offline cached autonomy。
- Decision: 使用 design 给定的 critical-path command；不改变用户持久配置以迎合测试固定模型，也不停止正在运行的主 Gateway 来抢占共享 Feishu Bot。
- Rationale: cron failure 的根因是 `~/.nano-assistant/config.yaml` 当前 provider 清单不含测试硬编码的 `kimiCoding:K2.6`，Gateway 日志明确报 `no registered provider for model: kimiCoding:K2.6`，不属于 composition 改动。真实 Feishu runbook 要求先停止主 Gateway；该主 Gateway 属于共享用户实例，未经独占协调不得杀掉。
- Evidence:
  - E2E: `scripts/e2e-critical.sh -k 'gateway_im_resilience or restart_session_continuity'`：3 passed, 14 deselected, 40.90s，覆盖真 IM + 真 Gateway 进程和用户可见 IM 往返。
  - Cron E2E: 完整指定筛选首次运行时在 `test_cron_job_auto_pushes_message` 等待用户可见消息超时；保留的临时 Gateway log 指认模型 provider 配置根因，未改产品代码或测试阈值规避。随后单测直跑因 live gate env 未设置而 clean skip。
  - Feishu smoke: BLOCKED。runbook 规定必须停止主 Gateway，当前检测到共享主 Gateway foreground 进程仍在运行；需要 orchestrator 协调独占时段后才能执行两次真实哨兵消息往返。未以启动日志替代。
  - Frontend State Matrix / Browser QA / Visual / Prototype Comparison: N/A。
- Rollback: 不适用（验证未改产品行为）。
- Commits: C1/C2=N/A，C3=本次 progress commit。
- Next: 等待真实 Feishu Bot 独占授权；获准后按 runbook 停止主 Gateway、运行 online reconnect 与 IM-unreachable cached autonomy 两次哨兵消息、清理 review 目录并恢复主 Gateway。
