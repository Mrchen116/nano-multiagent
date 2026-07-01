# 参考项目 subagent 可观测性调研

供 `change-design-author` 参考。只记产品行为和用户感知，不记实现细节。

---

## 1. openclaw

### IM 端

| 能力 | 用户看到什么 |
|---|---|
| 子 agent 启动 | 父 agent 的 spawn 工具调用卡片，带子 agent session key |
| 子 agent 运行中 | **看不到**。子 agent 活动在独立 session，父对话无感知 |
| 子 agent 完成 | 推一条完成消息到 IM："Background task done: {title} ({run}). {summary}" |
| 主动查状态 | `/subagents list` 命令：活跃子 agent 列表 + 状态 + 耗时 |
| 控制子 agent | `/subagents kill <id>`、`steer <id>`、`send <id>` |
| 打字指示器 | agent 运行期间每 6 秒向 IM channel 发 typing indicator |
| 通知策略 | 可配置：`done_only`（只推完成）/ `state_changes`（状态变更都推）/ `silent` |

**关键设计**：push-based announce，明确禁止父 agent 轮询子 session。子 agent 完成后结果作为结构化消息注入父 session，带 `<<<BEGIN_UNTRUSTED_CHILD_RESULT>>>` 分隔符防注入。

### Web 端

| 能力 | 用户看到什么 |
|---|---|
| 子 agent 列表 | 侧边栏 session 下拉菜单里，带 "Subagent:" 前缀 |
| 查看子 agent 活动 | **手动切到子 agent session**，看到完整的工具调用、thinking、消息时间线 |
| 父对话里的子 agent | 只有一个 spawn 工具调用卡片，无内部活动 |
| 实时流 | 有，但 session-scoped——只对当前查看的 session 生效 |
| Gateway 数据 | 已发 `subagentRunState`、`childSessions`、`hasActiveSubagentRun`、`runtimeMs` 等字段，但 **UI 未渲染** |

**结论**：Web 端没有 inline 子 agent 活动展示。用户必须切 session 才能看到。Gateway 数据丰富但 UI 没用上。

---

## 2. hermes-agent

### IM 端

| 能力 | 用户看到什么 |
|---|---|
| 子 agent 启动 | 父 agent 的 delegate 工具调用，带 goal 描述 |
| 子 agent 运行中 | **工具名批量推送**：每 5 个工具名拼成一条消息（如 "bash, edit, read, web_search, grep"），原地编辑更新。不是逐工具推送 |
| thinking | 每条 thinking 单独推，立刻 relay，不进 batch |
| 文字输出 | `subagent.text` 事件单独推，不进 batch |
| 子 agent 完成 | 剩余不足 5 个工具名 flush 出来 + 完成通知 |
| 活跃子 agent 注册表 | `_active_subagents` 记录 subagent_id、parent_id、depth、goal、model、started_at、tool_count、status |
| 打字指示器 | 平台适配器的 `send_typing()`，每 6 秒刷新 |
| Stale 检测 | 30 秒 heartbeat 触摸，450 秒 idle 阈值，1200 秒 in-tool 阈值，超时通知父 agent |

**关键设计**：
- 工具名 batch=5，减少 IM 刷屏
- CLI 终端里是逐工具实时打印（`├─ 🔧 bash "git diff"`），IM 里才做批量
- thinking 和文字输出不 batch，直接推
- 子 agent 完成后，通知包含完整上下文（原始 goal、耗时、token、cost、文件读写统计、output_tail）

### 平台适配

- 消息编辑：Telegram/Discord/Slack 支持，WhatsApp 不支持（降级为新消息）
- 编辑节流：最小 1.5 秒间隔，防止平台限流
- 洪水控制：连续 3 次触发限流后降级为新消息

---

## 3. clowder-ai

### 多 agent 模型

- "cat" = 一个独立 AI agent（Claude、Codex、Gemini 等），有自己的颜色、头像、气泡形状
- 每个 cat 的活动收在**一个气泡**内：文字、thinking（可折叠 brain 图标）、工具调用（可折叠 wrench 图标）
- 没有"cat 内部派 subagent"的概念——cat 就是一个 CLI 进程，Claude Code 内部的 subagent 不单独展示

### 并行模式（ideate）

多个 cat 同时执行时：
- `ParallelStatusBar`：一排 `CatStatusCard`，每个显示状态点 + cat 名 + 耗时
- 状态：pending=脉冲、streaming=绿脉冲、done=✓、error=✕
- 汇总 token 用量（In/Out/Cost）

### 任务进度（PlanBoardPanel）

- 来源：cat 的 CLI 进程调用 TodoWrite 工具时生成
- 不创建聊天消息，静默更新到 `catInvocations[catId].taskProgress`
- UI 渲染为看板卡片：进度计数 "3/5"、状态 badge（运行中/已中断/已完成）、每项 ✓/转圈/方块、`activeForm`（如 "Reading file.ts"）、进度条

### Liveness 检测

- `alive_but_silent`：琥珀色计时器 + 取消按钮
- `suspected_stall`：红色三角警告 + 取消按钮

**结论**：没有子 agent 概念，不适用于我们的场景。但 TaskProgressState 模型（静默更新 + 看板渲染）和 Liveness 两级警告值得参考。

---

## 4. 我们的现状

| 能力 | 当前用户看到什么 |
|---|---|
| 子 agent 启动 | AgentCard 显示 prompt + "running" 脉冲动画 |
| 子 agent 运行中 | **空白**。无工具调用、无 thinking、无文字输出 |
| 子 agent 完成 | AgentCard 更新为 "completed" + 最终 result 内容 |
| 子 agent 失败 | AgentCard 更新为 "failed" + error |
| 长时间运行 | 无任何 stale 警告 |
| 查子 agent 列表 | 无 IM 命令 |
| 控制子 agent | 无（`/stop` 终止主 agent + 所有子 agent） |

### 根因

subagent 在独立 session 运行，其 `tool_start`/`tool_end`/`assistant_message` 事件只在子 session 的 EventStreamHub 里。Gateway 的 `_build_kernel_event_observer` 只订阅父 session 事件，不订阅子 session。父 session 只收到两个事件：`agent tool_start`（开始）→ `agent tool_end`（结束）。

---

## 5. 跨项目对比

| 能力 | openclaw IM | openclaw web | hermes | clowder-ai | 我们 |
|---|---|---|---|---|---|
| 运行中工具调用可见 | ❌ | 切 session | ✅ 批量5 | N/A(无子agent) | ❌ |
| 运行中 thinking 可见 | ❌ | 切 session | ✅ 实时 | N/A | ❌ |
| 运行中文字输出可见 | ❌ | 切 session | ✅ 实时 | N/A | ❌ |
| 完成后回看 | ✅ 推完成消息 | ✅ 切 session | ✅ 通知+output_tail | N/A | ✅ result |
| Stale 警告 | ❌ | ❌ | ✅ 450s/1200s | ✅ 两级 | ❌ |
| IM 命令查状态 | ✅ /subagents list | N/A | ❌ | N/A | ❌ |
| 打字指示器 | ✅ 每6s | N/A | ✅ 平台适配 | N/A | ❌ |
| 通知策略 | ✅ 3种 | N/A | ❌ | N/A | ❌ |

**核心发现**：没有参考项目实现了"子 agent 活动 inline 嵌入父对话"。大家要么切 session 看（openclaw web），要么靠 IM 命令查（openclaw IM），要么批量推工具名列表（hermes）。

---

## 6. 可借鉴的模式

1. **hermes 的 batch+编辑**：工具名每 5 个批量推，原地编辑更新。适合 IM 场景减少刷屏
2. **hermes 的 thinking/文字不 batch**：这两类信息量大但频率低，逐条推合理
3. **openclaw 的 push-based + 反轮询**：子 agent 完成后主动推结果，禁止父 agent 轮询
4. **openclaw 的通知策略**：`done_only` / `state_changes` / `silent` 可配置
5. **clowder-ai 的 TaskProgressState**：静默更新到状态对象，UI 按需读取渲染，不污染聊天流
6. **clowder-ai 的 Liveness 两级警告**：`alive_but_silent` → `suspected_stall`，比单一 running 状态丰富
7. **openclaw web 的 Gateway 元数据**：`subagentRunState`、`childSessions`、`hasActiveSubagentRun` 已有但 UI 未用——说明数据层比展示层先到位是常见模式
