# feat-439-M1: cache-hit-rate — Tasks

> 对齐: ../design.md（决策 1/2/3 + M1 行）

## 目标

token 气泡详情面板在「已用上下文」行下方新增一行「缓存命中 X (Y%)」，X = 本轮所有 LLM 请求命中缓存读取的输入量累计，Y% = X ÷ 本轮总输入量累计（整轮口径，spec Q1=B）。无命中显示 `0 (0%)`，不隐藏该行。`prompt_tokens` / 「已用上下文」数值零改动。

## 退出标准

- [x] `_parse_anthropic_usage` / `_parse_openai_usage`（client + mapper 两份）解析缓存字段、跨家归一（逐请求 `cache_total_input_tokens == prompt_tokens`），且 `prompt_tokens` 不变
- [x] `_accumulate_usage` 缓存两字段累加、prompt 仍取快照
- [x] gateway `main.py` token_usage_payload 显式补读/补带 cache 两字段
- [x] IM 透传链（`_parse_token_usage` → domain TokenUsage → repo encode/decode → event_types + REST）带 cache 字段并持久化往返
- [x] 前端 token-chip 渲染「缓存命中 X (Y%)」行（含 0% 空态）
- [x] 长对话「已用上下文」数值与改动前一致（回归核对）

## 测试策略

- 被测行为（来自退出标准）：
  1. 两家 provider 解析缓存字段 + 归一 + prompt_tokens 不变
  2. `_accumulate_usage` 缓存累加、prompt 快照
  3. gateway payload 带 cache
  4. IM `_parse_token_usage` 读 cache、repo encode/decode 往返、event_types/REST 带字段
  5. 前端命中行渲染 + 0% 空态
- 已有测试在：
  - `tests/unit/test_llm_anthropic_mapper.py`（扩展 mapper anthropic）；新建/扩展 `tests/unit/test_llm_openai_compat_mapper.py`（若无则就近）
  - `tests/im_service/unit/test_gateway_handler.py`（扩展 `_parse_token_usage`）
  - `tests/im_service/unit/test_message_runtime_state.py` 或 repositories 测试（encode/decode 往返）
  - `src/IM/frontend/src/features/chat/v2/components/token-chip.test.tsx`（扩展前端）
- 落层/目录/marker：tests/unit、tests/im_service/unit（无 e2e marker，纯解析/序列化单测）；前端 vitest
- 可选依赖 importorskip：无
- 一次性验收证据（收尾不删，作回归）：单测即回归；浏览器验收截图为一次性证据

前端 UI 部分：

用户路径分类：normal-ui（token 气泡详情面板新增一行，复用既有 chip 交互；非核心业务断裂点，组件测试 + 浏览器验收即可）

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default（有命中） | 组件测试：渲染「缓存命中 N (Y%)」+ 浏览器截图 |
| empty（无命中 0%） | 组件测试：渲染「缓存命中 0 (0%)」 |
| missing/nullable data（旧数据无 cache 字段） | 组件测试：默认 0、行仍显示 |
| long content（大数字千分位） | 组件测试：toLocaleString |
| loading/error/disabled/submitting/permission denied | N/A（chip 仅在完成态渲染） |
| mobile/desktop viewport | 浏览器截图（chip 详情面板宽度自适应，无独立断点逻辑） |
| dark mode | N/A（项目 chip 未做 dark 主题切换） |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 命中行渲染 + 百分比计算 | 组件测试 token-chip.test.tsx | 是 |
| 0% 空态 / 旧数据兜底 | 组件测试 | 是 |
| 真实数据贯穿到 UI | 浏览器验收截图 | 否（一次性） |

## Roadpoints

### R1 — 内核侧缓存字段贯穿（types + 两 provider + accumulate） — DONE

- 步骤: types.TokenUsage 加 `cache_read_tokens`/`cache_total_input_tokens`（默认 0）；anthropic/openai 各 client+mapper 的 `_parse_*_usage` 追加两字段（prompt_tokens 不动，OpenAI 补读 cached）；`_accumulate_usage` 两字段累加。
- 验证: provider 解析单测（含 prompt_tokens 不变 + 归一断言）、accumulate 单测；`pytest tests/unit/test_llm_anthropic_mapper.py 等`

### R2 — Gateway + IM 透传与持久化 — DONE

- 步骤: gateway `main.py` token_usage_payload 补读/补带 cache；IM `_parse_token_usage` 读 cache → domain TokenUsage 加字段 → repo encode/decode → event_types.token_usage_to_dict + REST routes/messages.py 带字段。
- 验证: gateway_handler 单测、repo 往返单测、event_types 单测；`pytest tests/im_service`

### R3 — 前端渲染 + 浏览器验收 — DONE

- 步骤: chat-types.TokenUsage 加可选 `cache_read_tokens`/`cache_total_input_tokens`；token-chip.tsx「已用上下文」下加命中行；i18n zh/en 加 key。
- 验证: token-chip.test.tsx 组件测试（命中/0%/旧数据）；真实浏览器打开 token 气泡详情看命中行截图。
