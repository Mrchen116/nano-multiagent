# 可观测性与成本追踪 —— nano-multiagent vs Claude Code

> 对比维度：成本追踪、usage 统计、遥测、tracing、analytics

---

## 1. 成本追踪

### Claude Code —— 完整成本体系

**文件**：`src/cost-tracker.ts`, `src/bootstrap/state.ts`

**统计维度**：

```ts
// 全局统计
getTotalCostUSD()           // 总成本
getTotalInputTokens()       // 总输入 token
getTotalOutputTokens()      // 总输出 token
getTotalCacheReadInputTokens()    // cache read
getTotalCacheCreationInputTokens() // cache creation
getTotalWebSearchRequests()  // web search 请求数
getTotalAPIDuration()        // API 调用时间
getTotalToolDuration()       // 工具执行时间
getTotalLinesAdded()         // 代码增加行数
getTotalLinesRemoved()       // 代码删除行数

// 按模型统计
getModelUsage(): { [modelName: string]: ModelUsage }
ModelUsage = {
  inputTokens, outputTokens,
  cacheReadInputTokens, cacheCreationInputTokens,
  webSearchRequests, costUSD,
  contextWindow, maxOutputTokens
}
```

**成本计算**：

```ts
// src/utils/modelCost.ts
calculateUSDCost(model, usage) → number
```

- 按模型的精确单价计算
- 支持 cache read/write 折扣
- 支持 web search 计费
- 未知模型标记 `hasUnknownModelCost`

**会话成本恢复**：

```ts
restoreCostStateForSession(sessionId): boolean
saveCurrentSessionCosts(fpsMetrics?): void
```

- 恢复会话时恢复成本状态
- 成本持久化到项目配置

**UI 展示**：

```
Total cost:            $0.0234
Total duration (API):  12s
Total duration (wall): 45s
Total code changes:    42 lines added, 13 lines removed
Usage by model:
              sonnet:   1,234 input, 567 output, 0 cache read, 890 cache write ($0.0234)
```

### nano-multiagent —— 基本 TokenUsage

```python
# src/agent/core/types.py
@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

- 仅三项基本统计
- 无 cache 分项
- 无成本计算
- 无按模型统计
- 无代码变更统计
- 无会话成本恢复

**observability 层**：

```python
# src/agent/core/observability/
tracing.py    # span 追踪
logger.py     # 结构化日志
console.py    # 控制台导出
```

- 有基本的 tracing span（`span("AgentLoop.run", ...)`）
- 但无成本相关追踪

**缺陷**：
1. 无法精确追踪 API 成本
2. 无法按模型分析使用模式
3. cache 节省无法量化
4. 无代码变更统计

---

## 2. Usage 统计

### Claude Code

**SDK 返回的 usage**：

```ts
BetaUsage = {
  input_tokens: number
  output_tokens: number
  cache_read_input_tokens?: number
  cache_creation_input_tokens?: number
  server_tool_use?: {
    web_search_requests?: number
  }
}
```

**流式中获取 usage**：
- `message_start` 事件：初始 usage
- `message_delta` 事件：usage 更新

**按模型累积**：

```ts
addToTotalModelUsage(cost, usage, model) → ModelUsage
```

- 每个模型的 usage 独立累积
- 支持模型短名聚合（如所有 sonnet 变体合并）

### nano-multiagent

```python
# AgentLoop.run()
turn_usage = _accumulate_usage(turn_usage, response.usage)
```

- 仅 turn 级别累积
- 无 session 级别累积
- 无按模型累积
- 无 cache 分项

---

## 3. 遥测与分析

### Claude Code

**Analytics 系统**：`src/services/analytics/`

```ts
logEvent(eventName, metadata)  // 上报分析事件
```

事件类型：
- `tengu_advisor_tool_token_usage` —— advisor 工具使用
- 各种用户交互事件
- 工具使用事件
- 错误事件

**遥测指标**：
- OpenTelemetry 兼容的 counter/gauge
- `getCostCounter()`, `getTokenCounter()`

**FPS 追踪**：`src/utils/fpsTracker.ts`
- UI 帧率追踪
- 性能分析

### nano-multiagent

```python
# src/agent/core/observability/tracing.py
# 基本的 span 上下文管理
```

- 有 span 追踪（`span("llm.generate", ...)`）
- 无 analytics 事件上报
- 无 OpenTelemetry 集成
- 无性能追踪

**平台层**：

```python
# src/agent/platform/hooks/builtins/usage_metrics.py
```

有 usage metrics hook，但功能较简单。

---

## 4. 关键差距总结

| 能力 | Claude Code | nano-multiagent | 严重程度 |
|------|------------|-----------------|---------|
| 成本计算 | 按模型精确计算 USD | 无 | 🔴 高 |
| Cache 成本分项 | read/write 分开 | 无 | 🟡 中 |
| 按模型统计 | 独立累积 + 短名聚合 | 无 | 🟡 中 |
| Web Search 统计 | 有 | 无 | 🟢 低 |
| 代码变更统计 | lines added/removed | 无 | 🟢 低 |
| 会话成本恢复 | save/restore | 无 | 🟢 低 |
| 成本 UI 展示 | 格式化输出 | 无 | 🟡 中 |
| Analytics 事件 | 完整事件系统 | 无 | 🟡 中 |
| OpenTelemetry | Counter/Gauge | 无 | 🟡 中 |
| FPS 追踪 | 有 | 无 | 🟢 低 |
| 未知模型标记 | hasUnknownModelCost | 无 | 🟢 低 |
