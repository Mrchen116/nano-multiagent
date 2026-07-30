# LLM Integration

本文记录 nano-multiagent 开发和真实链路验收使用的本地 LLM 代理入口、协议、交互日志和最近验证快照。Gateway 的 `llm:` 配置结构见 [`../operations/gateway.md`](../operations/gateway.md)。

## 调研与诊断入口

- LLM_PROXY 代码：`/Users/czj/Repos/LLM_PROXY`
- 协议与启动说明：`/Users/czj/Repos/LLM_PROXY/README.md`
- 按 session 聚合的交互日志：`/Users/czj/Repos/LLM_PROXY/logs/session/*_<session_id>/`
- 按协议保存的原始捕获：`/Users/czj/Repos/LLM_PROXY/logs/raw/<protocol>/`

nano 的 provider translator 会把 kernel session id 放入 `X-Session-Id`。先从触发请求的一侧取得
session id：Coding CLI 可用 `/session`，自动化测试应从 fixture/结果中记录；其他产品路径如果没有直接
暴露 id，就用发生时间、模型和消息中的唯一标记缩小日志目录，再从目录后缀确认 id。

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

session 目录中的 `*-req-*` 是代理收到的请求，`*-downstream-res-*` 是返回调用方的响应，
`*-non-stream-res-*` 是聚合后的非流式结果。需要排查协议转换或 session 未被识别时，再按时间和协议查看
`logs/raw/`；Session Inspector 也从 `logs/session/` 构建 timeline。

这些日志证明 provider 实际收到和返回了什么，应用是否正确消费、持久化并送达用户仍需结合 Gateway/IM
runtime evidence。原始内容可能含 prompt、工具参数和第三方数据，不提交进本仓；unit 中只记录 session id、
时间范围、要证明的 claim 和必要的脱敏摘要。日志会按 LLM_PROXY 的 retention 配置清理，长期回归应进入测试。

## 本地代理接口
- Base URL: `http://127.0.0.1:4000`
- 健康检查：`GET /health`
- OpenAI Chat Completions：`POST /v1/chat/completions`
- Anthropic Messages：`POST /v1/messages`

## 快速验证

### 1) 健康检查

```bash
curl -sS -i http://127.0.0.1:4000/health
```

下面两条模型请求使用最近一次留档的 model id。先通过健康检查，并按 LLM_PROXY 当前配置替换 model id，再把请求结果和对应 `<session_id>` 日志一起作为本次联调证据。

### 2) OpenAI Chat Completions

```bash
nano_smoke_session_id="nano-smoke-openai-$(date +%Y%m%d-%H%M%S)"
curl -sS -i http://127.0.0.1:4000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H "X-Session-Id: ${nano_smoke_session_id}" \
  -d '{
    "model":"codexOAuth:gpt-5.2-codex",
    "messages":[{"role":"user","content":"reply with one word: pong"}],
    "stream":false
  }'
```

### 3) Anthropic Messages

```bash
nano_smoke_session_id="nano-smoke-anthropic-$(date +%Y%m%d-%H%M%S)"
curl -sS -i http://127.0.0.1:4000/v1/messages \
  -H 'Content-Type: application/json' \
  -H "X-Session-Id: ${nano_smoke_session_id}" \
  -d '{
    "model":"codexOAuth:gpt-5.2-codex",
    "max_tokens":64,
    "messages":[{"role":"user","content":"reply with one word: pong"}]
  }'
```

## 最近验证快照

2026-02-26 的留档结果：

- 请求：`POST /v1/messages`
- 模型：`codexOAuth:gpt-5.2-codex`
- 返回：`HTTP/1.1 200 OK`
- 结果：`content[0].text = "pong"`

这是一条带日期的运行证据，不保证该 model id 在后续代理配置中持续可用。若 `codexOAuth:gpt-5.2-codex` 不可用，历史上使用过 `moonshot:kimi-k2.5`；实际联调仍以当前代理配置、健康检查、请求响应和 session 日志为准。
