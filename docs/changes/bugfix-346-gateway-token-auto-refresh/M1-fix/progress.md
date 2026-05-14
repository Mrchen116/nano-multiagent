# M1-fix Progress

## Roadpoints

### R1 — IMServiceConfig 扩展字段

- Context: IMServiceConfig 只有 url+token 两字段，无 refresh_token/username/password，refresh 路径无入口
- Decision: 在 frozen dataclass 里新增三个可选字段；`_parse_im_service` / `save_local_config` 同步支持
- Rationale: 最小改动，向后兼容（字段均可选），不破坏现有 YAML
- Evidence:
  - Tests: test_local_store.py 39 passed
  - Entry: N/A（配置解析，无 HTTP 入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 见 R1 测试文件新增用例
  - Visual/Interaction: N/A
- Rollback: C3 hash 见下
- Commits: C1=TBD, C2=TBD, C3=TBD

### R2 — IMAuthClient

- Context: Gateway 侧从未调用 `POST /im/v1/auth/refresh`，缺少异步 HTTP 封装
- Decision: 新建 `src/personal_assistant/auth/im_auth_client.py`，封装 refresh() 和 login()；用 httpx.AsyncClient
- Rationale: 独立模块便于注入测试；不复用现有同步 `_IMConfigSyncClient` 的 httpx.Client（auth 需要 async）
- Evidence:
  - Tests: test_im_auth_client.py 全绿
  - Entry: 通过 httpx.MockTransport 验证真实 HTTP body/header
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: test_im_auth_client.py
  - Visual/Interaction: N/A
- Rollback: C3 hash 见下
- Commits: C1=TBD, C2=TBD, C3=TBD

### R3 — IMConnectionManager 接受 token_getter

- Context: `connect_once()` 硬读 `config.token`，token 过期后重连必然被 401 拒绝
- Decision: 在 `__init__` 增加 `token_getter: Callable[[], Awaitable[str | None]] | None`；`connect_once()` 优先调用它
- Rationale: 回调注入，不改 IMConnectionConfig 的不可变性；老代码不传 token_getter 行为不变
- Evidence:
  - Tests: test_m102_gateway_im_connection.py 补用例，全绿
  - Entry: 单元测试验证 token_getter 被调用 + header 正确
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: test_m102_gateway_im_connection.py 新增 test_connect_once_calls_token_getter
  - Visual/Interaction: N/A
- Rollback: C3 hash 见下
- Commits: C1=TBD, C2=TBD, C3=TBD

### R4 — build_runtime 组装 token_getter 闭包

- Context: `_build_im_connection_manager` 只传 `token=im_service.token`，无 refresh 逻辑
- Decision: 在 `build_runtime` 组装 `_make_token_getter` 闭包：优先 refresh_token，失败则 username+password login，成功后 `save_local_config` 持久化新 refresh_token
- Rationale: bootstrap 层负责 side effect（持久化），connection 层只负责拿 token；职责分离
- Evidence:
  - Tests: test_main.py 相关测试保持绿；新增 test_token_getter_* 用例
  - Entry: 通过 mock IMAuthClient 验证闭包行为
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: test_main.py 新增
  - Visual/Interaction: N/A
- Rollback: C3 hash 见下
- Commits: C1=TBD, C2=TBD, C3=TBD
