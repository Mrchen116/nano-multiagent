# M2: pa-im-ask-rendering — Tasks

## 目标

PA + IM 后端 + IM 前端三层 `ask` 渲染链路：

- **PA**：`inbound_pipeline` 消费 `permission_request` SSE → 转 `node.streaming_delta`；消费 IM 决策 → POST 回 agent inbound；heartbeat run 传 `origin=RunOrigin.HEARTBEAT`。
- **IM 后端**：`gateway_handler` 新增 `permission_request` / `permission_resolved` / `permission_response` 三个 kind、`Message` 嵌入式 permission 结构、EventBridge upsert、新增 REST 端点接收用户决策、WS fan-out。
- **IM 前端**：聊天流内嵌权限卡片组件 + `types.ts` 类型 + `message-pane.tsx` 挂载点。

## 退出标准（[worker] 自验）

- `pytest tests/unit/`（IM / PA 相关）不比 M2 开始前新增失败
- `cd src/IM/frontend && npm run test` 全绿（含新增权限卡片测试）
- `pytest -m "not e2e" --continue-on-collection-errors` 不比 baseline 新增失败（baseline = 211 failed / 1403+ passed）
- progress.md Evidence 包含前端权限卡片真实浏览器/组件测试证据

## 测试策略

### PA 侧
- 单元测试：`inbound_pipeline` 的 `_on_other_event` 扩展（permission_request 转发）+ permission_response 消费 → POST
- 真实入口：mock agent SSE 事件流，验证正确 emit `node.streaming_delta` 并 POST 到 agent inbound

### IM 后端侧
- 单元测试：`gateway_handler._handle_streaming_delta` 对新 kind 的 EventBridge 调用
- 单元测试：`EventBridge.on_permission_request` / `on_permission_resolved` 更新 Message 嵌入式 JSON
- 单元测试：新 REST 端点 `POST /im/v1/conversations/{cid}/permissions/{request_id}` 转发 Gateway WS

### IM 前端侧
- 组件测试（vitest）：`PermissionCard` 组件 pending/submitting/resolved 三态
- 组件测试：`message-pane.tsx` 挂载点在 message 有 `permission_request` 时渲染卡片
- 状态矩阵覆盖：pending / submitting / resolved / timeout / mobile

## UI 状态矩阵（权限卡片）

| 状态 | 描述 | 覆盖方式 |
|---|---|---|
| default (pending) | 显示工具名 + reason + 选项按钮 | 组件测试 |
| submitting | 用户点击后按钮 disabled，spinner | 组件测试 |
| resolved (allow) | 按钮替换为"已允许·option" | 组件测试 |
| resolved (deny) | 按钮替换为"已拒绝" | 组件测试 |
| error | POST 失败后显示错误文字 | 组件测试 |
| mobile | N/A（卡片嵌入消息流，不影响 viewport） | N/A |
| desktop | 嵌入消息流，输入框不被阻塞 | 浏览器验收截图 |

## 用户路径分类

- `PermissionCard` 组件：`normal-ui` — 组件测试 + 浏览器临时验收
- `message-pane` 挂载点：`normal-ui` — 组件测试

## 风险点与验收方式

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| PA 消费 permission_request SSE 并转 node.streaming_delta | 单元测试 mock SSE stream | 是 |
| IM gateway_handler 新 kind 正确 upsert permission JSON | 单元测试 | 是 |
| IM REST 端点转 Gateway WS permission_response | 单元测试 TestClient | 是 |
| PermissionCard pending→submitting→resolved 状态机 | 组件测试 vitest | 是 |
| message-pane 挂载点渲染卡片 | 组件测试 vitest | 是 |
| heartbeat run origin 传递 | 单元测试 | 是 |
| 前端卡片视觉 | 浏览器 screenshot | 否 |

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | IM 后端：gateway_handler 新三 kind + EventBridge permission upsert | DONE |
| R2 | IM 后端：REST 端点 + WS fan-out permission_response | TODO |
| R3 | PA：permission_request SSE 消费 + heartbeat origin 修复 | TODO |
| R4 | IM 前端：PermissionCard 组件 + types.ts + message-pane 挂载点 | TODO |
