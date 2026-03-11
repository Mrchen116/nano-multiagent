# 可用 LLM API 与联调说明

## 当前可用模型（已验证）
- `codexOAuth:gpt-5.2-codex`

## LLM API（本地代理）
- Base URL: `http://127.0.0.1:4000`
- 健康检查：`GET /health`
- OpenAI Chat Completions：`POST /v1/chat/completions`
- Anthropic Messages：`POST /v1/messages`

## 快速验证 curl
### 1) 健康检查
```bash
curl -sS -i http://127.0.0.1:4000/health
```

### 2) OpenAI Chat Completions（已验证可用）
```bash
curl -sS -i http://127.0.0.1:4000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"codexOAuth:gpt-5.2-codex",
    "messages":[{"role":"user","content":"reply with one word: pong"}],
    "stream":false
  }'
```

### 3) Anthropic Messages（已验证可用）
```bash
curl -sS -i http://127.0.0.1:4000/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"codexOAuth:gpt-5.2-codex",
    "max_tokens":64,
    "messages":[{"role":"user","content":"reply with one word: pong"}]
  }'
```

## Anthropic 接口测试结果（2026-02-26）
- 请求：`POST /v1/messages`
- 模型：`codexOAuth:gpt-5.2-codex`
- 返回：`HTTP/1.1 200 OK`
- 结果：`content[0].text = "pong"`

## LLM_PROXY 本地代码路径
- `/Users/czj/Repos/LLM_PROXY`
- 协议与接口说明优先看：`/Users/czj/Repos/LLM_PROXY/README.md`

## 备注
- `gpt-4.1-mini` 在当前 Codex(ChatGPT 账号)通道下会返回 400，不建议用于本地联调。
