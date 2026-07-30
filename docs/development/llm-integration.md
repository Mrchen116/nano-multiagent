# LLM Integration

本文记录 nano-multiagent 开发和真实链路验收使用的本地 LLM 代理入口、当前配置、协议、交互日志和验证方法。Gateway 的 `llm:` 配置结构见 [`../operations/gateway.md`](../operations/gateway.md)。

## 调研与诊断入口

- LLM_PROXY 代码：`/Users/czj/Repos/LLM_PROXY`
- 协议与启动说明：`/Users/czj/Repos/LLM_PROXY/README.md`
- 按 session 聚合的交互日志：`/Users/czj/Repos/LLM_PROXY/logs/session/*_<session_id>/`
- 按协议保存的原始捕获：`/Users/czj/Repos/LLM_PROXY/logs/raw/<protocol>/`

nano 的 provider translator 会把 kernel session id 放入 `X-Session-Id`。先从触发请求的一侧取得 session id：Coding CLI 可用 `/session`，自动化测试应从 fixture/结果中记录；其他产品路径如果没有直接暴露 id，就用发生时间、模型和消息中的唯一标记缩小日志目录，再从目录后缀确认 id。

已知 session id 时直接定位：

```bash
nano_session_id="sess_..."
find /Users/czj/Repos/LLM_PROXY/logs/session \
  -mindepth 1 -maxdepth 1 -type d -name "*_${nano_session_id}"
```

只知道发生时间时，先查看最近写入的 session，再打开候选请求核对模型和脱敏后的消息标记：

```bash
ls -td /Users/czj/Repos/LLM_PROXY/logs/session/* | head
```

session 目录中的 `*-req-*` 是代理收到的请求，`*-downstream-res-*` 是返回调用方的响应，`*-non-stream-res-*` 是聚合后的非流式结果。需要排查协议转换或 session 未被识别时，再按时间和协议查看 `logs/raw/`；Session Inspector 也从 `logs/session/` 构建 timeline。

这些日志证明 provider 实际收到和返回了什么，应用是否正确消费、持久化并送达用户仍需结合 Gateway/IM runtime evidence。原始内容可能含 prompt、工具参数和第三方数据，不提交进本仓；unit 中只记录 session id、时间范围、要证明的 claim 和必要的脱敏摘要。日志会按 LLM_PROXY 的 retention 配置清理，长期回归应进入测试。

## 本地代理接口
- Base URL: `http://127.0.0.1:4000`
- 健康检查：`GET /health`
- OpenAI Chat Completions：`POST /v1/chat/completions`
- Anthropic Messages：`POST /v1/messages`

## 当前配置与模型

- LLM_PROXY 默认配置文件：`/Users/czj/Repos/LLM_PROXY/upstreams.json`
- 配置结构说明：`/Users/czj/Repos/LLM_PROXY/README-zh.md` 的“上游配置”
- 实际进程设置了 `UPSTREAM_CONFIG_PATH` 时，以该路径为准。

`defaultProfile` 指定默认 profile，`profiles.<name>.defaults.model` 记录该 profile 的默认模型，`profiles.<name>.capabilities.ingress` 记录它支持的入口协议。请求中的模型 ID 使用 `profile:model`；`codex_oauth` profile 还支持可选的 `@effort` 后缀。

用下面的命令只查看非敏感的模型路由字段：

```bash
llm_proxy_config="${UPSTREAM_CONFIG_PATH:-/Users/czj/Repos/LLM_PROXY/upstreams.json}"
jq -r '
  .defaultProfile as $default
  | .profiles
  | to_entries[]
  | [
      .key,
      (.value.provider // ""),
      (.value.defaults.model // ""),
      ((.value.capabilities.ingress // []) | join(",")),
      (if .key == $default then "default" else "" end)
    ]
  | @tsv
' "$llm_proxy_config"
```

输出依次是 profile、provider、默认模型、支持的入口协议和是否为默认 profile。配置文件可能包含鉴权信息，不要把完整文件复制进本仓、change evidence 或聊天记录。

## 快速验证

### 1) 健康检查

```bash
curl -sS -i http://127.0.0.1:4000/health
```

先从当前配置中选择支持目标入口协议的 profile 和模型，再设置：

```bash
nano_smoke_model="<profile>:<model>"
```

### 2) OpenAI Chat Completions

```bash
nano_smoke_session_id="nano-smoke-openai-$(date +%Y%m%d-%H%M%S)"
curl -sS -i http://127.0.0.1:4000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H "X-Session-Id: ${nano_smoke_session_id}" \
  -d "$(jq -nc --arg model "$nano_smoke_model" \
    '{model:$model,messages:[{role:"user",content:"reply with one word: pong"}],stream:false}')"
```

### 3) Anthropic Messages

```bash
nano_smoke_session_id="nano-smoke-anthropic-$(date +%Y%m%d-%H%M%S)"
curl -sS -i http://127.0.0.1:4000/v1/messages \
  -H 'Content-Type: application/json' \
  -H "X-Session-Id: ${nano_smoke_session_id}" \
  -d "$(jq -nc --arg model "$nano_smoke_model" \
    '{model:$model,max_tokens:64,messages:[{role:"user",content:"reply with one word: pong"}]}')"
```
