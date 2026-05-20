# bugfix-369: auto_mode_gate 分类器继承主 agent 的 thinking,64-token 快路被推理吃空 → fail-closed → 整轮卡住

## Relations

- Related: bugfix-366（引入此缺陷：给主 agent 开 thinking 时挂在了模型元数据上）
- Related: feat-333（auto-mode classifier / 权限 gate 首版）
- Related: bugfix-367（同一 gate 区域的 permission 卡 UI/协议缺陷，独立问题）

## 原始报告

> http://127.0.0.1:8011/chat/a43e2465a3174e96b91387c431069208 怎么停下来了，怎么他拿到工具结果之后停下来了？

澄清/纠正（用户原话）：

> 上游 LLM proxy 对 K2.6 默认开 thinking: {type: adaptive}。不是上游开的呀，是 nano 这个项目传过去的呀。

> 这应该对应着最近的某个需求。加进去的

> 之前是主agent没有think，然后改的

## 现象 / 复现

PA 聊天会话里，agent 第一轮正常返回一个 `bash` 工具调用后，整轮就"停下来"了——用户观察到 agent 拿到（或本该执行）工具调用后不再推进，既没有继续执行工具、也没有后续文字输出。

复现会话：`http://127.0.0.1:8011/chat/a43e2465a3174e96b91387c431069208`

对应的 LLM proxy 日志（`logs/session/2026-05-20_10-35-22_254_sess_f96f246cd3aabfa6/`）显示三次往返：

1. **主循环**：LLM 正常返回 `bash: pwd && ls -la`，`finish_reason=tool_calls`。正常。
2. **门禁 stage-1 分类**（`auto_mode_gate._classify_action` 快路，`max_tokens=64`、`temperature=0`、`stop=["</block>"]`，系统提示要求"整段回复必须以 `<block>` 开头"）：实际返回 **content 为空、`finish_reason=length`、只有 `reasoning_content`**。请求体里带着 `thinking: {type: adaptive}`，user prompt 为空 transcript。
3. 善后空跑（0 token）。

stage-1 拿到空 content → `parse_xml_block` 返回 `None` → fail-closed → ask。在这个 attended 聊天里这次 ask 没能正常推进（叠加 bugfix-367 的 permission 卡缺陷），整轮表现成"停下来了"。

**触发条件**：使用带 thinking 的模型（如 `kimiCoding:K2.6`）时，任何会落到 classifier 的工具调用（即非 SAFE_TOOL_ALLOWLIST、tool.check_permissions 走 passthrough 的工具，典型是 `bash`）都会命中。

## 根因

**根因（错位的开关层级）**

bugfix-366 给主 agent 开 thinking 时，把开关安在了**模型元数据**上：

- `src/agent/core/llm/model_registry.py:45,55` 给 `kimiCoding:K2.6` / `volcanoArk:...` 的 `extra_request_body` 设了 `{"thinking": {"type": "adaptive"}}`。
- `src/agent/platform/llm/providers/anthropic/client.py:56-60` 在 `generate()` 里对**所有**走该模型的请求无差别 merge 这个 `extra_request_body`，不区分调用方。

后果：`auto_mode_gate._classify_action`（`auto_mode_gate.py:438`）的 stage-1 快路调用 `ctx.call_model` 时没传 model override，复用主会话模型 `K2.6`（`runtime.py:986` `call.model or self._llm_config.model`），于是连 thinking 也一起继承。stage-1 的设计前提是"无 thinking 的小模型 64 token 内立刻吐 `<block>no/yes`"（Claude Code yoloClassifier 的像素级复刻），而推理把 64 token 预算全花在 `reasoning_content` 上，`finish_reason=length` 截断时还没轮到吐 `<block>`，可见 content 为空 → `parse_xml_block` → `None` → fail-closed → ask（`auto_mode_gate.py:473`）。

链路：`model_registry` 模型级 thinking → `client.generate` 无差别 merge → 门禁 stage-1 继承 thinking → 64 token 被推理吃空 → 空 `<block>` → fail-closed ask → 整轮卡住。

**Before bugfix-366**（主 agent 无 thinking，门禁快路正常）

```
              ┌─────────────────────────────────────┐
              │  model_registry: K2.6                │
              │  extra_request_body = None           │  ← 没 thinking
              └─────────────────────────────────────┘
                              │ client.generate() merge
              ┌───────────────┴───────────────┐
              ▼                                ▼
   ┌──────────────────┐            ┌──────────────────────┐
   │ 主 agent 循环     │            │ 门禁 stage-1 分类器   │
   │ call K2.6        │            │ call K2.6, 64 tok    │
   │ → 无 thinking     │            │ → 无 thinking         │
   │ (能跑,但不会推理) │            │ → 立刻吐 <block>no ✓  │
   └──────────────────┘            └──────────────────────┘
```

**After bugfix-366**（thinking 加在模型层 → 漏给门禁，本 bug）

```
              ┌─────────────────────────────────────┐
              │  model_registry: K2.6                │
              │  extra_request_body =                │  ← 开关安在这里
              │    {thinking: adaptive}              │     (对该模型所有调用生效)
              └─────────────────────────────────────┘
                              │ client.generate() 无差别 merge
              ┌───────────────┴───────────────┐
              ▼                                ▼
   ┌──────────────────┐            ┌──────────────────────────┐
   │ 主 agent 循环     │            │ 门禁 stage-1 分类器        │
   │ call K2.6        │            │ call K2.6, 64 tok         │
   │ → thinking on ✓  │            │ → thinking on ✗(误)       │
   │ (想要的效果)      │            │ reasoning 吃光 64 tok      │
   └──────────────────┘            │ finish=length, content="" │
                                   │ parse <block> → None       │
                                   │ → fail-closed → ask        │
                                   │ → 整轮卡住 / "停下来"        │
                                   └──────────────────────────┘
```

**目标状态**（开关回到调用方这一层；具体方案归 design/worker）

```
              ┌─────────────────────────────────────┐
              │  model_registry: K2.6                │
              │  extra_request_body =                │
              │    {thinking: adaptive}  (默认)       │
              └─────────────────────────────────────┘
                              │ merge,但 call 端 extra_body 可覆盖
              ┌───────────────┴────────────────┐
              ▼                                 ▼
   ┌──────────────────┐            ┌────────────────────────────┐
   │ 主 agent 循环     │            │ 门禁 stage-1 分类器          │
   │ 不传 extra_body  │            │ 显式关 thinking              │
   │ → 继承默认        │            │ → thinking off ✓            │
   │ → thinking on ✓  │            │ → 立刻吐 <block> → 快路恢复 ✓ │
   └──────────────────┘            └────────────────────────────┘
```

> `client.py:58-59` 已有"call 端 `extra_body` 覆盖 metadata"的逻辑，方向上支持让门禁那条调用显式压掉 thinking；最终修法由 worker 在"修复"段落定。

**为什么这种错能进来**

thinking 的正确语义是"**谁在调用**决定要不要推理"——主 agent 循环要 reasoning，门禁分类器这条旁路调用明确不要（它要的是确定性的快判定）。bugfix-366 图省事把开关挂在了"**用哪个模型**"这一层，于是跨调用方的语义被抹平：门禁借同一个模型做安全判定，被连坐。

feat-333 实现 gate 时复刻了 CC"无 thinking 64-token 快路"的假设，但当时主 agent 也没开 thinking，两边一致看不出问题；bugfix-366 单独给主 agent 开 thinking 后，gate 这条共享同模型的旁路才暴露。没有测试覆盖"classifier 跑在带 thinking 的模型上"这条路径。

## 修复

<!-- worker 回填 -->

## 验证

<!-- worker 回填 -->
