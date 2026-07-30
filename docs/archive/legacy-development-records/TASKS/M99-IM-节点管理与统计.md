# M99 IM 节点管理 + 统计

## 前置确认
- 已先阅读 `SPEC.md`、`docs/IM-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。
- 本 Milestone 的代码与文档将遵守 `COMMENTING_GUIDE.md` 的 public API docstring / 注释规范。
- 参考 LOGBOOK 与里程碑约束：先跑真实基线；保持 IM 内单一 canonical 结构；仅修改 M99 所需的节点管理、统计 API、相关测试与 M99 文档/board。

## 当前处境
- Milestone: M99 / IM 节点管理 + 统计
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M99`
- branch: `milestone/M99`
- 测试门禁命令: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M99/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M99/tests/im_service`
- 基线结果: `46 passed`
- 当前已发现差距:
  - 后端尚未注册 `/im/v1/nodes`、`/im/v1/metrics/usage` 路由。
  - `NodeRepository` 只有基础 upsert/get/assign_owner，缺少节点配置、状态聚合、列表查询。
  - WebSocket `node.register` / `node.heartbeat` 只保留内存连接态，没有把节点状态聚合回 SQLite。
  - 统计面尚无 token/turn 聚合模型与 API。

## Roadpoints

### R1 节点仓储与应用服务
- Status: TODO
- Acceptance:
  - 扩展节点领域模型与 SQLite schema，补齐节点中心配置字段（别名、中继开关、上报开关）与心跳聚合输入。
  - `NodeRepository` 支持列表查询、配置更新、注册/心跳聚合写入，状态可归一为 `online/offline/degraded`。
  - 新增应用服务收口节点看板查询与配置修改。
- Tests Plan:
  - unit: 仓储状态聚合与配置更新测试。
  - integration: 通过 websocket/register/heartbeat 驱动 SQLite 状态回写。

### R2 节点 API
- Status: TODO
- Acceptance:
  - `GET /im/v1/nodes` 返回节点看板列表。
  - `PATCH /im/v1/nodes/{id}/config` 返回更新后的节点配置与状态。
  - app 注册 `nodes` 路由，错误语义稳定。
- Tests Plan:
  - contract + integration: 节点列表、配置更新、404/400 场景。

### R3 使用统计 API
- Status: TODO
- Acceptance:
  - 为消息/relay/报告链路补足最小 usage 聚合来源，提供 Token/Turn 统计读模型。
  - `GET /im/v1/metrics/usage` 至少支持 owner / conversation / agent 维度的汇总返回。
  - 统计实现保持 M99 scope，不提前侵入 M100+ 或前端大改。
- Tests Plan:
  - unit + integration + contract: usage 聚合和 API 返回。

### 收尾
- Status: TODO
- Acceptance:
  - 更新 `PROGRESS/M99-*.md`，写清已读 SPEC、决策、证据、回滚点。
  - 在 worktree 内跑 `PYTHONPATH=src pytest -q tests/im_service`。
  - 完成后合并到本地 `main`、更新 `data/dev-tasks.json` 为 `DONE` 并记录结果，按要求清理 M99 worktree。
