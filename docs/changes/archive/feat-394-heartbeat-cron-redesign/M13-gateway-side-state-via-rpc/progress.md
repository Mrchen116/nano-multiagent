# feat-394-M13 Progress

## 启动记录

- 基线：2575 passed, 2 failed（macOS 预存 known failures，与本 milestone 无关）
- 范围确认：
  1. HEARTBEAT.md 只读预览：gateway_handler.py + im_connection.py + agents.py + 前端
  2. cron jobs list/delete 改 RPC：gateway_handler.py + im_connection.py + agents.py
- 关键参照：`request_node_prompt_preview`（waiter + `_push_downstream` + gateway 侧 handler）

---

### R1 — IM WS RPC 三方法 + handle 方法（gateway_handler.py）

DONE。新增 `request_node_heartbeat_md` / `request_node_cron_jobs` / `request_node_cron_delete`
三个 RPC 方法 + 三个 `_handle_*` 方法。waiter 模式与 `request_node_prompt_preview` 完全一致。
8 个单测全绿。

---

### R2 — gateway 侧帧处理（im_connection.py）

DONE。新增 `node.heartbeat.md.request` / `node.cron.jobs.request` / `node.cron.delete.request`
三个 request 帧处理分支；gateway 读写自己的 workspace 文件后回帧。
额外修复：将硬编码 `.nanoassistant` 改为从 `personal_assistant.defaults.WORKSPACE_CONFIG_DIRNAME`
引用，新建 `src/personal_assistant/defaults.py`，通过 contract 测试。5 个单测全绿。

---

### R3 — IM 路由层（agents.py）

DONE。`list_agent_cron_jobs` / `delete_agent_cron_job` 改为 async + WS RPC（移除直读文件逻辑）；
新增 `GET /im/v1/agents/{id}/heartbeat-md` 端点（返回 `{content, node_online}`）。
6 个集成测试全绿。

---

### R4 — 前端 heartbeat-md 折叠预览（agent-detail-page.tsx）

DONE。HeartbeatCard 新增可折叠 HEARTBEAT.md 只读预览 panel，仿 promptPreview 交互。
支持 loading / node offline / 文件不存在 / 有内容四态。tsc -b 干净，vitest(主仓) 345 passed。
新增 `getAgentHeartbeatMd` API 到 `im-agent-config-api.ts`。

---

### R5 — 全树验证 + delta-spec

DONE。2594 passed，2 failed（均为 baseline macOS `/tmp` symlink 问题，与 M13 无关，
主仓 origin 同样失败）。`docs/specs/im/spec.md` 和 `docs/specs/gateway/spec.md` 均已更新
M13 delta（HEARTBEAT.md RPC + cron RPC + 决策 G 说明）。

---

## 收尾

- `milestone/feat-394-M13` FF merge → `unit/feat-394`（`c34658ae`）
- unit/feat-394 新 tip：`c34658ae`
- milestone 分支 + worktree 待清理
