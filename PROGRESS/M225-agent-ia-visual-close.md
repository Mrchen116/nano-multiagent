# M225 Agent 页面信息架构与视觉收口进度

## Milestone 摘要
- Goal: 基于当前 create/detail/list/allowlist 页面，收口明显产品缺陷：信息过载、术语误导、右栏噪音、allowlist 视觉穿模与 workspace 相关误导文案。
- Constraints:
  - 只改 `src/IM/frontend/**`, `src/IM/api/**`, `tests/**`, `TASKS/**`, `PROGRESS/**`, `ACCEPTANCE/**`, `data/dev-tasks.json`
  - 不碰 `src/agent/**`, `src/personal_assistant/**`, 与 workspace runtime 修复无关的后端深层逻辑
  - 需要真实页面/产品验收证据

### Plan
- R1: 收口 create/detail/list/allowlist 的信息架构与术语
- R2: 补真实页面产品验收证据并完成主干集成

### R1 收口 create/detail/list/allowlist 的信息架构与术语
- Context:
  - M224 已经把 runtime/workspace 语义修到可用，但 create/detail/list/allowlist 仍然把过多内部信息堆在首屏，尤其是 create 右栏、workspace preview、Read-only runtime path 与 allowlist 高噪音结构。
  - 本次只允许收口设置页 IA/文案，不重做 runtime 深层后端逻辑。
- Decision:
  - create 页改成单主路径结构，只保留 `Identity` / `Behavior` / `Access & model` / `Runtime` 四段。
  - workspace 文案统一拆成 `Workspace setting`、`Managed default directory`、`Current runtime directory` 三层语义；create 页额外显式说明 live runtime 只会在创建后出现。
  - allowlist 默认仅展示 `Common choices`，已保存高级项或当前不可用项统一进入 `Needs review`，删除 `Selected N`、chip cloud 与 `Show advanced options` 主路径噪音。
  - list 页与 detail 页对齐 create 页词汇，统一使用 `Runtime` / `Access`。
- Rationale:
  - 用户真正要做的决策是角色、行为、访问面与运行放置，不需要在首屏消费内部术语和次级提示。
  - 把 saved setting、managed default、live runtime 拆开后，能直接消除“页面展示值就是当前 pwd”的误导。
- Evidence:
  - Tests: `npx pnpm --dir src/IM/frontend test -- --run agent-create agent-detail agents-list-mobile allowlist-selector router && pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py`
  - Entry: create/detail/list/allowlist 的红测先锁定旧文案与旧结构，再由页面实现收口到新 IA 与统一词汇。
- Rollback: `d1eb5ff`（R1 红测稳定点）
- Commits: C1=`d1eb5ff`, C2=`013774a`, C3=`pending-this-docs-commit`
- Next: 用真实页面验证新 IA 已落到 dist 入口，而不是只在测试中通过。

### R2 补真实页面产品验收证据并完成主干集成
- Context:
  - M225 的退出条件要求真实页面级证据，不能只停在单测/集成测试。
  - 之前尝试直接复用现有 8011 服务时，页面仍指向旧 acceptance 数据与旧 dist，需要切到独立 runtime 才能避免被外部状态污染。
- Decision:
  - 使用 `/Users/czj/Repos/nano-multiagent/.worktrees/M225/ACCEPTANCE/m225-runtime/im_service.sqlite3` 作为独立验收数据库，并在 8013 端口启动隔离 IM 服务。
  - 重新 build M225 frontend dist，确保真实页面证据来自当前分支产物。
  - 用 Playwright CLI 对 list/create/detail 三页截图，并把观察结果固化到 `ACCEPTANCE/M225-acceptance.md` 与 `ACCEPTANCE/m225-runtime/m225-ui-observations.json`。
- Rationale:
  - 隔离 runtime 能避免误把其他 milestone 的 agents / dist / live state 当作本次证据。
  - 截图 + 结构化观察文件能同时证明视觉收口与具体文案变化。
- Evidence:
  - Tests: `npx pnpm --dir src/IM/frontend test -- --run agent-create agent-detail agents-list-mobile allowlist-selector router && PYTHONPATH=src pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py`
  - Entry: `http://127.0.0.1:8013/settings/agents`, `http://127.0.0.1:8013/settings/agents/new`, `http://127.0.0.1:8013/settings/agents/agent-m225-custom`
  - Artifacts:
    - `/Users/czj/Repos/nano-multiagent/.worktrees/M225/ACCEPTANCE/M225-acceptance.md`
    - `/Users/czj/Repos/nano-multiagent/.worktrees/M225/ACCEPTANCE/m225-runtime/m225-ui-observations.json`
    - `/Users/czj/Repos/nano-multiagent/.worktrees/M225/ACCEPTANCE/m225-runtime/m225-agents-list.png`
    - `/Users/czj/Repos/nano-multiagent/.worktrees/M225/ACCEPTANCE/m225-runtime/m225-agent-create.png`
    - `/Users/czj/Repos/nano-multiagent/.worktrees/M225/ACCEPTANCE/m225-runtime/m225-agent-detail-custom.png`
- Rollback: `013774a`（R1 实现全绿点）
- Commits: C1=`pending`, C2=`pending`, C3=`pending-this-docs-commit`
- Next: rebase `origin/main`，完成主干合并、dev-tasks 更新与 worktree 清理。
