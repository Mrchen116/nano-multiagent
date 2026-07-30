# Runtime Troubleshooting

本文用于定位日常 IM、Gateway、Web IM 和外部通道故障。先保留首个错误、当前 config 和运行身份，再执行恢复动作；直接重启全部服务会丢失最有价值的因果证据。

## 诊断顺序

按数据流从外到内检查：

1. **运行对象**：当前 shell 属于哪个 checkout，Gateway 使用哪份 config，浏览器访问哪个 IM 地址。
2. **IM 可达性**：HTTP OpenAPI 是否可访问，Web IM 静态页面是否已经构建并由 IM host 提供。
3. **Gateway 进程**：`.gateway-state.json`、live process 和 `gateway.log` 是否属于同一 config 与同一次启动。
4. **连接和绑定**：节点是否已绑定、是否 online，日志中是否有 `ACTION ...`、`NEXT ...` 或首个 bootstrap 错误。
5. **真实路径**：登录、打开会话、发送消息、收到回复；只检查进程或接口不能替代用户路径。

默认 config 的基础证据：

```bash
GATEWAY_DIR="$HOME/.nano-assistant"

curl -fsS http://127.0.0.1:8011/openapi.json >/dev/null
test -f "$GATEWAY_DIR/.gateway-state.json" && sed -n '1,120p' "$GATEWAY_DIR/.gateway-state.json"
ps -ax -o pid=,command= | grep '[p]ersonal_assistant.main'
tail -n 100 "$GATEWAY_DIR/gateway.log"
```

`curl` 返回 `401` 的数据面接口仍然证明 HTTP 服务可达，只表示该接口要求 Bearer token。PID 文件、状态文件和历史日志都要与 live process 及本次启动时间交叉核对。

## 常见症状

| 症状 | 优先检查 | 恢复动作 |
|---|---|---|
| `/` 或 `/chat` 打不开 | IM 进程、`8011` 监听和 OpenAPI | 启动 IM；端口被占时确认占用者，不直接覆盖 |
| OpenAPI 可达但没有 Web IM 页面 | `src/IM/frontend/dist/index.html` 是否存在 | 在前端目录执行 `npm install && npm run build`，再刷新页面 |
| Gateway 启动后立刻退出 | `gateway.log` 的第一个错误、config 的 `llm:` / `web_relay` / IM 地址 | 修正原始配置后，对同一 config 重新启动 |
| `gateway already running` | 状态文件中的 config、PID 和 process birth | 需要替换时使用 `restart`；不要启动第二个同 config 实例 |
| `NOT RUNNING` 或 `STALE` | 是否传了与启动时相同的 `--config`，日志是否属于旧运行 | 确认 config；保存证据后重新启动 |
| 浏览器要求绑定 | `gateway.log` 中的 `NEXT Open ...` 和当前登录用户 | 用当前用户打开绑定页并确认，随后回到节点或聊天页 |
| Web IM 显示 Gateway offline | Gateway 进程、IM WebSocket、节点页面和 `last_error` | 先恢复 Gateway → IM 连接，再验证一次真实消息往返 |
| 进程存在但 Agent 能力为空或接口返回 503 | 是否残留旧 Gateway、`node_id` 是否被其他实例复用 | 停止目标 config 的旧实例，确认进程退出后再启动 |
| `workspace_root does not exist` | config 中显式 workspace 路径 | 创建准确目录，或移除显式值使用默认 workspace |
| Agent 不回复或 LLM 报错 | `llm.default_model`、provider 协议、代理健康和本次 LLM 日志 | 按 [`../可用LLM_API与联调说明.md`](../可用LLM_API与联调说明.md) 验证上游，再重试当前消息 |
| 飞书配置已保存但未连接 | Agent 通道页 runtime 诊断、节点 online 状态、App ID/Secret 和飞书长连接设置 | 先让节点 online；按页面诊断修正凭据或权限并执行重连 |
| 飞书普通群消息未进入上下文 | 飞书应用是否有 `im:message.group_msg` | 补齐 scope，等待或触发通道重连后复测 |
| 飞书主路径可用但 Web IM 没有新影子消息 | IM 是否离线或 Gateway 正在重连 | 先恢复 IM 连接；外部通道离线自治期间的单次同步允许暂缺 |

worktree 或 E2E 产生的端口、config、PID 和数据由 [`../development/worktree-runtime.md`](../development/worktree-runtime.md) 管理，不用日常实例的 state 文件判断它们。

## 安全恢复

1. 记录 config 绝对路径、启动命令、首个错误、`.gateway-state.json` 和相关日志时间。
2. 只对目标 config 执行 `stop` 或 `restart`；状态文件中的 PID 未通过 live birth 校验时，不向该 PID 手工发信号。
3. Gateway 需要重启时优先使用 `restart`，让 lifecycle lock 在同一次操作中完成 stop + start。
4. 整套服务需要关闭时先停 Gateway，再停 IM。
5. 恢复后重新验证节点 online 和一条真实消息往返，不以“命令没有报错”作为完成证明。

Gateway 的 fail-closed 进程识别和关闭顺序见 [`../specs/gateway/service-lifecycle.md`](../specs/gateway/service-lifecycle.md)。

## 认证和节点 API 诊断

以下命令用于页面无法提供足够信息时的手工诊断。正常用户路径直接使用 Web IM。

空库创建第一个账号：

```bash
PYTHONPATH=src .venv/bin/python -m IM.cli init_admin \
  --username root \
  --password '<set-strong-password>' \
  --display-name Root
```

登录并取得 token：

```bash
curl -sS -X POST http://127.0.0.1:8011/im/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"root","password":"<password>"}' \
  | python -m json.tool
```

把返回值写入当前 shell 的 `TOKEN` 后检查账号与节点：

```bash
TOKEN='<access-token>'

curl -sS -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8011/im/v1/me \
  | python -m json.tool

curl -sS -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8011/im/v1/nodes \
  | python -m json.tool
```

确实需要手工发起或确认绑定时：

```bash
curl -sS -X POST http://127.0.0.1:8011/im/v1/bind \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"action":"start","node_id":"my-macbook"}' \
  | python -m json.tool

curl -sS -X POST http://127.0.0.1:8011/im/v1/bind \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"action":"confirm","bind_id":"<bind-id>"}' \
  | python -m json.tool
```

用户事件 WebSocket 的低层诊断入口：

```bash
wscat -c "ws://127.0.0.1:8011/im/ws/user?token=$TOKEN"
```

自动化关键路径和真实进程测试属于开发反馈体系，入口见 [`../e2e-critical-paths.md`](../e2e-critical-paths.md) 与 [`../development/worktree-runtime.md`](../development/worktree-runtime.md)。
