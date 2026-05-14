# bugfix-346: Gateway 断线后自动刷新 token 重连

## Relations

- Related: feat-340-agent-native-im
- Closes: #6

## 原始报告

> 当前 Gateway 连接 IM 使用 15 分钟有效期的 access_token。当 IM 服务重启或 token 自然过期后，Gateway 无法自动恢复连接，导致：
>
> 1. 用户在 IM 前端发送消息给 agent，agent **收不到**
> 2. 用户在 IM 前端新建 agent，提示 **"target_node_id is not connected"**
> 3. 用户必须手动重新登录、获取新 token、修改 Gateway config 文件，才能恢复
>
> — issue #6，2026-05

## 现象 / 复现

1. 启动 IM 服务，登录获取 token，写入 `~/.nano-assistant/config.yaml`，启动 Gateway
2. Gateway 显示 `[connected]`
3. 等 15 分钟，或重启 IM 服务
4. Gateway 日志停止打印心跳，WebSocket 断开
5. 前端发消息给 agent → 无响应
6. 前端新建 agent → 503 "target\_node\_id is not connected"
7. 唯一恢复方式：人工更新 config 里的 access\_token

## 根因

**直接原因**：`IMConnectionManager.connect_once()`（`src/personal_assistant/ws/im_connection.py:182`）在重连时直接复用 `IMConnectionConfig.token`，该值是启动时从 config 文件读入的固定字符串，不会随时间更新。access\_token 15 分钟过期后重连必然被 IM 以 401 拒绝。

**为什么能进来**：

- `IMServiceConfig`（`local_store.py:113`）设计时只有 `url + token` 两字段，没有预留 `refresh_token`，也没有 credential 存储，refresh 路径在 Gateway 侧从来没有实现入口。
- `run_forever()` 的重试循环把所有异常（包括 auth 失败）都当网络抖动处理，在指数退避后用同一个过期 token 继续重试，没有区分 auth 错误和连接错误。
- IM 服务端的 `POST /im/v1/auth/refresh` 接口早已实现（带 token 轮换），但 Gateway 侧从未调用过，两侧形成了"服务端准备好、客户端从未接入"的对称缺口。

## 修复

### 改动文件

| 文件 | 说明 |
|---|---|
| `src/personal_assistant/config/local_store.py` | `IMServiceConfig` 新增三个可选字段：`refresh_token`、`username`、`password`；`_parse_im_service` 和 `save_local_config` 同步支持解析和序列化 |
| `src/personal_assistant/auth/im_auth_client.py` | 新建 `IMAuthClient`：封装 `POST /im/v1/auth/refresh`（优先）和 `POST /im/v1/auth/login`（兜底）两个异步 HTTP 操作；`IMAuthError` 统一表达认证失败 |
| `src/personal_assistant/auth/__init__.py` | 新建 `auth` 子包 |
| `src/personal_assistant/ws/im_connection.py` | `IMConnectionManager.__init__` 增加 `token_getter: TokenGetter | None` 参数；`connect_once()` 在建立连接前优先调用 `token_getter` 获取最新 access_token，无 getter 时回退到 `config.token`（向后兼容） |
| `src/personal_assistant/main.py` | 新增 `_make_token_getter` 闭包工厂函数：优先用 `refresh_token` 换新 token，失败则用 `username+password` 登录，成功后通过 `save_local_config` 把新 token 对持久化到 `config.yaml`；`_build_im_connection_manager` 增加 `token_getter` 参数；`build_runtime` 在有 `im_service` 时创建 `IMAuthClient` 和 `token_getter` 并注入 |

### Commit 列表

- R1 C2: `f6a1f47e` — IMServiceConfig 增加 refresh_token/username/password 字段及序列化
- R2 C2: `467aee87` — 新建 IMAuthClient
- R3 C2: `03f416e6` — IMConnectionManager 接受 token_getter 回调
- R4 C2: `a298ef31` — build_runtime 组装 token_getter 闭包

## 验证

### 自动化测试覆盖

**修前复现路径**（R1 Red 阶段已在测试文件中捕获）：
- `test_im_service_config_refresh_token_and_credentials_round_trip` 在修前抛 `AttributeError: 'IMServiceConfig' object has no attribute 'refresh_token'` → 证明字段缺失是实际 bug 入口
- `test_connect_once_calls_token_getter_and_uses_returned_token` 在修前抛 `TypeError: IMConnectionManager.__init__() got an unexpected keyword argument 'token_getter'` → 证明原始代码不支持动态 token

**修后全绿**：
```
tests/unit/personal_assistant/ 250 passed
```

### 行为验证

1. `IMServiceConfig` 的 YAML 往返：写入 `refresh_token`/`username`/`password`，`load_local_config` → `save_local_config` → `load_local_config` 结果不变（`test_im_service_config_refresh_token_and_credentials_round_trip`）
2. `IMAuthClient.refresh()` 正确发送 `POST /im/v1/auth/refresh` body 并返回新 token pair（`test_refresh_sends_correct_body`、`test_refresh_returns_new_tokens_on_success`）
3. `IMAuthClient.login()` 正确发送 `POST /im/v1/auth/login` body（`test_login_sends_correct_body`）
4. `connect_once()` 使用 `token_getter` 返回值而非 `config.token` 写入 Authorization 头（`test_connect_once_calls_token_getter_and_uses_returned_token`）
5. `_make_token_getter` 闭包：refresh 成功 → 返回新 access_token 并持久化（`test_make_token_getter_uses_refresh_token_first`）；refresh 失败 → fallback login（`test_make_token_getter_falls_back_to_login_when_refresh_fails`）；无 refresh_token 和 credentials → 返回静态 token（`test_make_token_getter_returns_static_token_when_no_refresh_or_credentials`）

### 回归说明

所有已有 `test_m102_gateway_im_connection.py` 测试（24 个）、`test_local_store.py`（20 个）、`test_main.py`（55 个）全部通过，无行为回归。
