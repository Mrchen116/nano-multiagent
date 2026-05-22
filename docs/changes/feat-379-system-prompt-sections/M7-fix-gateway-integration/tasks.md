# feat-379-M7: fix-gateway-integration — Tasks

## 目标

修复连续 3 轮 fail 的 3 个 issue，并用真实 live chain 证明每个症状消失。

## 退出标准

1. `GET /im/v1/nodes/{node_id}/capabilities` 返回非空 features 数组
2. PATCH features+custom_prompt → 真实重启 IM 和 Gateway → GET /config 仍含两字段
3. `POST /im/v1/agents/{id}/prompt-preview` 分别传 memory_curation true/false → 返回串不同
4. 浏览器：create 页 Features 开关组可见，detail 页切 memory_curation 预览变化

## 测试策略

后端：补 live-chain 验证（curl/httpx 真实服务），单测作为补充
前端：TypeScript 类型修复 + npm run build 验证，浏览器截图验收

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | ISSUE-1: Gateway node.capabilities 返回 FEATURE_REGISTRY 投影 | DONE |
| R2 | ISSUE-2: IM 重启后 features/custom_prompt 不丢失（PATCH + re-register 双路径） | DONE |
| R3 | ISSUE-3: Gateway WS 连接稳定 + preview 链路端到端通 | DONE |
| R4 | live chain 验证 + 前端构建 + 浏览器证据 | DONE |

## 测试策略（详）

- R1: 单测断言 `build_runtime_capabilities().as_payload()` 含 features 键；live chain curl 验证
- R2: 单测断言 upsert_profile 在 features=None 时保留旧值；live chain 重启验证
- R3: 集成测试 prompt-preview 端到端；live chain curl 验证内容差异
- R4: 浏览器 gstack-browse 截图

## UI 状态矩阵（create 页 Features 区块）

| 状态 | 覆盖 |
|---|---|
| default (node 在线) | Features checkbox 可见，按 default_on 渲染 |
| node 离线 | Features 区块可能空（capabilities 不可用）|
| feature 缺依赖工具 | checkbox disabled + tooltip |
| N/A | loading/error 态由父组件处理 |
