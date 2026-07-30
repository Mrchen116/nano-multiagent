# M99 IM 节点管理 + 统计

## 启动记录
- 已阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。
- 注释规范承诺：后续新增 public module/class/function/method 均按 Google 风格 docstring 写契约；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M99，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M99`，branch=`milestone/M99`。
- 测试门禁：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M99/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M99/tests/im_service`。
- 基线结果：开始前定向基线 `46 passed in 1.24s`。
- prevention / 注意事项：
  - 仅在 IM M99 所需节点管理、统计 API、对应测试与 M99 文档内收口，不扩散到 M100/M105/M106。
  - 广泛改动后复查负向断言、导入路径和兼容结构，保持单一 canonical 结构。
  - 从商业产品视角审视：节点看板不仅要有 happy path，还要覆盖离线/降级、错误摘要、使用统计可读性。

## 实施记录
### R1 节点仓储与状态聚合
- Context: M99 需要 IM-SPEC §5 的节点看板与 `NodeStatus` 聚合，但现状只有基础 `nodes` 表和 owner 绑定，`node.register` / `node.heartbeat` 仅停留在 websocket 内存态。
- Decision: 扩展 `nodes` schema 与领域模型，增加 `relay_enabled`、`reporting_enabled`、`alias`；在 `NodeRepository` 内收口注册、心跳、断连与配置更新，并把原始 heartbeat 状态统一归一为 `online/offline/degraded`。
- Rationale: 让节点看板只依赖一个 canonical SQLite 读模型，避免 API 层拼装内存态和 DB 态两套结构；断连直接回写 offline，前端读取语义稳定。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M99/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M99/tests/im_service/unit/test_nodes_metrics_repositories.py`
  - 关键点：`GatewayHandler` 注册/心跳/断连均已同步到 `NodeRepository`，节点状态从 websocket 瞬时信息转为持久化看板数据。

### R2 节点 API
- Context: app 还未注册 `/im/v1/nodes`，也没有节点配置 PATCH 路由。
- Decision: 新增 `application/node_service.py` 与 `api/routes/nodes.py`，暴露 `GET /im/v1/nodes` 和 `PATCH /im/v1/nodes/{id}/config`，返回节点状态与中心配置合并视图。
- Rationale: 节点查询与修改都通过统一服务和统一响应模型，避免后续前端接多套字段。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M99/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M99/tests/im_service/integration/test_nodes_metrics_api.py`
  - 关键点：支持 alias / relay_enabled / reporting_enabled 更新，并保持 404 语义稳定。

### R3 使用统计 API
- Context: M99 要求 `GET /im/v1/metrics/usage`，但现有 IM 后端没有 usage 存储与聚合。
- Decision: 新增 `usage_metrics` 表、`UsageMetricsRepository`、`MetricsService` 和 `api/routes/metrics.py`；在 `WebIMService.create_message()` 里按 IM 可见消息写入最小 token/turn 样本，并按 owner/conversation/agent 维度聚合返回。
- Rationale: 先以 message write path 作为单一采样入口，满足 M99 token/turn 看板能力，同时不提前侵入 M100+ gateway/reporter 范围；商业产品视角下，至少可先展示对话与 Agent 的使用热点。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M99/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M99/tests/im_service/integration/test_nodes_metrics_api.py`
  - 关键点：同一 conversation 下可区分用户对话 usage 与 agent usage 聚合行。

## 验证
- 定向基线（改动前）：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M99/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M99/tests/im_service` → `46 passed in 1.24s`
- 收口验证（改动后）：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M99/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M99/tests/im_service` → `50 passed in 1.13s`

## 进行中
- 待补：git 提交、merge 到本地 main、board 更新为 DONE、worktree 清理。
