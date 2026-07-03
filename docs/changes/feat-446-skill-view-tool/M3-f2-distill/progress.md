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
- Rollback: revert `72180e0a` and `f4f5523e` together to remove builtin skill bootstrap implementation/tests.
- Commits: C1=f4f5523e, C2=72180e0a, C3=5505d7e5
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
- Rollback: revert `663ed2c6` and `247fec3e` together to remove response fields and tests.
- Commits: C1=247fec3e, C2=663ed2c6, C3=bd619c59
- Next: R3

## R3 — frontend selection and prefill flow

- Context: F2 入口必须从现有 IM chat v2 列表进入，不能新增后端注入 transcript 的特殊发送路径；用户最终仍编辑并发送一条普通聊天消息。
- Decision: 扩展 `Conversation` 前端类型，`ConversationSidebar` 增加受控 distill 多选模式；默认列表不显示 `run_state`，进入模式后只允许 `idle + source_agent_id + source_jsonl_path` conversation 勾选，`running` 显示运行态禁选。`ChatWorkspacePageV2` 根据选中来源 agent 集合自动/手动确定执行 agent，在同一 modal 选择 `agent|pa` scope，确认前用现有 live config + capabilities + `resolveEnabledSkills()` 校验执行 agent 可见 `conversation-skill-distiller`。可见时创建执行 agent 单聊并通过 `MessagePane.draftSeed` 预填普通 composer。
- Rationale: distill skill 可见性与 slash picker 使用同一 enablement 规则，避免 UI 预填一个运行时不可解析的 `/skill:`。预填只写 textarea，不改 `createMessage()` payload 和 Gateway 解析链路，因此 `source_jsonl_paths` 仍由 agent 在 skill 指导下自行读取。
- Evidence:
  - Tests: C1 红测 `cd src/IM/frontend && npm run test -- --run src/features/chat/v2/components/conversation-sidebar.test.tsx src/features/chat/v2/chat-workspace.integration.test.tsx` -> 4 failed（无 checkbox / Generate skill / Distill to skill 流程）。C2 后同命令 -> 2 files / 35 tests passed；`npm run build` -> passed（仅既有 Vite chunk/dynamic import warning）。
  - Entry: 侧栏 `Generate skill` 按钮和 conversation row context-menu 进入多选；`Distill to skill` 打开确认弹窗；`Start distillation` 校验技能可见性后跳转 `/chat/<new conversation>`，composer 预填 `/skill:conversation-skill-distiller`、`source_jsonl_paths`、`execution_agent_id`、`target_scope` 和默认意图 prompt。
  - Frontend State Matrix: default=无运行态标签；disabled=`running` 禁选并显示状态、无 transcript 禁选；empty=无选择时提交按钮 disabled；error=skill 不可见时 modal 内提示且不 POST conversation；submitting=Start distillation 禁用并显示 starting；nullable=缺 `source_agent_id/source_jsonl_path` 不可选；desktop/mobile 视觉验收留 R4。
  - Browser QA: 留 R4 真入口验收。
  - E2E/Regression: workspace integration 覆盖单来源自动执行 agent、跨来源必须选择执行 agent、scope=pa、skill 不可见不预填不创建 conversation、预填后普通 composer 仍可按现有发送测试路径发送。
  - Visual/Interaction: component/integration 覆盖可访问名称；真实 viewport 截图留 R4。
- Rollback: revert `270cb33c` and `a580628e` together to remove frontend distill entry and tests.
- Commits: C1=a580628e, C2=270cb33c, C3=1d2eccec
- Next: R4

## R4 — real entry QA and final gates

- Context: 收尾需要证明 M3 的后端、前端、Gateway 自举和真实页面入口均可工作，并把每条退出标准落到证据。
- Decision: 使用窄后端 pytest、完整 chat v2 Vitest、前端生产 build、隔离 HOME Gateway foreground 启动、Vite + Playwright 浏览器脚本完成最终验收。浏览器脚本走真实 Vite bundle，HTTP/WS 在浏览器侧 mock 固定数据，以便稳定覆盖桌面/移动 distill UI，而 Gateway 自举另用真实进程验证。
- Rationale: Gateway 启动只需验证 product builtin skill bootstrap，不需要真实 LLM 调用；浏览器侧 mock 避免本地 IM/Gateway/LLM 状态影响视觉验收，同时仍覆盖真实 React route、CSS、composer 和可访问交互。
- Evidence:
  - Tests:
    - `PYTHONPATH=src pytest tests/unit/personal_assistant/test_builtin_skills_bootstrap.py tests/unit/personal_assistant/test_gateway_launch.py tests/unit/test_skill_manage_tool.py tests/im_service/unit/test_repositories_user_conversation.py tests/im_service/unit/test_message_runtime_state.py -x` -> 49 passed.
    - `cd src/IM/frontend && npm run test -- --run src/features/chat/v2` -> 18 files / 306 tests passed. Existing warnings: React `act(...)`, `--localstorage-file`, missing test route for `/settings/agents/a-planner`.
    - `cd src/IM/frontend && npm run build` -> passed. Existing Vite warnings: auth-store mixed static/dynamic import and large chunk.
  - Entry: 隔离 HOME Gateway foreground 启动验证 `~/.nanoassistant/skills/conversation-skill-distiller/SKILL.md` 自动生成；将同名 `SKILL.md` 写入 `CUSTOM USER SKILL` 后再次启动，文件保持用户内容不被覆盖。
  - Frontend State Matrix: default/no run-state label、selection checkboxes、running disabled、no transcript disabled、cross-agent execution choice、scope choice、skill-visible prefill、skill-invisible error 均由 Vitest 覆盖；desktop/mobile layout 由 Playwright 截图覆盖。
  - Browser QA: Playwright against real Vite bundle passed with no console/page errors. Screenshots copied to `/tmp/feat446-m3-browser-qa/desktop-distill-selection.png`, `/tmp/feat446-m3-browser-qa/desktop-distill-prefill.png`, `/tmp/feat446-m3-browser-qa/mobile-distill-selection.png`.
  - E2E/Regression: `source_jsonl_paths` 仅预填到 `MessagePane` draft，未修改 `createMessage()`/Gateway parser；普通发送路径由 chat workspace existing send tests回归。`conversation-skill-distiller/SKILL.md` 指导 agent 自行读取 JSONL，任一 source 不可读或证据不足不得创建 skill，并通过 `skill_manage(create, scope=<target_scope>)` 写入目标 root；历史蒸馏产物声明为用户主动创建，不进自动 Curator。
  - Visual/Interaction: 截图检查无明显重叠；desktop selection 展示可选 idle 与 running 禁选标签，desktop prefill 展示执行 agent 新对话和 composer 草稿，mobile selection 展示 checkbox/禁选标签/底部导航不冲突。
- Rollback: revert R1/R2/R3 implementation commits plus their tests/docs if M3 must be removed; no schema migration added, rollback is code-only.
- Commits: C3=7524d409
- Next: DONE
