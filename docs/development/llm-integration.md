# LLM Integration

本文记录 nano-multiagent 开发和真实链路验收使用的本地 LLM 代理入口、协议、交互日志和最近验证快照。Gateway 的 `llm:` 配置结构见 [`../operations/gateway.md`](../operations/gateway.md)。

## 调研与诊断入口

- LLM_PROXY 代码：`/Users/czj/Repos/LLM_PROXY`
- 协议与启动说明：`/Users/czj/Repos/LLM_PROXY/README.md`
- 每次 LLM 交互日志：`/Users/czj/Repos/LLM_PROXY/logs/<session_id>/`

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
curl -sS -i http://127.0.0.1:4000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"codexOAuth:gpt-5.2-codex",
    "messages":[{"role":"user","content":"reply with one word: pong"}],
    "stream":false
  }'
```

### 3) Anthropic Messages

```bash
curl -sS -i http://127.0.0.1:4000/v1/messages \
  -H 'Content-Type: application/json' \
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
