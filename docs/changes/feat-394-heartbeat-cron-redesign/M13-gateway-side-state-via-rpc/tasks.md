# feat-394-M13: gateway-side-state-via-rpc — Tasks

## 目标

消除「IM 进程直读 gateway workspace 文件」的跨机假设，改为经 IM↔gateway WS RPC 向该 node 请求、
gateway 读/改自己的文件后回传。两件事：
1. HEARTBEAT.md 只读预览（新功能，M11 移交至此）
2. cron jobs list/delete 改 RPC（修既存缺陷 M3 WARNING-3）

## 退出标准

- `[worker]` HEARTBEAT.md 预览经 `node.heartbeat.md.request` RPC、IM 不直读文件 的测试
- `[worker]` cron jobs list/delete 经 `request_node_cron_*` RPC、不再直读 `<workspace>` 文件 的测试（含 node 离线降级）
- `[worker]` `pytest -m "not e2e"` 全绿（含 im_service）+ tsc -b + vitest 绿
- `[reviewer]` heartbeat 特性下可展开只读查看当前 HEARTBEAT.md 全文（数据来自 gateway，非 IM 本机）
- `[reviewer]` 配置页 cron 任务列表/删除照常可用
- `[reviewer]` node 离线时预览/列表优雅降级（空 + 提示，不报错）

## 测试策略

后端：
- gateway_handler.py 新增 RPC 方法 + handle 方法：IM 单元测试（`tests/im_service/unit/test_gateway_handler.py` 扩充）
- agents.py 新路由 + 改旧路由：IM 集成测试（`tests/im_service/integration/test_agent_config_api.py` 扩充）
- im_connection.py 新增 request 帧处理：gateway 单元测试（`tests/unit/personal_assistant/test_gateway_im_connection_behavior.py` 扩充）
- node 离线降级覆盖：gateway_handler 单测（返回 None 时路由优雅处理）

前端（普通 UI 改动）：
- `im-agent-config-api.ts` 新增 `getAgentHeartbeatMd()`：vitest 单元测试
- `agent-detail-page.tsx` 新增折叠预览 panel：浏览器验收 + 状态矩阵

UI 状态矩阵（heartbeat 预览 panel）：

| 状态 | 覆盖方式 |
|---|---|
| default（未展开）| 浏览器验收 |
| loading | 浏览器验收 |
| empty（node 离线 / 文件不存在）| 浏览器验收 |
| error（网络错误）| N/A（走降级 empty） |
| 展开有内容 | 浏览器验收 |
| disabled（heartbeat 未开启）| N/A（panel 整体不显示） |

用户路径分类：
- HEARTBEAT.md 预览：`normal-ui` — 折叠面板，浏览器临时验收
- cron jobs list/delete：`bug-regression` — 必须补 regression（改了跨机正确性）

## Roadpoints

| ID | 标题 | 状态 | 说明 |
|---|---|---|---|
| R1 | IM WS RPC — heartbeat-md + cron 三方法（红测 + 实现） | TODO | gateway_handler.py 新增 3 个 RPC + 3 个 handle 方法；IM 单测红→绿 |
| R2 | gateway 侧帧处理（红测 + 实现） | TODO | im_connection.py 新增 2 个 request 帧处理；gateway 单测红→绿 |
| R3 | IM 路由层（红测 + 实现）：新 heartbeat-md 端点 + 改 cron jobs 路由 | TODO | agents.py 改旧 2 路由 + 新增 1 路由；IM 集成测试红→绿；不直读文件 |
| R4 | 前端：heartbeat-md 折叠预览 panel + API client | TODO | im-agent-config-api.ts + agent-detail-page.tsx；vitest + 浏览器验收 |
| R5 | 全树验证 + delta-spec 更新 | TODO | pytest 全绿 + tsc -b + vitest；更新 docs/specs/{im,gateway}/spec.md |
