# bugfix-375: thinking round-trip 的两条架构根缺陷收口 — 技术方案

> 对齐: fix.md（lite 首文档，owner 决定在本 unit 内升级处理两条架构根缺陷）

## Changelog

<!-- 按时间倒序追加。格式：YYYY-MM-DD (Mx): 一句话 — 详见 Mx/progress.md -->

## 现状分析

本 unit 收尾的真 e2e（deep bug-finding + 跨重启续跑，kimi K2.6 thinking adaptive）暴露：此前一连串"thinking 字段丢失 / fork 里 hook 残废"的 bug 不是孤立缺陷，而是两条**架构根缺陷**的反复发作。本 design 把它们从契约层根治，并把已修的点纳入同一框架。

### 涉及范围

- `src/agent/core/hooks/runner.py` — `_strip_fork_conversation`（已修，#46）+ `dispatch_observe` mode 过滤（已修，#46）。
- `src/agent/core/hooks/context.py` — `HookContext`（frozen dataclass，字段随时间增长：message_history / permission_requester / fork_conversation 均后加）。
- `src/agent/core/types.py` — `Message`（frozen dataclass，reasoning_content / reasoning_signature 后加）。
- `src/agent/core/agent/loop.py:297/463/492` — 三处"复制 active_hook_ctx 改字段"型 `HookContext(...)` 重建。
- `src/agent/core/agent/runtime.py:508` — `background_hook_ctx`（复制型，漏 message_history/permission_requester）；`:763` `_fork_locked`（已修，#44）；`:976` canonical ctx builder（从零新建，安全）。
- `src/agent/core/agent/prompting.py:365` — `_merge_adjacent` 的 `Message(...)` 复制（已含 reasoning，但仍手写）。
- `src/agent/core/agent/context_fork.py` — `AgentContextFork.execute → AgentLoop.run` **不传 hook_ctx**（fork 上下文缺口的根）；`make_fork_conversation`。
- `src/agent/core/session/jsonl_store.py` `_to_message` / `_message_to_entry`、`src/agent/core/session/entries.py` — Message↔JSONL 序列化 round-trip（字段漏拷表现为持久化丢失）。
- `src/agent/platform/hooks/builtins/self_improvement.py` — review fork 的 allowlist + review prompt。

### 既有约束

- `core` 不依赖 `platform`/`products`（分层硬规则）。本 unit 改动集中在 `agent/core`，self_improvement 在 platform。
- `HookContext` / `Message` 是 `@dataclass(frozen=True, slots=True)` → 可安全用 `dataclasses.replace`。
- fork 侧链反递归约束：fork 自身 ctx 的 `fork_conversation` 必须为 None（防 review fork 再触发 review）。
- heartbeat / cron run 无人值守：不能产生"无人接听的 pending permission"（feat-333 既定）。

### 可复用能力

- `dataclasses.replace` — 标准库，已在 `_strip_fork_conversation`(#46) / `_fork_locked`(#44) 用过，本 unit 推广为统一纪律。
- `HookContext.metadata["run_origin"]` + `_UNATTENDED_ORIGINS` + `auto_mode.unattended_fallback` — feat-333 已有的无人值守短路机制，B' 直接复用，不新发明。
- `tool_execution_allowlist`（feat-349 fork 执行层收口）— 作为 fork 的硬安全边界，B' 复用。
- `skill_manage` 工具已支持 `list`/`view`/`create`/`edit`/`patch`（skill_manage.py:22）— 技能域内 inspect+写齐全，**无需补通用 read**。

### 相关历史

- #44(bugfix-375)：signature round-trip + 持久化保真 + `_fork_locked` 已修（co-root-cause A/B/C/D）。
- #46(bugfix-377)：`_strip_fork_conversation` replace 化 + `dispatch_observe` 按 mode 过滤（根缺陷1的两处发作 + 根缺陷3的一例）已修，已合 main。
- 参考实现核对：
  - **CC**（claude-code）`resumeAgent.ts:158` 子 agent 用 `workerPermissionContext = {...appState.toolPermissionContext, <override>}`；`spawnMultiAgent.ts` teammate 继承 permission mode；fork 子 agent `permissionMode:'bubble'` 冒泡给父终端，非交互 session 不开 fork；后台 worker"先跑自动检查，判不了才打扰人"。→ 印证 replace 派生（A）+ fork 继承父上下文（B）。
  - **Hermes**（hermes-agent）`agent/background_review.py:12` 后台 review"whitelist 限于 memory + skill 管理工具，其余运行时拒"，全自主不问人、写直接落库；用 `skill_view` 读、`skill_manage write_file` 写（技能域专用动词，非通用 read）。→ 印证 allowlist 是硬边界（B'）+ 不补通用 read（C）。

## 架构总览

两条根缺陷在参考实现里其实是**同一条原则**：派生上下文 = 复制父 + 只覆盖差异（CC 的 `{...parent, override}` = Python 的 `dataclasses.replace`）。

```
   反模式（现状，散落多处）：手写列字段重建 frozen dataclass
     new = T(a=src.a, b=src.b, ... )      ← 漏列即静默丢；新增字段全线漏
                       │
        ┌──────────────┴───────────────┐
   根缺陷1：数据保真               根缺陷2：能力传递
   复制 Message/HookContext        fork 不传 hook_ctx →
   漏 reasoning_*/message_history   裸默认 ctx（无 model_caller…）
        │                                │
   → 持久化/历史丢 thinking        → gate 在 fork fail-close、
     → 上游 reasoning missing         自进化处处碰壁、ask 必 deny

   ───────────────────────────────────────────────────────────

   正模式（目标，统一）：replace(src, 只写要改的)
     new = replace(src, a=新a)            ← 其余字段自动守恒，新增字段不漏
        │                                │
   根缺陷1 修：所有"复制改字段"        根缺陷2 修：fork 用 replace 派生
   点 → replace + 守卫测试            父 ctx（带 model_caller/permission_
   序列化类 → round-trip 完整性测试    requester）+ override allowlist
                                       → gate 在 fork 正常跑（B'：跑分类器
                                         + 标 unattended + allowlist 硬边界）
```

## 关键决策

### 决策 A：派生上下文 / 重建对象统一 `dataclasses.replace`

- **选择**：所有"复制一个已有 HookContext/Message 并改几个字段"的点改用 `dataclasses.replace(src, 只写要改的)`。新增一个守卫测试：给 HookContext/Message 实例化时填满所有字段（含哨兵值），断言每个复制点透传非显式覆盖的字段。序列化类（Message↔JSONL）无源对象、不能用 replace，改为补 round-trip 完整性测试（构造满字段 Message → entry → Message，断言字段不丢）。
- **理由**：把"字段守恒"从人工维护变成机制保证；CC 的 `{...parent, override}` 同款；新增 dataclass 字段时不再全线静默漏。
- **拒绝**：逐处点修（打地鼠，下次加字段又漏）；给 dataclass 加 `__post_init__` 校验（不解决"复制时漏列"，只在缺必填时报错）。
- **风险**：个别复制点是**故意**只取子集（如 observe ctx 故意不带 fork_conversation）；replace 会保留它 → 需逐点确认语义，故意丢弃的字段显式 `replace(src, x=None)`。

### 决策 B：fork 继承父执行上下文（采 CC 的 (a)）

- **选择**：`make_fork_conversation` / `context_fork.execute` 把父 `HookContext` 用 `replace` 派生给 fork 的 `AgentLoop.run(hook_ctx=...)`，带上 `model_caller` / `permission_requester` / `session_event_publisher`，只覆盖 fork 专属字段（`fork_conversation=None` 反递归、metadata 标记）。`tool_execution_allowlist` 仍走 run 参数。
- **理由**：CC（worker 继承 permissionContext）+ Hermes（review fork "uses the same auth"）一致；fork 内 hook 行为与主路径一致，gate 不再因无 model_caller 而 fail-close。
- **拒绝**：(b) fork 内 hook 整体旁路 — 会让 fork 失去安全门软校验，且与 CC/Hermes 不符；现状"裸默认 ctx" — 即 bug 本身。
- **风险**：fork 现在会真跑 gate（多若干分类器模型调用）；靠 B' 的无人值守短路 + allowlist 控制成本与安全。

### 决策 B'：fork 跑 gate + 标无人值守，ask 走 fallback，allowlist 当硬边界

- **选择**：fork run 的 `metadata["run_origin"]` 标为无人值守类（复用 `_UNATTENDED_ORIGINS`）。gate 在 fork 正常跑：routine 工具（skill_manage/memory/read…）由分类器自动放行；命中 `ask` 时因无人值守 → 走 `auto_mode.unattended_fallback`（默认 deny，可配 allow），不产生 pending。最终硬边界仍是 `tool_execution_allowlist`（不在表内的工具执行层直接拒）。
- **理由**：CC（后台 worker 先自动检查、非交互不冒泡）+ Hermes（白名单内自主、其余运行时拒）共识；复用 feat-333 既有无人值守机制，不新发明 pending 通道。
- **拒绝**：fork 内 ask 阻塞等人（heartbeat 无人 → 永久挂起，feat-333 已否决）。
- **风险**：unattended_fallback=deny 时偶发误拒 review 动作 → 该 review 轮无害放弃（self_improvement 已有 try/except 容错）。

### 决策 C：self_improvement review 不补通用 read，靠 B 通 skill_manage + prompt 引导

- **选择**：保持 review fork allowlist 为技能域工具（`("skill_manage",)` / `("skill_manage","memory")`），**不加通用 read/bash**。靠决策 B 让 skill_manage 在 fork 里不再 fail-close。`_SKILL_REVIEW_PROMPT` / `_COMBINED_REVIEW_PROMPT` 补一句明确引导：先 `skill_manage action=list` 发现、`action=view` inspect，再 create/edit/patch。
- **理由**：Hermes 同款（whitelist 限技能/memory 工具，用 skill_view 而非通用 read）；`skill_manage` 已自带 list/view；加通用 read/bash 会扩大 fork 的能力面、偏离"技能域闭环"。
- **拒绝**：给 allowlist 加 `read`（错误抽象，扩权面 + 与 Hermes 不符）。
- **风险**：prompt 引导不保证模型一定走 list/view；但 B 修好后即便它试通用 read 被拒，也已有 skill_manage 正路可用。

## 接口与数据流

- `_strip_fork_conversation(ctx)` → `replace(ctx, fork_conversation=None)`（已修，纳入 A 的纪律）。
- `loop.py` 三处 `tool_hook_ctx = HookContext(...)` / `runtime.py:508 background_hook_ctx` / `prompting.py:365` → `replace(src, …只改字段…)`；故意丢弃字段显式置 None。
- `context_fork.execute(..., parent_hook_ctx: HookContext | None)`：新增入参（或经 `make_fork_conversation` 闭包捕获父 ctx），内部 `fork_ctx = replace(parent_hook_ctx, fork_conversation=None, metadata={**parent.metadata, 标记无人值守})`，传给 `self._loop.run(state, hook_ctx=fork_ctx, tool_execution_allowlist=...)`。
- 守卫测试（A）：`tests/unit/` 新增——遍历/断言每个复制点字段守恒；Message↔JSONL round-trip 满字段。
- self_improvement：review prompt 文本增补；allowlist 不变。

## 风险与回退

- **风险1**：把某个"故意取子集"的复制点错误地 replace 全量透传 → 引入非预期字段。对策：逐点确认 + 单测；故意丢弃显式置 None。
- **风险2**：fork 现在跑 gate 增加模型调用与时延。对策：routine 自动放行、unattended 短路、allowlist 兜底；可观测 review fork 的分类器调用数。
- **回退**：本 unit 改动按决策分文件，可逐条 revert（A 的 replace 化、B 的 fork ctx 派生、C 的 prompt）。守卫测试独立，回退不影响既有绿测。
- **降级**：若 fork 跑 gate 出意外，B 可临时退回"fork 内 gate 旁路"（决策 B 拒绝项），但需显式声明 allowlist 为唯一边界。

## Runbook for Reviewer

本 unit 改的是 agent 内核库代码 + 一个 platform hook，**无新增常驻服务**。验收靠单测 + 一次真 e2e（reviewer 如需复现自进化路径，按 AGENTS.md 起 IM+Gateway 或 coding_cli managed，kimi K2.6 thinking，触发一次 self-improvement fork，翻 LLM proxy 日志确认 skill_manage 在 fork 里不再 fail-close）。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| （无常驻服务，仅库代码 + hook） | — | — | 单测 + 可选 e2e |

## Milestones

单 M1：四条决策同属"上下文/对象派生纪律 + fork hook 契约"一个内聚改动，跨文件但逻辑一体、无可并行的独立模块、估算 < 800 行，不满足拆分硬触发。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| bugfix-375-M2 | ctx-derive-discipline-and-fork-hook-contract | — | A | `hooks/runner.py`、`hooks/context.py`、`types.py`、`agent/loop.py`、`agent/runtime.py`、`agent/context_fork.py`、`agent/prompting.py`、`session/jsonl_store.py`、`session/entries.py`、`platform/hooks/builtins/self_improvement.py`、`tests/unit/*` | `[worker]` 全部"复制改字段"型 HookContext/Message 构造改用 `replace`，逐点确认语义；`[worker]` 守卫测试：复制点字段守恒 + Message↔JSONL round-trip 满字段，新增哨兵字段能触发失败；`[worker]` fork 经 `replace` 派生父 ctx，单测验 fork 的 `hook_ctx.model_caller/permission_requester` 非空、`fork_conversation is None`；`[worker]` 单测验 fork 内 gate 不再因无 model_caller fail-close（routine 工具放行）、无人值守 ask 走 fallback；`[worker]` self_improvement review prompt 含 list/view 引导，allowlist 未扩通用 read；`[reviewer]` 开 thinking 的 session fork 后可继续对话、self-evolution review 能用 skill_manage 实际改进 skill（不再"处处碰壁"），翻 proxy 日志无 `reasoning_content is missing`、无 fork 内 gate fail-close。 |
