# M135 Agent 新增

## [DONE] R135.1 create flow red/green
- Steps:
  - 先写后端 contract/integration 红测，固定 `/im/v1/agents` 创建入口、节点绑定与 relay 证据。
  - 最小实现 IM create agent API，并补齐 list/detail 的 `bound_nodes/updated_at`。
  - 跑后端目标测试并记录证据。
- Expected Tests:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M135/tests/im_service/contract/test_agent_create_contract.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M135/tests/im_service/integration/test_agent_create_flow.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M135/tests/im_service/contract/test_agent_config_contract.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M135/tests/im_service/integration/test_agent_config_api.py`
- Evidence:
  - `pytest -q ...test_agent_create_contract.py ...test_agent_create_flow.py ...test_agent_config_contract.py ...test_agent_config_api.py` -> `5 passed in 0.38s`
- Rollback:
  - 移除 `POST /im/v1/agents` 与附加 `bound_nodes/updated_at` 字段，回退到只读 config API。
- Commits:
  - pending
- Next:
  - R135.2 前端真实入口与测试

## [DONE] R135.2 frontend real entry
- Steps:
  - 安装 `/Users/czj/Repos/nano-multiagent/.worktrees/M135/src/IM/frontend` 依赖。
  - 对 `agent-create.test.tsx` / `agent-edit.test.tsx` 执行目标 vitest，最小修正 create flow 测试，使其直接锁定提交 payload 与跳转行为，不再依赖 jsdom fetch/AbortSignal 细节。
  - 重建前端 dist，修复真实 IM host `/settings/agents` 空白页。
- Expected Tests:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M135/src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M135/src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
- Evidence:
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M135/src/IM/frontend install` -> `added 253 packages, and audited 254 packages in 3s`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M135/src/IM/frontend test -- --run src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx` -> `2 passed (2 files), 3 passed (3 tests)`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M135/src/IM/frontend run build` -> build passed，并生成 `dist/assets/index-DgEIGfWH.js` / `dist/assets/index-dwZKXoD9.css`。
  - `GET http://127.0.0.1:8011/assets/index-DgEIGfWH.js` 在重启 IM host 后返回 `200`，证明真实入口静态资源恢复可达。
- Rollback:
  - 删除 `agent-create-page.tsx`、router 新路由、列表入口与 create API client。
- Commits:
  - `dbb0a39 fix(M135): restore agent create settings entry`
  - frontend test stabilization commit pending in current changeset
- Next:
  - R135.3 真实浏览器证据

## [DONE] R135.3 real-entry evidence
- Steps:
  - 启动 IM frontend host + backend + Gateway。
  - 使用真实浏览器从 `/settings/agents` 进入 `New Agent`，提交 `Create Agent`。
  - 采集浏览器路径证据与接口返回证据，并更新 milestone 文档。
- Expected Tests:
  - Playwright real browser flow
  - targeted backend/frontend regression
- Evidence:
  - 真实浏览器链路：
    - `list_heading=Agents`
    - `new_agent_visible=True`
    - `create_url=http://127.0.0.1:8011/settings/agents/new`
    - `detail_url=http://127.0.0.1:8011/settings/agents/agent-m135-browser`
    - `detail_heading=Agent Detail`
    - `profile_version=Profile Version: 1`
  - 真实创建结果：
    - `GET /im/v1/agents` 含 `agent-m135-browser`，`bound_nodes=['m135-node']`
    - `GET /im/v1/agents/agent-m135-browser/config` 返回创建表单对应字段，`profile_version=1`
  - 收尾回归：`npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M135/src/IM/frontend test -- --run src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx` -> `2 passed (2 files), 3 passed (3 tests)`
- Rollback:
  - 如需回退真实入口验证环境，删除 `/Users/czj/Repos/nano-multiagent/.worktrees/M135/node-config.yaml` 并停止当前 Gateway/IM 进程。
- Commits:
  - `dbb0a39 fix(M135): restore agent create settings entry`
  - frontend test stabilization commit pending in current changeset
