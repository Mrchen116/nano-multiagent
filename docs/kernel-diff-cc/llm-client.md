# LLM 客户端 —— nano-multiagent vs Claude Code

> 对比维度：provider 支持、流式 API、thinking mode、retry 策略、非流式降级、多 provider

---

## 1. Provider 支持

### Claude Code —— 4 个 Provider

| Provider | SDK | 说明 |
|----------|-----|------|
| Anthropic | `@anthropic-ai/sdk` | 默认，`api.anthropic.com` |
| AWS Bedrock | `@anthropic-ai/bedrock-sdk` | 企业部署 |
| Google Vertex | `@anthropic-ai/vertex-sdk` | GCP 部署 |
| Azure | 类似 Bedrock 包装 | Azure 部署 |

Provider 选择逻辑：`src/utils/model/providers.ts` 的 `getAPIProvider()`

### nano-multiagent —— 2 个 Provider

| Provider | 实现 | 说明 |
|----------|------|------|
| Anthropic | `httpx.Client` + 原生 HTTP | `src/agent/platform/llm/providers/anthropic/client.py` |
| OpenAI-compatible | `httpx.Client` + 原生 HTTP | `src/agent/platform/llm/providers/openai_compat/client.py` |

- 不使用官方 SDK，直接用 `httpx` 发送 HTTP 请求
- 通过 `LLMTranslator` + `Mapper` 做请求/响应转换

**缺陷**：
1. 不支持 Bedrock/Vertex/Azure 等企业部署路径
2. 不使用官方 SDK，可能错过 SDK 层面的新功能（如新的 beta API）
3. 自行维护请求/响应映射，维护成本高

---

## 2. 流式 API

### Claude Code

使用 `.create() + stream: true` 而非 `.stream()`：

```ts
// src/services/api/claude.ts:1823
const result = await anthropic.beta.messages
  .create(
    { ...params, stream: true },
    { signal, ...(clientRequestId && { headers: { ... } }) },
  )
  .withResponse()
```

**设计原因**：避免 `BetaMessageStream` 的 O(n²) partial JSON 解析开销。

流式事件处理：
```ts
for await (const part of stream) {
  switch (part.type) {
    case 'message_start':    // 记录 request_id、usage
    case 'content_block_start':  // 新的内容块开始
    case 'content_block_delta':  // 增量内容 → yield stream_event
    case 'content_block_stop':   // 内容块完成 → yield AssistantMessage
    case 'message_delta':    // stop_reason、usage 更新
    case 'message_stop':     // 整条消息完成
  }
}
```

### nano-multiagent

```python
# src/agent/platform/llm/providers/anthropic/client.py:45-49
def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
    if request.stream:
        raise ModelError("streaming generation is not implemented yet", retryable=False)
    # 非流式请求
    response = self._http_client.request(...)
    return self._translator.from_provider_response(payload)
```

- 完全不支持流式
- `LLMGenerateRequest.stream` 字段存在但会报错

---

## 3. Thinking Mode

### Claude Code

支持两种 thinking 配置：

```ts
// src/services/api/claude.ts:1559
if (hasThinking && modelSupportsThinking(options.model)) {
  if (modelSupportsAdaptiveThinking(options.model)) {
    thinking = { type: 'adaptive' }
  } else {
    thinking = { type: 'enabled', budget_tokens: thinkingBudget }
  }
}
```

- `adaptive`：模型自适应决定是否思考
- `enabled`：启用思考，可配置 `budget_tokens`
- 通过 beta headers 传递
- thinking 内容块不添加 `cache_control`

**CLI 参数**：`--effort <level>`（low/medium/high/max）

### nano-multiagent

- `LLMGenerateRequest` 无 thinking 相关字段
- `AnthropicMapper` 不处理 thinking
- 无 effort 配置

**缺陷**：无法利用 Claude 的 extended thinking 能力，复杂推理任务质量受限。

---

## 4. Retry 策略

### Claude Code —— withRetry

```ts
// src/services/api/claude.ts:1779
withRetry(
  () => getAnthropicClient({ maxRetries: 0, ... }),
  async (anthropic, attempt, context) => { ... },
  { model, fallbackModel, thinkingConfig, signal, querySource }
)
```

| 错误码 | 策略 |
|--------|------|
| 429 Rate Limit | 等待 `Retry-After` 后重试 |
| 529 Overloaded | 切换到 `fallbackModel`，throw `FallbackTriggeredError` |
| 500 Server Error | 指数退避重试 |
| 408 Timeout | 重试 |
| 其他 | 不重试，直接抛出 |

最大重试次数根据模型和错误类型动态计算。

### nano-multiagent —— 基本无 Retry

```python
# src/agent/core/llm/retry.py
```

`retry.py` 文件存在，但内容需要确认。从 `AnthropicClient.generate()` 的代码看：

```python
try:
    response = self._http_client.request(...)
    response.raise_for_status()
except httpx.HTTPStatusError as exc:
    raise ModelError("anthropic request failed", details={...})
except httpx.HTTPError as exc:
    raise ModelError("anthropic transport error", details={...})
```

- 无自动重试
- 无 fallback model 切换
- 无指数退避
- 仅将 HTTP 错误包装为 `ModelError`

**缺陷**：
1. 429 时直接失败，用户体验差
2. 529 时无降级，服务过载时完全不可用
3. 瞬态网络错误无法恢复

---

## 5. 非流式降级

### Claude Code

当流式请求中途失败时：

```
流式失败（部分响应已收到）:
  ├── 已接收的内容 → yield 给上层
  ├── 剩余部分 → 降级为非流式请求（anthropic.beta.messages.create）
  └── 非流式结果 → 转换格式 yield
```

### nano-multiagent

N/A（本来就不支持流式）

---

## 6. API 请求参数构建

### Claude Code

`paramsFromContext()` 动态构建（`src/services/api/claude.ts:1539-1730`）：

```ts
return {
  model: normalizeModelStringForAPI(options.model),
  messages: addCacheBreakpoints(messagesForAPI, ...),
  system,                           // 系统提示块
  tools: allTools,                  // 工具 schema
  tool_choice: options.toolChoice,
  max_tokens: maxOutputTokens,
  thinking,                         // thinking 配置
  temperature,                      // 温度
  betas: betasParams,              // beta headers
  metadata: getAPIMetadata(),
  speed,                            // 快速模式
  ...extraBodyParams,
}
```

**Beta Headers**：
- 基础 betas
- advisor beta
- tool search beta
- cache scope beta
- effort / task budget betas

### nano-multiagent

`AnthropicMapper.to_provider_request()` 构建：

```python
# 请求体仅包含基本字段：
{
    "model": request.model,
    "messages": [...],
    "system": system_prompt,
    "tools": tools,
    "max_tokens": max_tokens,
    "temperature": temperature,
    "stream": stream,
}
```

- 无 beta headers
- 无 metadata
- 无 speed
- 无 tool_choice
- 无 thinking

---

## 7. 消息归一化

### Claude Code

```ts
// userMessageToMessageParam()
// assistantMessageToMessageParam()
// normalizeMessagesForAPI()
```

- 跳过 system/attachment/progress 等内部消息类型
- 支持 image content blocks
- thinking/redacted_thinking 块特殊处理
- 自动添加 cache breakpoints

### nano-multiagent

```python
# AnthropicMapper
```

- 基本的消息格式转换
- `LLMMessage.content: str | list[dict[str, Any]]` 支持多模态
- 但无特殊内容块处理（thinking, redacted_thinking 等）

---

## 8. 关键差距总结

| 能力 | Claude Code | nano-multiagent | 严重程度 |
|------|------------|-----------------|---------|
| Provider 数量 | 4 (Anthropic/Bedrock/Vertex/Azure) | 2 (Anthropic/OpenAI-compat) | 🟡 中 |
| 流式 API | 完整，6 种事件类型 | 完全不支持 | 🔴 高 |
| Thinking Mode | adaptive/enabled + budget | 无 | 🔴 高 |
| Retry 策略 | 429/529/500/408 自动处理 | 基本无重试 | 🔴 高 |
| Fallback Model | 529 自动切换 | 无 | 🟡 中 |
| 非流式降级 | 流式失败降级 | N/A | 🟢 低 |
| Beta Headers | 动态组装多种 beta | 无 | 🟡 中 |
| Cache Breakpoints | 自动添加 | 无 | 🔴 高 |
| Temperature | 支持 | 支持 | 🟢 低 |
| Speed/Fast Mode | 支持 | 无 | 🟢 低 |
| Metadata | 支持 | 基本支持 | 🟢 低 |
| Tool Choice | 支持 | 无 | 🟢 低 |
| Image Blocks | 支持 | 基本支持 | 🟡 中 |
