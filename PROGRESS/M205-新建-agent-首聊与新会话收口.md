# M205 新建 Agent 首聊与新会话收口

## 前置确认
- 已阅读 `LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`。
- 已阅读失败输入：`/Users/czj/Repos/nano-multiagent/.worktrees/M146/ACCEPTANCE/M146-acceptance.md`。
- 注释/文档承诺：新增 public API 使用 Google 风格 docstring；注释只写意图、约束、边界。
- 仅在 `/Users/czj/Repos/nano-multiagent/.worktrees/M205` 工作；不改 `data/dev-tasks.json`；不触碰禁止 worktree。

## 当前处境
- Milestone: `M205 / 修复新建 Agent 可聊闭环与新会话产品路径`
- execution_mode: `parallel`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M205`
- branch: `milestone/M205`
- test_command: `pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/im_service/integration/test_m103_im_gateway_e2e.py && cd src/IM/frontend && npm test -- --runInBand src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/chat/chat-workspace-page.test.ts && npm run build`
- allowed_scope: `src/IM/**`、`src/personal_assistant/**`、`tests/**`、`scripts/acceptance/**`、`ACCEPTANCE/**`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
- forbidden_scope: `data/dev-tasks.json`、`.worktrees/M146/**`、`.worktrees/M204/**`、`.worktrees/M104/**`
- prevention_rules:
  - 真实产品闭环必须以 IM 前端为准，不能只修 API/mock。
  - 不允许恢复全局 `New direct chat` 按钮，需在每 Agent 单一复用直聊模型下提供可发现的新会话路径。
  - 新 Agent 创建后必须真正进入 Gateway/runtime 可聊态，不能停留在 DB/UI 已创建。
  - 创建页面面向普通产品用户，避免把内部 orchestrator/worker/acceptance 技能与开发工具直接铺满。
  - 若指定 worktree 已存在则复用，不再创建额外隔离层。

## Roadpoints

### R1 新建 Agent 首聊闭环与 runtime 可聊态
- Status: DONE
- 实现摘要:
  - 修复 `ConfigService.create_profile()`：允许用真实 owner/profile 覆盖 Gateway 先注册的 ownerless runtime placeholder。
  - 当创建请求同时绑定 node 时，若 node 之前 owner 为空则立即回填 owner，避免 `/im/v1/agents` runtime-selectable 过滤把新 Agent 隐藏掉。
  - 保留真正 owner 冲突时的 `409` 保护，不放宽已存在真实 profile 的重复创建。
- backend 回归根因:
  - Gateway `node.register` 会先 materialize ownerless runtime profile；后续 `POST /im/v1/agents` 如果直接按“agent_id 已存在”拒绝，就会把合法的新建绑定路径误判为冲突。
  - 同时 profile owner 已写入、node owner 仍为空时，runtime selectable SQL 过滤会返回空列表，导致创建成功但列表/首聊路径丢失。
- 修复内容:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/application/config_service.py`
- 最终验证:
  - `pytest tests/im_service/integration/test_agent_create_flow.py` → `2 passed in 0.59s`
  - `pytest -q tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless tests/im_service/integration/test_m103_im_gateway_e2e.py::test_direct_chat_keeps_old_session_after_config_sync_while_new_conversation_gets_new_profile` → `10 passed in 0.97s`
- DoD 结论:
  - 实现侧满足；创建后可进入真实 relay 路径，不再停留在 DB/UI 假成功状态。

### R2 每 Agent 单一入口下的 fresh session 路径
- Status: DONE
- 实现摘要:
  - 新增 `direct_agent_id` conversation detail 字段，聊天页识别“这是某个 Agent 的稳定 direct chat”。
  - 在 direct chat header 增加 `Start fresh session` CTA；点击后创建新的 direct conversation，并导航到新线程。
  - 保留 stable reusable direct chat，不恢复全局 `New direct chat`。
  - 更新 create/detail/chat 文案，明确“旧线程保留旧 snapshot；fresh session 才吃新 prompt version”。
- 修复内容:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/chat/chat-api.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/chat/types.ts`
- 最终验证:
  - `npm --prefix src/IM/frontend test src/features/chat/chat-workspace-page.test.ts src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx` → `31 passed (31)`
  - `pytest -q tests/im_service/integration/test_m103_im_gateway_e2e.py::test_direct_chat_keeps_old_session_after_config_sync_while_new_conversation_gets_new_profile` → included in `10 passed in 0.97s`
  - `npm --prefix src/IM/frontend run build` → passed
- DoD 结论:
  - 实现侧满足；旧 direct thread 不漂移，新 direct conversation 可吃到新 prompt snapshot。

### R3 Allowlist 面向普通用户的收敛与分组
- Status: DONE
- 实现摘要:
  - 默认只展示 `Recommended for product users`。
  - 内部/高级 skill 与 tool 收敛到 `Show advanced/internal options` 折叠区。
  - 已保存的高级项保留在 `Saved advanced items`，避免旧配置被静默丢失。
- 修复内容:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/settings/agents/allowlist-selector.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
- 最终验证:
  - `npm --prefix src/IM/frontend test src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx` → both included in `31 passed (31)`
  - `npm --prefix src/IM/frontend run build` → passed
- DoD 结论:
  - 实现侧满足；普通用户默认视图已收敛，同时历史高级配置仍可见。

### R4 自证证据、runtime 复用说明与交接
- Status: DONE
- 实现摘要:
  - 补齐 TASKS / PROGRESS / ACCEPTANCE，明确实现自证与最终产品验收边界。
  - 在补跑 backend gate 期间定位到一个额外 backend 回归：Gateway pipeline 对没有显式 `status` 但已有 `output_text` 的 run snapshot 不会收敛为 completed，导致 browserless roundtrip 用例卡住。
  - 为此增加 `_run_status()` fallback，并以 unit test 锁定。
- backend 回归根因:
  - 某些 fake/test kernel run snapshot 只返回 `output_text`，不带 `status`。当前 pipeline 轮询逻辑仅依赖 `status in {completed, failed, cancelled}` 才退出，于是会无限轮询 `get_run()`。
- 修复内容:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/personal_assistant/gateway/inbound_pipeline.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/tests/unit/personal_assistant/test_gateway_pipeline.py`
- 最终验证:
  - `pytest tests/unit/personal_assistant/test_gateway_pipeline.py -k statusless_run_snapshot_with_output` → `1 passed`
  - `pytest tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless` → `1 passed in 0.63s`
  - `pytest tests/im_service/integration/test_agent_create_flow.py` → `2 passed in 0.59s`
  - `pytest tests/im_service/integration/test_agent_config_api.py` → `6 passed in 0.65s`
  - `pytest -q tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless tests/im_service/integration/test_m103_im_gateway_e2e.py::test_direct_chat_keeps_old_session_after_config_sync_while_new_conversation_gets_new_profile` → `10 passed in 0.97s`
  - `npm --prefix src/IM/frontend test src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/chat/chat-workspace-page.test.ts && npm --prefix src/IM/frontend run build` → passed
- DoD 结论:
  - 实现侧自证已完整；可交由主 agent 重派最终产品验收。

## 当前结论
- M205 的实现侧 exit criteria 已满足：
  - R1 首聊/runtime 可聊态已修复并回归锁定。
  - R2 fresh session 产品路径已落地且不恢复全局 New direct chat。
  - R3 allowlist 默认视图已收敛并保留旧值可见性。
  - R4 证据已落盘，且补齐了 Gateway statusless-run 的 backend 回归修复。
- 但尚未进入 commit / merge / worktree cleanup：
  - 当前仓库根 `main` 工作区本身存在与 M205 无关的脏改动和未跟踪文件，直接切回根仓执行 merge 不安全。
  - 因此此刻的唯一阻塞点已变为“主仓库 main 工作区不干净，无法在不干扰用户现有改动的前提下安全完成 merge / cleanup”。
