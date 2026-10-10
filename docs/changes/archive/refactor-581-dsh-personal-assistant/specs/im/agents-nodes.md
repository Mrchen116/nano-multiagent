# im/agents-nodes Specification (delta for refactor-581)

## MODIFIED Requirements

### Requirement: HEARTBEAT.md 只读预览与 cron 任务管理经 WS RPC 代理到 gateway（feat-394-M13 决策 G）

IM 进程**绝不**直读 gateway 侧 workspace 文件（IM 与 gateway 可跨机）。相关 endpoint 均经 WS RPC 将请求委托给目标节点 gateway，由 gateway 读写其本地 workspace 后回包，IM 做路由转发与离线降级。

#### Scenario: 获取 HEARTBEAT.md 预览内容
- **WHEN** 前端 `GET /im/v1/agents/{id}/heartbeat-md`
- **THEN** 200 返回 `{content: string, node_online: bool}`；节点在线时 content 为 `HEARTBEAT.md` 内容 （文件不存在则空串）；节点离线或 RPC 超时时 `{content:"", node_online:false}`

#### Scenario: 列 cron 任务经 RPC 代理
- **WHEN** 前端 `GET /im/v1/agents/{id}/cron/jobs`
- **THEN** 200 返回 jobs 数组；节点离线或超时时返回空列表（不报错），不直读 gateway 侧文件

#### Scenario: 删 cron 任务经 RPC 代理
- **WHEN** 前端 `DELETE /im/v1/agents/{id}/cron/jobs/{job_id}`
- **THEN** 204 表示删除成功；节点离线或 RPC 超时或 job_id 不存在均返回 404
