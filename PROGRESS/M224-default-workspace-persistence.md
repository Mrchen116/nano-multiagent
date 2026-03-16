# M224 修复已有 Agent 默认 Workspace 未持久化导致 Bash cwd 回落仓库根

## Notes
- 已阅读 `LOGBOOK.md`：新增关键 session metadata 时，旧 binding 复用前必须向 kernel 取回 session metadata，缺字段要自动重建；真实入口若与源码矛盾，先确认是否仍跑在旧 worktree/旧进程上。
- 已阅读 `COMMENTING_GUIDE.md`：后续 public API/docstring 与注释只写契约、边界和原因，不复述实现。
- 基线：派工中的 `tests/personal_assistant/test_inbound_pipeline.py` 在当前仓库不存在；本 milestone 用现有对应测试 `tests/unit/personal_assistant/test_gateway_pipeline.py` 建立 red/green，并在最终结果里报告这条测试命令漂移。

## Roadpoint Records

### R1.1 默认 workspace_root 持久化与 legacy profile 迁移
- Context:
  - 主运行态 `data/im_service.sqlite3` 中 agent `fuck` 的 `workspace_root` 为 `NULL`，而 API/UI 只是在读取时临时回退默认路径。
  - 问题同时存在于 HTTP create/update、gateway `node.register` materialize profile，以及旧库里已经落下的 `NULL` 行。
- Decision:
  - 在 `/Users/czj/Repos/nano-multiagent/.worktrees/M224/src/IM/application/config_service.py` 将 `None/blank` 的 `workspace_root` 统一规范化为 managed default path 并真实落库。
  - 在 `/Users/czj/Repos/nano-multiagent/.worktrees/M224/src/IM/ws/gateway_handler.py` 给 runtime 注册生成/更新的 profile 同样写入 managed default path。
  - 在 `/Users/czj/Repos/nano-multiagent/.worktrees/M224/src/IM/infra/db.py` 为历史 `workspace_root IS NULL/''` 做 schema backfill，并在 `/Users/czj/Repos/nano-multiagent/.worktrees/M224/src/IM/domain/models.py` 抽出 managed workspace helper；API 的 `workspace_is_default` 改成按路径语义判断。
- Rationale:
  - 只有把默认路径变成持久化真值，后续 session 刷新与真实运行态才能信任 profile 行，而不是每层临时猜测默认值。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M224/src pytest /Users/czj/Repos/nano-multiagent/.worktrees/M224/tests/im_service/unit/test_repositories.py /Users/czj/Repos/nano-multiagent/.worktrees/M224/tests/im_service/integration/test_agent_create_flow.py /Users/czj/Repos/nano-multiagent/.worktrees/M224/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M224/tests/im_service/integration/test_m103_im_gateway_e2e.py::test_gateway_registration_materializes_runtime_agents_before_and_after_bind -q`
  - Entry: 隔离 M224 IM runtime 重新注册 `fuck` 后，`data/im_service.sqlite3` 中 `agent_profiles.agent_id='fuck'` 变为 `workspace_root=/Users/czj/nano-assistant/workspace/fuck`。
- Rollback:
  - `f6bd693`。
- Commits: C1=`f6bd693`, C2=`69bc8b3`, C3=`pending`
- Next:
  - 用真实 direct chat 证明 legacy session 会被刷新，`pwd` 不再落回 repo root。

### R2.1 legacy direct-chat session 刷新与真实 pwd 验证
- Context:
  - 旧真实会话 `7947b93380fe43fd806c759ed1efccd9` 曾返回 `/Users/czj/Repos/nano-multiagent`，说明直聊复用到了缺少 `workspace_root` metadata 的 legacy kernel session。
  - 主运行态当前 8000 kernel 对新建 session 的 `GET /v1/sessions/{id}` 不返回 metadata，因此要用隔离 M224 kernel 做可观测验证，同时保留真实 direct chat 入口与真实 IM 数据库。
- Decision:
  - 保持 `/Users/czj/Repos/nano-multiagent/.worktrees/M224/src/personal_assistant/gateway/inbound_pipeline.py` 的 legacy binding 校验逻辑，并用现有集成/单测覆盖旧 binding 缺 `workspace_root` 时的新 session 重建。
  - 额外启动隔离 M224 IM (`18121`) 与隔离 M224 kernel (`18122`)，二者都指向真实直聊所在的 `data/im_service.sqlite3`，再用临时 gateway 配置 `/Users/czj/Repos/nano-multiagent/.worktrees/M224/ACCEPTANCE/M224-runtime-node-config.yaml` 让真实 agent `fuck` 跑完整直聊消息。
- Rationale:
  - 这样既能复用真实用户/agent/直聊数据完成入口验证，又不会破坏主运行态进程；同时隔离 kernel 会把 session metadata 按当前 M224 代码完整落盘，方便直接取证。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M224/src pytest /Users/czj/Repos/nano-multiagent/.worktrees/M224/tests/im_service/unit/test_repositories.py /Users/czj/Repos/nano-multiagent/.worktrees/M224/tests/im_service/integration/test_agent_create_flow.py /Users/czj/Repos/nano-multiagent/.worktrees/M224/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M224/tests/im_service/integration/test_m103_im_gateway_e2e.py::test_gateway_registration_materializes_runtime_agents_before_and_after_bind /Users/czj/Repos/nano-multiagent/.worktrees/M224/tests/im_service/integration/test_m103_im_gateway_e2e.py::test_direct_chat_recreates_legacy_kernel_session_without_workspace_metadata /Users/czj/Repos/nano-multiagent/.worktrees/M224/tests/unit/personal_assistant/test_main.py::test_im_config_sync_client_drops_existing_agent_session_bindings_after_profile_refresh -q`；`npx pnpm --dir /Users/czj/Repos/nano-multiagent/.worktrees/M224/src/IM/frontend test -- --run agent-create agent-detail allowlist-selector`
  - Entry: 对真实直聊 `7947b93380fe43fd806c759ed1efccd9` 发送“请只执行 pwd，并且只回复当前工作目录的绝对路径，不要加解释。”后，`conversation_events` 的 `relay.completed/message.delivered.detail` 返回 `/Users/czj/nano-assistant/workspace/fuck`；隔离 kernel 的 `m224-sessions.sqlite3` 新 session `sess_b85f433279c0b957` 持久化了 `metadata.workspace_root=/Users/czj/nano-assistant/workspace/fuck`。
- Rollback:
  - `69bc8b3`。
- Commits: C1=`already present in branch baseline`, C2=`69bc8b3`, C3=`pending`
- Next:
  - 提交文档，随后 rebase/merge main，并更新 `data/dev-tasks.json`。
