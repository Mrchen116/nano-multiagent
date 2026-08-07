# 启动与首次聊天

按“先 IM，后 Gateway，再绑定并聊天”的顺序启动。

## 1. 准备环境和 Gateway 配置

项目要求 Python 3.11+。默认 Gateway 配置位于 `~/.nanoassistant/config.yaml`。最小结构如下：

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

llm:
  default_model: <model-id>
  providers:
    - name: anthropic
      base_url: <anthropic-compatible-base-url>
      models:
        - name: <model-id>
```

关键约束：

- `llm` 必填，`llm.default_model` 必须登记在某个 `llm.providers[].models[]` 中。
- provider 使用 `anthropic` 或 `openai_compat`，并与上游协议匹配。
- 配置 `im_service` 时启用内置 `web_relay`。
- 省略 `agents[].workspace_root` 时，默认使用 `~/.nanoassistant/workspaces/<agent_id>/` 并自动创建。
- 配置、密钥、状态文件和日志属于本机运行数据，不应作为普通项目文件分享。

## 2. 启动 IM

在项目 checkout 中运行：

```bash
PYTHONPATH=src python -m uvicorn IM.app:app --host 0.0.0.0 --port 8011
```

访问：

- `http://127.0.0.1:8011/`
- `http://127.0.0.1:8011/chat`

先用 `http://127.0.0.1:8011/openapi.json` 判断 HTTP 是否可达。若 OpenAPI 可达但页面不存在，检查当前安装或 checkout 是否包含已经构建的 Web IM 静态资源。

## 3. 启动 Gateway

```bash
PYTHONPATH=src python -m personal_assistant.main
```

常用生命周期命令：

```bash
PYTHONPATH=src python -m personal_assistant.main stop
PYTHONPATH=src python -m personal_assistant.main restart
PYTHONPATH=src python -m personal_assistant.main --foreground
```

使用非默认配置时，start、stop、restart 都传同一 `--config /absolute/path/to/config.yaml`。`--im-service-url` 只覆盖本次连接的 IM 地址；`--auto-bind` 用于自动化，日常使用通过浏览器确认绑定。

`Gateway started (pid=...)` 只证明后台 child 已创建有效运行态且当时存活，不证明 IM、Agent 或渠道已经就绪。继续检查 `gateway.log` 和 Web IM 节点状态。

## 4. 绑定并聊天

- 首次连接未绑定节点时，按 `gateway.log` 中的 `ACTION` / `NEXT` 打开绑定页并确认。
- 节点已绑定且 online 后，打开 `/chat` 发送消息。
- 输入区显示 `Chat unavailable` 时，按卡片提示先完成绑定或恢复 Gateway online。
- 发送瞬间节点失效时，Web IM 保留草稿并显示失败，不要求重新输入。
