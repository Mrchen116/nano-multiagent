# M1-fix: Gateway Token Auto-Refresh

## 目标

修复 Gateway 断线重连时使用过期 access_token 的问题，使其在每次重连时自动刷新 token。

## 退出标准

1. `IMServiceConfig` 新增 `refresh_token`、`username`、`password` 可选字段
2. 新建 `src/personal_assistant/auth/im_auth_client.py` 封装 refresh + login 两个 HTTP 操作
3. `IMConnectionManager.connect_once()` 接受 `token_getter` 回调，每次重连调用以获取最新 access_token
4. `build_runtime()` / `_build_im_connection_manager()` 组装 token_getter 闭包：优先 refresh_token，失败则 username+password login，成功后持久化新 refresh_token
5. 单元测试覆盖：IMAuthClient refresh/login 路径、token_getter 集成到 connect_once

## 测试策略

- 后端纯逻辑改动，不涉及前端 UI
- 新建 `tests/unit/personal_assistant/test_im_auth_client.py`：测试 IMAuthClient.refresh() 和 IMAuthClient.login()（用 httpx.MockTransport）
- 在已有 `test_m102_gateway_im_connection.py` 中补：token_getter 被正确调用、token_getter 返回的 token 写入 Authorization header

## Roadpoints

| ID | 标题 | 状态 |
|----|------|------|
| R1 | IMServiceConfig 扩展字段 + 解析/序列化 | DONE |
| R2 | IMAuthClient（refresh + login） | DONE |
| R3 | IMConnectionManager 接受 token_getter | DONE |
| R4 | build_runtime 组装 token_getter 闭包并持久化 | DONE |
