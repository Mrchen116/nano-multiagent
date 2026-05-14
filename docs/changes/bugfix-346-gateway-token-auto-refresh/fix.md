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

<!-- 改了什么 + commits。worker 完成后补全。 -->

## 验证

<!-- 修前能复现 → 修后不能；相关功能回归正常。worker 完成后补全。 -->
