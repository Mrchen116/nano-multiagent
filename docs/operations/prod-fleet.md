# 生产舰队（IM@mini + 双 Gateway）

本文描述个人生产拓扑：Mac mini 跑唯一 IM，本机与 mini 各跑一个常驻 Gateway，均连同一 IM。Agent 执行部署/重启时的逐步命令与局部动作表见 [`.claude/skills/prod-fleet-deploy/SKILL.md`](../../.claude/skills/prod-fleet-deploy/SKILL.md)。纯本机一次性主链路见 [`local-stack.md`](local-stack.md)；worktree 隔离见 [`../development/worktree-runtime.md`](../development/worktree-runtime.md)。

## 拓扑

```
本机 jmacbook-air                          Mac mini (ssh: mini)
Gateway node_id=macbook-air  ──Tailscale──▶ IM :8011（唯一）
LLM_PROXY :4000                            Gateway node_id=mac-mini
浏览器打开 mini:8011                        LLM_Bridge :4000
                                           SearXNG :8888
```

约束：

- 本机**禁止**再起 IM `:8011`；Web IM 入口为 `http://100.88.34.122:8011/`。
- 两边 `node_id` 必须不同；后连同名会踢掉先连。
- 两边 Gateway 使用同一个 IM owner；`node.user_id` 必须是该用户的 **IM UUID**（`GET /im/v1/me`），不能是用户名或占位符。错了会出现飞书能回、内部 IM 看不到影子会话。
- mini 上 LLM 走 `LLM_Bridge`；本机 Gateway 走本机 `LLM_PROXY`。两边 SearXNG 都指向 mini `:8888`。
- 两边 Gateway 的 `gateway.autostart` 保持默认开启，稳定的 SearXNG 地址写入各机 `gateway.environment.SEARXNG_URL`；不要依赖一次重启命令前的 inline 环境。

## 节点身份

| 机器 | `node_id` | `im_service.url` | LLM 代理 |
|---|---|---|---|
| Mac mini | `mac-mini` | `http://127.0.0.1:8011` | `~/Repos/LLM_Bridge` → `:4000` |
| 本机 | `macbook-air` | `http://100.88.34.122:8011` | `~/Repos/LLM_PROXY` → `:4000` |

各机使用各自的 `~/.nanoassistant/config.yaml`。`node.user_id` 对齐与飞书影子会话验收步骤见 skill 验证清单。

## 日常入口

| 任务 | 去做 |
|---|---|
| 全量更新代码并重启舰队 | 触发 `prod-fleet-deploy` 完整闭环 |
| 只重启 IM / 某一侧 Gateway / LLM 代理 | 同一 skill 的「局部动作」表 |
| 改 Gateway 配置 | 目标机先 `stop`，改 config，再启动；运行中直接编辑可能被 token 回写覆盖，细节见 [`gateway.md`](gateway.md) |
| 排障 | [`troubleshooting.md`](troubleshooting.md)；结合两边 `gateway.log` 与 IM `im-service.log` |

mini 的 IM 签名密钥是生产持久状态：`~/.nanoassistant/im-jwt-secret`（权限 `0600`）。常规更新在停止 IM 前读取并复用它，不能临时生成。需要主动换钥时才覆盖这个文件；换钥会使 Web IM 既有登录态失效，之后须重启两台 Gateway 让其重新认证并恢复在线。首次从旧目录升级时，先执行 [`PA workspace layout migration`](pa-workspace-layout-migration.md)，再按 [`prod-fleet-deploy` skill](../../.claude/skills/prod-fleet-deploy/SKILL.md) 完成启停与验收。

## 可用性判断

同时满足才视为舰队正常：

1. `http://100.88.34.122:8011/` 返回可用页面或 200。
2. `GET /im/v1/nodes` 中两个生产节点均为 `online`。
3. 本机 `lsof -ti:8011` 为空（无本地 IM）。
4. 两边 `node.user_id` 等于 `GET /im/v1/me` 的用户 id；gateway 日志无持续的 `configured node owner differs`。
5. 两边 LaunchAgent 均已加载；plist、live process 与 `.gateway-state.json` 都指向本次部署的 checkout 和同一 PID/process birth。本机旧 production worktree 只能在这些证据成立后清理。

## 飞书

飞书 Bot 只跑在 Mac mini Gateway（`mac-mini`）。本机 `macbook-air` 不承载飞书通道。

## IM 用户访问入口配置

IM 启动必须显式设置 `IM_PUBLIC_URL` 为用户实际打开 Web IM 的 HTTP(S) 绝对 URL；允许部署路径前缀，不允许凭据、query 或 fragment。它与 Gateway 的内部 `im_service.url` 独立。IM 在已认证的 `node.register` ACK 下发 `im_user_url`，Gateway 注册完成前不会启动依赖 IM 的 PA 工作；重连期间保留最近一次认证的入口，下一轮会话 runtime 使用新入口。

Gateway YAML 的 `node.execution_access_address` 可选，填写执行设备供用户访问的主机名或 IP（不含协议、端口、路径或凭据）；缺失时省略提示中的该行。此值仅提供访问事实，不开放监听端口、不授予文件权限，也不保证用户能访问任意服务。

升级前保留原配置并为 IM 增加 `IM_PUBLIC_URL`，先升级 IM 再升级 Gateway。旧 IM 未下发入口时，新 Gateway 报配置/版本不匹配，不采用内部连接地址猜测。回退代码时可保留新增环境变量；此配置说明不授权执行生产部署。
