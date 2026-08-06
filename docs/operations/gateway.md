# Gateway Operations

本文负责日常 Gateway 持久配置、后台进程生命周期、外部通道和运行时 provider 配置。Gateway 的对外可观察行为由 [`../specs/gateway/`](../specs/gateway/spec.md) 定义。

## 持久配置

默认 config 是 `~/.nano-assistant/config.yaml`。它属于本机运行配置，可能包含上游地址和登录凭据，不提交仓库。使用其他 config 时，start、stop 和 restart 都应传同一绝对路径。

下面是结构示例；把尖括号内容替换成本机实际值：

```yaml
node:
  node_id: my-macbook

agents:
  - agent_id: assistant
    title: My Assistant

channels:
  - name: web_relay
    enabled: true

im_service:
  url: http://127.0.0.1:8011
  # username: <im-username>
  # password: <im-password>

llm:
  default_model: <model-id>
  # tool_approval_model: <registered-model-id>
  providers:
    - name: anthropic
      base_url: <anthropic-compatible-base-url>
      models:
        - name: <model-id>
```

关键约束：

- `llm:` 必填，`llm.default_model` 必须出现在某个 `llm.providers[].models[]` 中。
- `llm.tool_approval_model` 可选。配置后，所有 PA Agent 的自动工具权限分类都使用这个已注册模型；省略时，各次分类复用发起运行的 Agent 模型。空值或未注册值会让 Gateway 拒绝启动。
- 专用审批模型只影响自动分类，不改变 Agent 的正常回复或工具结果续跑模型。分类调用失败时不会改用 Agent 模型或其他模型；有人值守时进入既有显式审批，无人值守时遵守既有 unattended fallback。
- 修改 `llm.tool_approval_model` 后需要重启 Gateway；运行中的进程不会热加载该字段。
- provider name 使用 `anthropic` 或 `openai_compat`，与上游接口协议匹配。
- `im_service` 存在时需要启用内置 `web_relay`。
- `agents[].workspace_root` 省略时，Gateway 为该 Agent 使用默认 workspace；需要固定位置时显式填写绝对路径。
- `im_service.username` / `password` 可用于 Gateway 首次登录和 token 刷新失败后的凭据回退。
- 本地 LLM 代理配置、协议、交互日志和验证方法见 [`../development/llm-integration.md`](../development/llm-integration.md)。

## 启动、停止与重启

默认 config：

```bash
PYTHONPATH=src .venv/bin/python -m personal_assistant.main
PYTHONPATH=src .venv/bin/python -m personal_assistant.main stop
PYTHONPATH=src .venv/bin/python -m personal_assistant.main restart
```

指定 config：

```bash
GATEWAY_CONFIG=/absolute/path/to/config.yaml

PYTHONPATH=src .venv/bin/python -m personal_assistant.main --config "$GATEWAY_CONFIG"
PYTHONPATH=src .venv/bin/python -m personal_assistant.main stop --config "$GATEWAY_CONFIG"
PYTHONPATH=src .venv/bin/python -m personal_assistant.main restart --config "$GATEWAY_CONFIG"
```

调试时可以把 Gateway 附着在当前终端：

```bash
PYTHONPATH=src .venv/bin/python -m personal_assistant.main \
  --config "$GATEWAY_CONFIG" \
  --foreground
```

`--im-service-url` 只覆盖本次启动连接的 IM 地址。`--auto-bind` 自动确认首次节点绑定，供脚本和 E2E 使用；日常实例通过浏览器确认绑定。

## 运行状态与可用性

同一 config 的 start、stop 和 restart 由 config 目录中的 lifecycle lock 串行化。后台实例的 PID、规范化 config 路径和 process birth 写入同目录的 `.gateway-state.json`，运行日志写入 `gateway.log`。

生命周期命令的结果：

| 输出 | 含义 | 下一步 |
|---|---|---|
| `Gateway started (pid=...)` | 后台 child 已写入有效运行态，启动命令可以返回 | 继续看日志和 IM 节点状态 |
| `STOPPED ...` | 目标实例已停止；超时强停时带 `forced=true` | 可以关闭 IM 或再次启动 |
| `NOT RUNNING ...` | 该 config 目录没有可管理的运行态 | 确认 config 后直接启动 |
| `STALE ...` | 状态文件中的进程身份已经失效，CLI 已清理陈旧状态 | 保留相关日志后重新启动 |

Gateway 可用需要同时满足：

1. `.gateway-state.json` 指向的 process birth 仍然匹配存活进程。
2. `gateway.log` 中没有被后续关闭掩盖的启动首因，并已进入预期的连接或离线重试状态。
3. IM 节点页面显示目标 node 已绑定且 online。
4. Web IM 的真实消息路径能够完成一次往返。

IM 暂时不可达时，Gateway 可以保持本地自治并继续重连；Web IM 路径要等 IM 连接和节点状态恢复。详细契约见 [`../specs/gateway/service-lifecycle.md`](../specs/gateway/service-lifecycle.md)。

## 外部通道

外部通道由 Web IM 托管。Gateway 至少上线一次、完成节点绑定并登记凭据公钥后，在 Web IM 打开 `/settings/agents/<agent_id>`，进入“通道”页，选择“添加通道”，再按向导填写飞书 App ID 和 App Secret。

当前流程的要点：

- provider catalog 当前包含飞书；同一 Agent 最多配置一个飞书实例。
- 飞书应用需要启用 Bot 和长连接，并授予消息收发权限。需要让未 @Bot 的普通群消息成为后续上下文时，还要授予 `im:message.group_msg`。
- 保存成功表示 desired state 已提交；页面中的 runtime 状态和诊断信息表示 Gateway 是否已经实际连接。
- App Secret 经 IM 封装后交给目标节点，不写入普通 `config.yaml`、日志或 HTTP 响应。
- Gateway 在线时新增、编辑、停用、重连或删除通道会热调和；IM 暂时不可达时，已应用通道可以从本机密文 cache 恢复。

用户可见行为、安全边界和离线自治以 [`../specs/gateway/external-channels.md`](../specs/gateway/external-channels.md) 与 [`../specs/im/agents-nodes.md`](../specs/im/agents-nodes.md) 为准。

## `web_search` provider

Gateway 进程通过环境变量选择 `web_search` 的运行时 provider：

| provider | 配置 | 默认行为 |
|---|---|---|
| DuckDuckGo | 无需环境变量 | 未配置其他默认项时使用 |
| Brave | `BRAVE_API_KEY` | 调用时显式选择 `brave` |
| SearXNG | `SEARXNG_URL` | 设置后成为未显式选择 provider 时的默认项 |

例如：

```bash
SEARXNG_URL=http://127.0.0.1:8888 \
  PYTHONPATH=src .venv/bin/python -m personal_assistant.main
```

显式选择 provider 会覆盖默认选择。provider 未配置、不可达、返回非 2xx 或不可解析响应时，工具明确报错，不静默切换到另一个 provider；SearXNG 实例需要启用 JSON 输出格式。`web_search` 只返回搜索结果，正文读取仍由 `web_fetch` 完成。
