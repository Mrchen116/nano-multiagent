# Verification Report: bugfix-507

> Validation snapshot: `5bba0493f34bd5acc2343787f04a8e092d1309b4 → 8ae5fdd7a7f87a5aa60d145efb73e7225a14f3c8`

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 milestone；6/6 退出标准；5/5 requirements |
| Correctness | 19/19 scenarios covered |
| Coherence | 5/5 design decisions followed |

All checks passed. Ready for PR.

## Completeness

- Tasks: `M1-visible-custom-cutover/tasks.md` 4/4 roadpoints DONE，6/6 退出标准均有代码、永久回归或可复查 evidence；`progress.md` 记录了 R1–R4 的命令、结果与清理。
- Spec 覆盖：incident 的 3 条 requirement、IM delta 的 1 条 MODIFIED + 1 条 ADDED requirement、Gateway delta 的 1 条 MODIFIED requirement 均投影到同一 M1；重叠的用户契约按 5 个独立 requirement 计数，5/5 已实现。
- SQLite/YAML legacy-first 合并、first-seen register seed、notification-only sync + mirror GET、runtime/preview 同源、conversation prompt 正文退役和 UI stable-preview 边界均有实现与测试证据。
- Prototype / Reference 覆盖：N/A；design 明确无 prototype/reference contract。本轮已检视提交的 desktop/mobile 截图及 `evidence/browser-qa.md`，stable preview 标题、Custom Agent Instructions 和 group/memory exclusion help 均可见。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| Incident: 新建/编辑 Agent 无隐藏第二份人设 | `src/IM/api/routes/agents.py:26`, `src/IM/api/routes/nodes.py:78`, `src/personal_assistant/product.py:289` | `tests/im_service/contract/test_agent_config_contract.py:17`; `tests/integration/test_personal_assistant_prompt_integration.py:67` | covered |
| Incident: 保存专属说明只影响该 Agent 后续新回复，历史继续 | `src/personal_assistant/gateway/agent_catalog.py:65`, `src/personal_assistant/gateway/session_composition.py:38` | `tests/unit/personal_assistant/test_inbound_pipeline_agent_sessions.py:19`; `tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py:259` | covered |
| Incident: preview 包含 saved/draft 专属说明 | `src/IM/api/routes/agents.py:586`, `src/personal_assistant/gateway/composition.py:132` | `tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py:263`; frontend component regressions + browser evidence | covered |
| Incident: preview 明示 runtime-only 边界 | `src/IM/frontend/src/i18n/en.json:377`, `src/IM/frontend/src/i18n/zh.json:374` | `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx:684`; `M1-visible-custom-cutover/evidence/browser-qa.md` | covered |
| Incident: 升级保留 legacy 有效说明且不重复 | `src/IM/infra/db.py:652`, `src/personal_assistant/config/local_store.py:1113` | `tests/im_service/unit/test_agent_prompt_config_migration.py:10`; `tests/unit/personal_assistant/config/test_agent_prompt_config_migration.py:11` | covered |
| IM MODIFIED: 读配置仅暴露 stable profile 字段和 custom prompt | `src/IM/api/routes/agents.py:26`, `src/IM/domain/models.py:105` | `tests/im_service/contract/test_agent_config_contract.py:17`; `tests/im_service/integration/test_agent_config_api.py:21` | covered |
| IM MODIFIED: PATCH 持久化并保持 optimistic lock | `src/IM/infra/repositories/agents.py:256` | `tests/im_service/contract/test_agent_config_contract.py:65`; `tests/im_service/unit/test_repositories_agent_profile.py:41` | covered |
| IM MODIFIED: 既有聊天下一回复采用新运行配置 | `src/personal_assistant/gateway/session_composition.py:38`, `src/personal_assistant/gateway/session_run_coordinator.py:296` | `tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py:259`; `tests/unit/personal_assistant/test_session_run_coordinator_admission.py:919` | covered |
| IM MODIFIED: live merge 保留 IM-owned 字段 | `src/IM/api/routes/agents.py:207` | `tests/im_service/contract/test_agent_config_contract.py:238` | covered |
| IM MODIFIED: heartbeat cadence 返回真实配置/默认 30m | `src/IM/api/routes/agents.py:674`, `src/personal_assistant/config/local_store.py:184` | `tests/unit/personal_assistant/test_heartbeat_scheduler_config_every.py:130`; `tests/unit/personal_assistant/test_heartbeat_scheduler_config_every.py:170` | covered |
| IM ADDED: 空 Custom Instructions 无 hidden profile persona | `src/personal_assistant/product.py:317`, `src/personal_assistant/product.py:341` | `tests/integration/test_personal_assistant_prompt_integration.py:67`; frontend empty-state regression | covered |
| IM ADDED: preview 检查当前稳定说明/能力配置 | `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:134`, `src/personal_assistant/gateway/composition.py:141` | `src/IM/frontend/src/features/settings/agents/agent-prompt-preview.test.tsx:164`; E2E + browser evidence | covered |
| IM ADDED: 升级保留且 legacy-first/幂等 | `src/IM/infra/db.py:659`, `src/personal_assistant/config/local_store.py:1340` | 两个 migration parameterized suites，覆盖四种组合与重复 initialize/reload | covered |
| IM ADDED: old YAML → empty IM first register seed，existing/explicit-empty 不被覆盖 | `src/personal_assistant/reporter/upstream_reporter.py:245`, `src/IM/infra/gateway_persistence.py:147` | `tests/im_service/integration/test_gateway_im_registration.py:14`; `tests/im_service/integration/test_gateway_im_registration.py:170`; true-stack E2E | covered |
| Gateway MODIFIED: 增加工具后继续历史 | `src/personal_assistant/gateway/session_composition.py:38` | `tests/integration/test_session_run_coordinator_real_kernel.py:141`; true-stack E2E 同时新增 `read` | covered |
| Gateway MODIFIED: 删除工具不破坏已有工具历史 | `src/agent/sdk/kernel.py:1122`, `src/personal_assistant/gateway/session_composition.py:58` | Kernel runtime replacement/transcript regression and existing persisted tool-history tests | covered |
| Gateway MODIFIED: 修改 custom/skills/features 后保留历史 | `src/personal_assistant/gateway/session_composition.py:55` | `tests/unit/personal_assistant/test_session_run_coordinator_admission.py:919`; `tests/integration/test_session_run_coordinator_real_kernel.py:141` | covered |
| Gateway MODIFIED: 连续保存只采用真正开始时最终配置 | `src/personal_assistant/gateway/session_run_coordinator.py:296`, `src/personal_assistant/gateway/agent_catalog.py:65` | admission/active-run replacement regressions at `tests/unit/personal_assistant/test_session_run_coordinator_admission.py:919` and `:970` | covered |
| Gateway MODIFIED: 完整配置替换失败不以 mixed runtime 回复 | `src/personal_assistant/gateway/session_run_coordinator.py:323` | runtime replacement failure/terminal regressions in `tests/unit/personal_assistant/test_session_run_coordinator_terminal.py` | covered |

### Verification execution

- Changed non-E2E Python tests: `379 passed`.
- Focused prompt/migration/API/registration/architecture set: `83 passed`.
- Isolated real-process config-continuity E2E: `1 passed`.
- Runtime replacement + Kernel internal override suites: `35 passed`.
- Changed Python Ruff: passed; `scripts/docs-check`: passed; `git diff --check`: passed.
- Frontend tests/build were not re-run in this detached worktree because it intentionally has no dependency directory and verifier did not mutate it with a symlink. The committed implementation record reports 15 files / 130 tests and `tsc -b && vite build` passed; this round independently inspected the relevant TS tests, i18n, API payload code, browser QA record, and both screenshots.

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1 `custom_prompt` 是 IM/PA profile 唯一公开人设接口 | 是 | `src/IM/domain/models.py:105`, `src/IM/api/routes/agents.py:26`, `src/personal_assistant/config/local_store.py:164`, `src/personal_assistant/product.py:289` |
| D2 双持久化边界 legacy-first 幂等迁移，first-seen seed，existing IM profile 权威 | 是 | `src/IM/infra/db.py:652`, `src/personal_assistant/config/local_store.py:1340`, `src/personal_assistant/reporter/upstream_reporter.py:271`, `src/IM/infra/gateway_persistence.py:147` |
| D3 preview 是 stable prompt preview，与 runtime 复用 `prompt_for()` | 是 | `src/personal_assistant/gateway/composition.py:141`, `src/personal_assistant/gateway/session_composition.py:60`, `src/IM/frontend/src/i18n/en.json:377` |
| D4 conversation provenance 不再存 prompt 正文，id/version 保留 | 是 | `src/IM/infra/db.py:35`, `src/IM/infra/db.py:675`, `src/IM/infra/repositories/conversations.py:140`, `src/IM/application/relay_service.py:367` |
| D5 以一个原子 M1 关闭全部 public/runtime ingress | 是 | unit diff 在 `ac1eb138f` 一次合并 R1–R4；`M1-visible-custom-cutover/tasks.md` 全部 DONE |

- Kernel generic override 未删除：`src/agent/` 在 unit diff 中无修改，`tests/unit/test_background_hook_fork.py::test_fork_conversation_inherits_parent_system_prompt` 通过。
- 依赖方向与模块边界未回归：`personal_assistant` 仍通过 `agent.sdk`，IM 未 import `agent`；`test_cli_sdk_only_contract.py` 与 `test_core_no_platform_imports.py` 通过。
- 跨机边界正确：IM 通过 WS `node.register` 收 seed，通过 HTTP mirror 向 Gateway 提供 profile，preview 仍通过 Gateway RPC；IM 没有直读 Gateway YAML/workspace。
- 未新建平行 sync/preview 机制：`config.sync` 仍只是 `{agent_id, profile_version}` 通知，mirror GET 仍是 profile source，preview/runtime 仍共用 `prompt_for()`。

### Prototype / Reference Contract

N/A. The approved design supplied neither a prototype nor a reference artifact contract.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

# Round 2

> Validation snapshot: `8ae5fdd7a7f87a5aa60d145efb73e7225a14f3c8 → 204b22de9f4871f06e4a5fbad165c9ed74bd3fd6`

## Summary

Mode: targeted-closure
Delta range: `8ae5fdd7a7f87a5aa60d145efb73e7225a14f3c8..204b22de9f4871f06e4a5fbad165c9ed74bd3fd6`
Focus issues: C1 SQLite < 3.35 migration startup failure; C3 Gateway service-lifecycle public `system_prompt`
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 2/2 focus issues closed |
| Correctness | C1 的 modern/old SQLite paths、C3 的 canonical/delta public contract 均已覆盖 |
| Coherence | 修复局限于 IM migration compatibility 与现有 Gateway/IM 契约对齐 |

All checks passed. Ready for PR.

## Focus-Issue Closure

### C1 SQLite < 3.35 `DROP COLUMN` migration startup failure — closed

- `src/IM/infra/db.py:661-691` first merges legacy `system_prompt` into canonical `custom_prompt`. SQLite >= 3.35 removes both retired columns; older SQLite retains only the physical compatibility columns and clears their values. On every later startup the blank legacy value leaves custom text unchanged, so the migration is idempotent and cannot re-merge the hidden text.
- `tests/im_service/unit/test_agent_prompt_config_migration.py:105-160` uses a real on-disk connection, simulates SQLite 3.34, initializes twice, and proves retained compatibility columns are blank while `custom_prompt` remains `Legacy role\n\nCustom tail`. It also verifies the retired conversation field is cleared.

### C3 Gateway service-lifecycle still declares public `system_prompt` — closed

- Canonical `docs/specs/gateway/service-lifecycle.md:62-88` and the unit delta `specs/gateway/service-lifecycle.md:7-33` now describe exactly four register seed mappings, with `agent_custom_prompts` as normalized non-empty Custom Instructions, and list `custom_prompt` as the only public agent-specific field in a live snapshot.
- The related IM capability/profile specifications retain `default_system_prompt` only as a product default capability and explicitly exclude a public per-agent `system_prompt`; no Gateway lifecycle contract exposes it.

## Fix-delta Guard

- The only production-code change is the SQLite version guard and clear-on-old-version migration path; the matching regression test is the only changed Python test. No package imports, RPC surface, persistence ownership, or cross-machine access boundary changed.
- The remaining delta is migration/acceptance evidence plus canonical and delta spec alignment. The Gateway still sends `config.sync` as a notification and uses the existing mirror/live snapshot path; it does not introduce a second configuration mechanism.
- The delta introduces no spec/design/architecture deviation. A full verification escalation is not required because it changes neither an architecture-boundary test nor the approved public behavior beyond closing the two named defects.

### Verification execution

- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/im_service/unit/test_agent_prompt_config_migration.py tests/im_service/contract/test_agent_config_contract.py tests/im_service/integration/test_gateway_im_registration.py tests/unit/personal_assistant/test_gateway_upstream_reporter.py` → `34 passed`.
- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/ruff check src/IM/infra/db.py tests/im_service/unit/test_agent_prompt_config_migration.py` → passed.
- `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/docs-check` → passed (228 maintained Markdown sources, 66 required routes).
- `git diff --check 8ae5fdd7a7f87a5aa60d145efb73e7225a14f3c8..204b22de9f4871f06e4a5fbad165c9ed74bd3fd6` → passed after removing pre-existing trailing whitespace from this verification report.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.
