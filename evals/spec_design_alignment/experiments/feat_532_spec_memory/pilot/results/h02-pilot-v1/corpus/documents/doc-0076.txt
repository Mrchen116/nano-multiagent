# bugfix-366: Anthropic 输出限制、thinking 支持、Gateway config override token 丢失

## Relations

- Related: bugfix-346-gateway-token-auto-refresh（token getter / auto-refresh 机制）

## 现象

### 1. Agent 回复被截断

群聊/私聊中 agent 的回复经常"说到一半就断了"。例如一条本该完整的分析，输出到 ~500 字（中文）左右突然结束，没有 finish_reason 标记，内容明显不完整。

### 2. Gateway 重启后无法启动（token 过期）

Gateway 进程 kill 后重启，无论 `--foreground` 还是后台模式，均报：

```
Gateway failed to start
  node demo-node did not appear in IM bootstrap
  → Verify the IM node API is reachable at http://127.0.0.1:8011/im/v1/nodes and rerun gateway.
```

手动 `curl POST /im/v1/auth/login` 获取新 token 并写回 `config.yaml` 后才能启动。

## 根因

### 根因 A: Anthropic mapper 默认 max_tokens = 1024

`src/agent/platform/llm/providers/anthropic/mapper.py` 中：

```python
_DEFAULT_MAX_TOKENS = 1024
```

当 `LLMGenerateRequest.max_tokens` 为 None（agent loop 和 hook 调用均不传）时，fallback 到 1024。中文场景下 1 token ≈ 1.5-2 字，1024 tokens 仅能输出 ~500-700 汉字，任何稍长的回复（代码块、分析推理）都会被硬性截断。

对比 openai_compat mapper：max_tokens 为 None 时**不传该字段**，由上游 API 自行决定上限，不会人为截断。

### 根因 B: 无 thinking 支持

Anthropic Claude 3.7+ 的 extended thinking 需要在请求 payload 中传 `"thinking": {"type": "adaptive"}`，但代码里完全没这个字段。同时 SSE 响应中的 `thinking` / `redacted_thinking` / `thinking_delta` 内容块也未处理，会导致产生空消息污染消息流。

### 根因 C: `--im-service-url` 覆盖时丢失认证凭据

`src/personal_assistant/main.py` `_load_runtime_config`：

```python
return replace(config, im_service=IMServiceConfig(url=override_url, token=override_token))
```

当 operator 用 `--im-service-url` 显式指定 IM 地址时，只保留 `url` 和 `token`，**丢失了 `username`、`password`、`refresh_token`**。

这导致 `_make_token_getter` 构建的 token getter：
1. `refresh_token` 为 None → refresh 路径不走
2. `username` / `password` 为 None → login fallback 不走
3. 只能返回 config 中那个可能已经过期的静态 `token`

Gateway bootstrap 调用 `/im/v1/nodes` 时带过期 token → 401 → `_get_owner_id` 抛异常 → `_wait_for_owner` 5 秒超时 → `GatewayStartupError`。

**为什么之前能跑**：用户之前启动的 Gateway（PID 97955）不带 `--im-service-url`，config 文件完整，token 在进程生命周期内未过期。kill 后用相同命令重启时 token 已过期，触发了这个 bug。

## 修复

### 1. 提高 Anthropic 默认 max_tokens

`src/agent/platform/llm/providers/anthropic/mapper.py`:

```python
_DEFAULT_MAX_TOKENS = 1024 * 32  # 32768
```

现代 LLM（豆包、Kimi、Claude 等）的输出能力远超 1024，不需要代码层人为设限。模型不会强行填满到上限，只是允许更长的输出。

### 2. 增加 thinking 支持

**通用接口层** (`src/agent/core/llm/interfaces.py`):
- `LLMGenerateRequest` 新增 `extra_body: Mapping[str, Any] | None = None`，用于透传 provider-specific 参数。

**模型注册表** (`src/agent/core/llm/model_registry.py`):
- `ModelMetadata` 新增 `extra_request_body: dict[str, Any] | None = None`
- 两个 anthropic 模型（`kimiCoding:K2.6`、`volcanoArk:doubao-seed-2-0-code-preview-260215`）默认配置 `extra_request_body={"thinking": {"type": "adaptive"}}`
- `resolve_model_metadata` unknown model fallback 也继承 `extra_request_body`

**Mapper 层**:
- `anthropic/mapper.py`: 构造 payload 后合并 `request.extra_body`
- `openai_compat/mapper.py`: 同样支持 `extra_body` 合并

**Client 层** (`src/agent/platform/llm/providers/anthropic/client.py`):
- `generate()` 方法根据 `resolve_model_metadata` 获取模型配置，把 `extra_request_body` 自动合并进请求（operator 无需在调用层手动传）
- SSE 解析中过滤 `thinking` / `redacted_thinking` 内容块，避免 yield 空消息污染消息流
- `_apply_anthropic_delta` 新增 `thinking_delta` 类型处理

### 3. 修复 Gateway config override token 丢失

`src/personal_assistant/main.py` `_load_runtime_config`:

```python
old_im = config.im_service
if old_im is None:
    return replace(config, im_service=IMServiceConfig(url=override_url))
return replace(
    config,
    im_service=IMServiceConfig(
        url=override_url,
        token=old_im.token,
        refresh_token=old_im.refresh_token,
        username=old_im.username,
        password=old_im.password,
    ),
)
```

覆盖 URL 时完整保留所有认证字段，让 `_token_getter` 的 refresh → login fallback 链能正常工作。

## 验证

- Gateway 重启测试：`PYTHONPATH=src python -m personal_assistant.main --config ~/.nano-assistant/config.yaml --im-service-url http://127.0.0.1:8011 --foreground`
  - 启动成功，health endpoint `{"healthy":true}`
  - IM 连接 ESTABLISHED，agent 状态正常（非灰色）
  - bootstrap 阶段 `_token_getter` 能通过 username/password login 获取新 token
- 截断问题：需在生产会话中观察长回复是否完整输出（无法单测验证，依赖上游 API 行为）
- thinking：需在生产会话中验证 API 响应格式（依赖上游是否实际支持 thinking 字段）
