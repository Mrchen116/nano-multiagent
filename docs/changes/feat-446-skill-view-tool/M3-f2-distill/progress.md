# feat-446-M3 — Progress

## Startup

- Context: 按 `change-impl-worker` full 模式执行，worktree 为 `/Users/czj/Repos/nano-multiagent/.worktrees/feat-446-M3`，分支为 `milestone/feat-446-M3`。M1 已合入 `unit/feat-446`，M3 只负责 F2 conversation distillation 入口和最小共享状态/类型。
- Evidence:
  - Read: `AGENTS.md`、`CLAUDE.md`、`SPEC.md`、`LOGBOOK.md`、`docs/TESTING_GUIDE.md`、`docs/changes/feat-446-skill-view-tool/spec.md`、`design.md`、`prototype-f2.html`、`specs/kernel/spec.md`、`specs/im/spec.md`、`specs/gateway/spec.md`、M1 `tasks.md`/`progress.md`、`change-impl-worker/SKILL.md`。
  - Baseline backend: `PYTHONPATH=src pytest tests/unit/test_skill_manage_tool.py tests/unit/test_skill_view.py tests/unit/personal_assistant/test_gateway_build_runtime.py tests/unit/personal_assistant/test_gateway_launch.py tests/im_service/unit/test_repositories_user_conversation.py tests/im_service/unit/test_message_runtime_state.py -x` -> 59 passed.
  - Baseline frontend: first run failed because worktree frontend dependencies were not installed (`vitest: command not found`); after `npm install`, `npm run test -- --run src/features/chat/v2` -> 18 files / 301 tests passed. Existing warnings: React `act(...)`, Playwright `--localstorage-file`, and missing settings route warnings in existing tests.
  - Scope confirmation: range is `src/personal_assistant/builtin_skills/conversation-skill-distiller/SKILL.md` + PA built-in skill bootstrap reuse/completion + IM conversation multi-select/execution-agent/scope/pre-fill flow + `run_state`/`source_jsonl_paths`/`execution_agent_id`/`target_scope`; no M2 Curator/F4, no M4 dashboard/skill_view card.

## R1 — built-in distiller and scope contract

- Context: M3 需要 PA 产品级内置 `conversation-skill-distiller`，新安装或干净 HOME 下 Gateway 启动必须能发现它；同时用户已有同名 skill 不能被产品升级覆盖。M1 已实现 `skill_manage(create, scope=agent|pa)`，R1 只回归它，不扩展写侧逻辑。
- Decision: 在 `personal_assistant.gateway.bootstrap` 增加通用 `install_builtin_skills()`，扫描包内 `personal_assistant/builtin_skills/*/SKILL.md`，将缺失目录复制到 `~/.nanoassistant/skills`；`build_runtime()` 在构建 PA kernel 前调用该 helper。新增包内 `conversation-skill-distiller/SKILL.md`，并通过 `pyproject.toml` package-data 纳入分发。
- Rationale: helper 按目录型资源工作，不绑定 feishu 或 distill 名称；以目标 `SKILL.md` 是否存在作为不覆盖判据，保护用户本地同名 skill。安装发生在 PA kernel 创建前，后续 skill discovery 搜索 `~/.nanoassistant/skills` 时可自然看到内置 skill。
- Evidence:
  - Tests: C1 红测 `PYTHONPATH=src pytest tests/unit/personal_assistant/test_builtin_skills_bootstrap.py tests/unit/personal_assistant/test_gateway_launch.py tests/unit/test_skill_manage_tool.py -x` -> collection 失败，`ImportError: cannot import name 'install_builtin_skills'`；C2 后同命令 -> 30 passed.
  - Entry: `tests/unit/personal_assistant/test_builtin_skills_bootstrap.py` 直接调用 `install_builtin_skills(target_root=...)` 验证缺失时生成 `conversation-skill-distiller/SKILL.md`，已有用户文件时不覆盖；`test_gateway_launch.py` 保持 Gateway launch 行为回归；`test_skill_manage_tool.py` 回归 `scope=agent` 写 agent root、`scope=pa` 写 PA root、PA root 不可用时失败不回退。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 后端 unit regression 已落库；真实 Gateway HOME 启动验证留到 R4 真入口验收。
  - Visual/Interaction: N/A
- Rollback: revert `e08b95b2` and `5b40f6ca` together to remove builtin skill bootstrap implementation/tests.
- Commits: C1=5b40f6ca, C2=e08b95b2, C3=TODO
- Next: R2

## R2 — conversation distill metadata

- Context: F2 前端必须从 IM conversation 列表拿到通用运行态和可读 transcript 路径；Gateway 的 kernel session id 绑定在 Gateway 本地 session binding store，IM 不能从 conversation id 直接拼出 session JSONL 文件名。
- Decision: 在 `Conversation` domain/API response 增加 `run_state`、`source_agent_id`、`source_jsonl_path`。`run_state` 由 IM messages 中未完成 agent bubble 派生；`source_agent_id` 优先使用 conversation 创建时冻结的 `config_agent_id`，否则退回唯一 agent participant；`source_jsonl_path` 通过 `agent_profiles.workspace_root/.nanoassistant/sessions/*.jsonl` 扫描 `session_created.metadata.conversation_id + agent_id` 匹配的真实文件。
- Rationale: 不让 IM 猜随机 kernel session id，也不在 list conversations 时写新 transcript 文件；只有真实存在且 metadata 匹配的 JSONL 才暴露给前端。路径不可得时返回 `null`，后续前端不把该会话作为可蒸馏 source。
- Evidence:
  - Tests: C1 红测 `PYTHONPATH=src pytest tests/im_service/unit/test_repositories_user_conversation.py::test_conversation_exposes_run_state_and_source_jsonl_path tests/im_service/unit/test_repositories_user_conversation.py::test_conversation_run_state_is_running_for_active_agent_message tests/im_service/integration/test_users_conversations_api.py::test_agent_conversation_response_includes_source_jsonl_path -q` -> 3 failed，缺 `run_state` / `source_agent_id` 字段；C2 后 `PYTHONPATH=src pytest tests/im_service/unit/test_repositories_user_conversation.py::test_conversation_exposes_run_state_and_source_jsonl_path tests/im_service/unit/test_repositories_user_conversation.py::test_conversation_run_state_is_running_for_active_agent_message tests/im_service/integration/test_users_conversations_api.py::test_agent_conversation_response_includes_source_jsonl_path tests/im_service/integration/test_users_conversations_api.py::test_users_and_conversations_roundtrip -q` -> 4 passed.
  - Entry: `/im/v1/conversations`、`/im/v1/sync`、`/im/v1/conversations/{id}` now serialize the three fields through existing `to_conversation_response()`.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: Backend repository/API tests cover idle default, running active agent message, null path without agent source, and real JSONL path when session metadata matches.
  - Visual/Interaction: N/A
- Rollback: revert `f0a24c0a` and `6bb1eb33` together to remove response fields and tests.
- Commits: C1=6bb1eb33, C2=f0a24c0a, C3=TODO
- Next: R3

## R3 — frontend selection and prefill flow

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: TODO
  - Browser QA: TODO
  - E2E/Regression: TODO
  - Visual/Interaction: TODO
- Rollback: TODO
- Commits: TODO
- Next: R4

## R4 — real entry QA and final gates

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: TODO
  - Browser QA: TODO
  - E2E/Regression: TODO
  - Visual/Interaction: TODO
- Rollback: TODO
- Commits: TODO
- Next: DONE
