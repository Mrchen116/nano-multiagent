# feat-385: System Prompt Runtime 切段式 + Memory 闭环修复 — 技术方案

> 对齐: spec.md v1
> Unit branch: `unit/feat-385` (will be created by orchestrator)

## Changelog

<!-- 按时间倒序追加。格式：YYYY-MM-DD (Mx): 一句话 — 详见 Mx/progress.md -->

## 现状分析

### 涉及范围

| 文件 / 模块 | 当前职责 | 本 unit 动作 |
|---|---|---|
| `core/agent/loop.py:155` | runtime 调 `build_system_prompt`(老 f-string 路径) | 替换为 `resolve_effective_prompt(sections, ctx, override)` 段式路径 |
| `core/agent/runtime.py:245` | `_run_locked` 构造 `hook_metadata`(`cwd / run_origin / context_window`...) + 传 `system_prompt_override` 给 loop | 在 session 启动点构造 `MemoryStore`、把 `memory_root` 注入 metadata;`hook_metadata` 已就位无需新增字段 |
| `core/agent/prompting.py` | `build_system_prompt` 老函数 + `LOCAL_CODING_SYSTEM_PROMPT` 字段缺省值常量 | 老函数与默认空字符串可保留供测试,**老 f-string 模板常量删除** |
| `core/agent/prompt_sections/base.py` | `PromptContext` 数据类(含 `memory_block` 字段) | **加 `user_profile_block: str \| None` 字段**(决策 X) |
| `core/agent/prompt_sections/wiring.py` | `build_prompt_context_from_metadata` 装配 helper | 函数签名加 `user_profile_block` 参数;runtime 在此点喂 memory & user 两块 |
| `core/agent/prompt_sections/core_sections.py` | 11 段 core,含 `core.memory_block`(order=950, cache_safe=False) | **加 `core.user_profile_block` 段**(order=960, cache_safe=False);**删 `core.runtime_tools` 段** |
| `core/memory/store.py` | `MemoryStore` + `format_for_prompt(target)` | 直接复用,不动 |
| `platform/bootstrap.py:78` | `resolved_system_prompt = profile.default_system_prompt or ""` —— 给 loop 当 fallback | **`profile.default_system_prompt` 不再用作 runtime 注入**,只保留 override 字段语义(给测试 / fork 路径用);bootstrap 不再赋 resolved_system_prompt |
| `platform/bootstrap.py:138-144` | 已构造 `memory_root = config_resolver.user_memory_root()`、注册 `MemoryTool(memory_root=...)` | **顺手把 `memory_root` 灌进 `default_session_metadata["memory_root"]`**,runtime 在 session 启动用 |
| `products/local_coding/prompts.py` | 含 `LOCAL_CODING_SYSTEM_PROMPT` f-string 模板常量 | **删除整个文件**(段都在 `local_coding/prompt_sections.py`) |
| `products/personal_assistant/prompts.py` | 含 `PERSONAL_ASSISTANT_SYSTEM_PROMPT` f-string 模板常量 | **删除整个文件** |
| `products/personal_assistant/prompt_sections.py:69-81` | `_PA_MEMORY_INTRO` 段(误导:让模型 read MEMORY.md) | **删整段**(沿用 `core.memory_guidance`,已是 hermes 写法)|
| `products/{local_coding,personal_assistant}/profile.py` | `default_system_prompt = ...` 字段赋值 | 改 `default_system_prompt = ""`(空串,触发段式装配)或显式去掉该字段 |
| `platform/http_api/routes/global_routes.py:359` | `/v1/prompt-preview` 端点已用段式,过滤 `cache_safe=True` | **不动**(本 unit 不改预览行为);删 `core.runtime_tools` 后预览自动一致 |
| 测试套件 | feat-379 段式 golden + 各产品 prompt 测试 | golden 需更新(memory/user 注入路径新增、`pa.memory_intro` 删除、`core.runtime_tools` 删除) |

### 既有约束

1. **核心包依赖方向硬规则**(`tests/contract/test_core_no_platform_imports.py` 验证):`core/agent/prompt_sections/` 是 pure core,禁止 import `platform` / `products`。装配 helper 只能调 core 内函数。
2. **段稳定/易变隔离**(`assemble_system_prompt` 校验):`cache_safe=False` 段必须 `order > 所有 cache_safe=True 段 order`。本 unit 新增 `core.user_profile_block` 用 order=960(`memory_block`=950 之后,符合)。
3. **memory_root 解析**:`config_resolver.user_memory_root()` 返回 `<workspace_root>/<workspace_config_dirname>/memory/`,**per-workspace 即 per-agent**(PA 每个 agent workspace 独立)。当 `config_resolver is None` 或 workspace 未配置时返 `None`,本 unit 在该情况下跳过 memory 注入(memory_block / user_profile_block 留 None,段自动失活)。
4. **Provenance 注释规则**(feat-379 决策 10):每个 PromptSection 定义处必带 `# Provenance:` 注释,标 CC 来源 / hermes 来源 / 改了什么。本 unit 新增段沿用,删段时同步删注释。
5. **frozen system prompt 通道**(`runtime.py:290 frozen_system_prompt = config.system_prompt`)和 before_agent_start hook 的 `system_prompt` 返回值仍走 override 路径,**装配阶段不能压制 override** —— `resolve_effective_prompt(sections, ctx, override)` 的 override 优先语义已经覆盖。
6. **MEMORY.md / USER.md 同一进程并发写**:`MemoryStore` 已用 `tempfile + os.replace` 原子写,readers 总看完整文件;本 unit 在 session 启动时读,与 MemoryTool 写无锁竞争(因为原子 rename)。

### 可复用能力

| 能力 | 当前位置 | 本 unit 用法 |
|---|---|---|
| 段式装配整套 | `core/agent/prompt_sections/{base, wiring, core_sections, feature_registry}` | **直接用**(`assemble_system_prompt` / `resolve_effective_prompt` / `build_prompt_context_from_metadata` / `resolve_flags_from_metadata` 全部既有 helper 全部够用) |
| MemoryStore + `format_for_prompt("memory" / "user")` | `core/memory/store.py` | **直接用**,session 启动时构造 + load_from_disk + 两个 target 各调一次 |
| memory_curation feature gate + 其 `core.memory_guidance` 段 | `core_sections.py:262-269` + `feature_registry.py:52-59` | **直接用**,memory_block 段已 enabled_when=ctx.memory_block,memory_curation 一旦关闭则 MEMORY.md 不渲染但需手动处理 USER.md(决策 Y 待定) |
| `/v1/prompt-preview` 装配模式 | `global_routes.py:296-360` | **作为 runtime 切换的参照实现**,runtime 装配几乎一样,只是不过滤 volatile 段(memory_block 实填) |
| `default_session_metadata` 注入机制 | `bootstrap.py:147-154` → `runtime._session_configs[].metadata` → `wiring.build_prompt_context_from_metadata` | **直接用**,把 `memory_root` 路径加入 default_session_metadata 即可流转到装配点 |

### 相关历史

- **feat-379**(PR #51 已合,2026-05-22):引入段式框架 + UI feature 开关 + prompt-preview 端点。**runtime 切换漏做**(bootstrap.py:160 自承"legacy string-based prompt path")—— 本 unit 收尾。
- **feat-349**(引入 MemoryTool + MemoryStore + 自进化):design.md L24 原计划"prompting.py 增注入 memory block",worker 漏接,本 unit 补。memory 双产品覆盖、USER.md 隔离、默认开关等已对齐结论(feat-349 spec Q1/Q3/Q5),本 unit 沿用不重新决议。
- **feat-383**(M1 已合,2026-05-23):基于段式做 prompt-preview 保真。本 unit 删 `core.runtime_tools` 后,预览的"`## Available Tools` 行后是空"问题自动消失,与 feat-383 无冲突。
- **bugfix-368**(memory tool auto-mode allowlist):MemoryTool 在 auto mode 下的允许策略,与本 unit 注入链路无交集。

### 待留观察的小漂移(本 unit 不修)

- `personal_assistant/config/local_store.py:32` 注释说"memory 文件应在 `.nanoassistant/memory/`",但 `_DEFAULTS` 实际 seed `MEMORY.md` 到 `<workspace_root>/` 根。此漂移在 feat-349 引入,与本 unit 注入路径不直接相关(MemoryTool 用的是 resolver 计算的 `.nanoassistant/memory/`)—— 留观察,后续若发现 workspace 根的 stale `MEMORY.md` 误导用户再开 bugfix。

## 架构总览

### 一句话

**runtime 装配 = 现有 `/v1/prompt-preview` 装配模式 + 不过滤 volatile 段 + 真填 memory_block / user_profile_block(per-session 隔离 + freeze-on-first-turn)+ 真值 datetime / cwd**。即 `loop.py` 把 `build_system_prompt(...)` 改为照搬 `global_routes.py:296-360` 的 `PromptContext` 装配模式,加上 memory 两块的渲染、override 路径的优先解析。同时顺手把 MemoryTool 的 per-process 共享 bug 修掉(读写从同一 memory_root 派生)。

### Before(本 unit 上线前)

```
RUNTIME 每个 turn:
  loop.build_system_prompt(LOCAL_CODING / PERSONAL_ASSISTANT 模板字符串)
    ├─ <RUNTIME_FILL:*> 占位符替换
    └─ + MEMORY_GUIDANCE / SKILLS_GUIDANCE / BACKGROUND_TASK_PROMPT 常量
  → 老 f-string 拼接产物
  → LLM call(system_prompt + tools=[])

段式资产(feat-379 已就绪):
  CORE_SECTIONS + 产品 sections → app.state.prompt_sections
  唯一消费者 = POST /v1/prompt-preview(过滤 cache_safe=True)
  memory_block 字段:存在但永远 None,segment 永不激活

MemoryTool 隔离:
  bootstrap.py:143 MemoryTool(memory_root=<bootstrap-time fixed path>)
  → MemoryTool._resolve_memory_root 第一行短路
  → 所有 agent session 共写一份 MEMORY.md / USER.md(per-process,非 per-agent)
```

### After(本 unit 上线后)

```
BOOTSTRAP-TIME(每 product profile 一次):
  bootstrap_product(profile):
    resolved.prompt_sections = CORE_SECTIONS + profile.prompt_sections
    resolved.tool_registry (含 memory_tool — 但不带 _fixed_memory_root)
    resolved.default_session_metadata["workspace_config_dirname"]
        = profile.workspace_config_dirname     ← 新增 metadata key
    (不再写 memory_root,因为路径要 per-session 派生)

SESSION 启动 + 每个 turn:
  bugfix-348 已建链路:caller 把 workspace_root 透到 SessionConfig.workspace_root
  runtime._run_locked:
    hook_metadata = config.metadata(含 workspace_config_dirname、agent_features)
                  + cwd + run_origin + ...
                  + workspace_root = str(session_workspace_root)   ← 新增 key

    (1) snapshot = self._ensure_memory_snapshot(session_id, metadata)
        - cache hit → 直接返回
        - cache miss:
            flags = wiring.resolve_flags_from_metadata(metadata)
            if not flags["memory_curation"]: snapshot = (None, None)  ← gate
            elif workspace_root / workspace_config_dirname 缺: snapshot = (None, None)
            else:
              memory_root = <workspace>/<workspace_config_dirname>/memory/
              store = MemoryStore(memory_root).load_from_disk()
              memory_block = store.format_for_prompt("memory")
              user_block   = store.format_for_prompt("user")
              snapshot = (memory_block, user_block)
            self._memory_snapshots[session_id] = snapshot
        - 返回 snapshot

    (2) ctx = wiring.build_prompt_context_from_metadata(
            metadata,
            available_tools, available_skills,
            current_datetime=session_created_at, cwd,
            memory_block=snapshot.memory_block,
            user_profile_block=snapshot.user_profile_block,  ← 新增字段
            flags=resolve_flags_from_metadata(metadata),
            vars={"custom_prompt": ...},
        )

    (3) rendered = resolve_effective_prompt(
            sections=app.state.prompt_sections,
            ctx=ctx,
            override=before_payload['system_prompt'] or config.system_prompt
        )

    (4) LLM call(system_prompt=rendered, tools=active_tools)

  段集状态:
    • core.runtime_tools 已删 — 工具描述只走 API tools=[] 通道
    • core.memory_block(order=950, cache_safe=False) 由 ctx.memory_block 激活
    • core.user_profile_block(order=960, cache_safe=False) 由 ctx.user_profile_block 激活  ← 新段
    • pa.memory_intro 已删 — 不再误导
    • LOCAL_CODING_SYSTEM_PROMPT / PERSONAL_ASSISTANT_SYSTEM_PROMPT 模板已删

COMPACTION 失效:
  loop._maybe_compact 成功路径调 runtime._invalidate_memory_snapshot(session_id)
  下个 turn _ensure_memory_snapshot cache miss → 重新 freeze → 重读磁盘

MEMORY TOOL 写入(同链路):
  MemoryTool.run(ctx):
    _resolve_memory_root(ctx):
      不再有 _fixed_memory_root 短路
      from ctx.session_metadata 读 workspace_root + workspace_config_dirname
      → 派生 <workspace>/<workspace_config_dirname>/memory/
      (用 core.memory.path 内 helper,与 _ensure_memory_snapshot 共享派生逻辑)
    → MemoryStore 操作 per-session 隔离的文件

PREVIEW 端点不变:
  仍过滤 cache_safe=True,memory_block / user_profile_block 段自动 skip
  core.runtime_tools 已删 → 与 runtime 自动一致
```

### 核心设计原则(本 unit 立)

**Per-workspace 资源路径治理**:

> 任何 per-workspace 资源(session JSONL / memory / skill / hook 等)的物理路径,必须基于 `<session.workspace_root> / <profile.workspace_config_dirname> / <subdir>` 派生。
>
> - **禁止硬编码** `.nano` / `.nanoassistant` / `.nanocode` 等字符串(只允许出现在 product `defaults.py` 常量定义处)
> - **禁止 bootstrap-time 固定** per-workspace 路径(bootstrap 是 per-process,session 是 per-agent)
> - **统一抽象**:`ConfigResolver._build_roots(subdir)` 或共享 `core.memory.path` helper
> - **加 contract 测试**(`tests/contract/test_no_hardcoded_workspace_dirname.py`):扫描 `src/` 下所有出现的 `.nano` / `.nanoassistant` / `.nanocode`,只允许 product `defaults.py` 命中,其他位置报错

(本 unit 落地 memory 部分,PR #9 bugfix-348 落地 session JSONL 部分。Skill / hook 抽象层已对,只需 contract 测试持续防回归。)

## 关键决策

### 决策 1: memory_root 解析方式 — per-session 从 metadata 派生

- **选择**:bootstrap **不再** 给 MemoryTool 传 fixed `memory_root`;runtime 在 `_run_locked` 把 `workspace_root` + 复制 `workspace_config_dirname` 进 hook_metadata;memory_root 由 `<workspace_root>/<workspace_config_dirname>/memory/` 派生,MemoryTool 与 runtime 的 freeze 流程共享此派生。
- **理由**:per-product 常量已有(`profile.workspace_config_dirname`),per-session workspace_root 透传由 bugfix-348 建好;memory_root 是纯派生不该缓存;读写从同一来源派生保证一致。
- **拒绝**:
  - bootstrap 时算固定 memory_root(现状,违背 per-agent 隔离契约,feat-349 spec Q3)
  - runtime 引用 ConfigResolver(打破 core ↛ platform 依赖方向)
- **风险**:依赖 bugfix-348 hook_metadata workspace_root 透传链路真完整 — 实施期 worker 第一步必须验证 PR #9 已合且链路工作。

### 决策 2: memory snapshot 存放点 — `AgentRuntime` 内部 dict

- **选择**:`AgentRuntime._memory_snapshots: dict[session_id, MemorySnapshot]` 内部 cache;`MemorySnapshot = TypedDict({"memory_block": str | None, "user_profile_block": str | None})`。session shutdown 时随 `self._session_configs.pop(...)` 一并清理。
- **理由**:SessionConfig 保持现状 immutable 语义;snapshot 是 runtime-only volatile cache,不该污染配置;与 hermes `agent._cached_system_prompt` 同思想。
- **拒绝**:
  - 写进 SessionConfig.metadata(破坏 immutable 假设)
  - 全局 dict(跨 runtime 实例共享语义不清)
- **风险**:多 session 大量 snapshot 占内存 — 单 snapshot 约 4KB(memory + user),1000 session 约 4MB,可接受。

### 决策 3: freeze 时机 — lazy on first `_run_locked`

- **选择**:首次 `_run_locked` 进入 `_ensure_memory_snapshot` 时构造 MemoryStore + render + cache;之后每 turn 直接读 cache;compaction 事件 invalidate cache。
- **理由**:对齐 CC `systemPromptSection` cache 模式(`systemPromptSections.ts:50`)+ hermes `_cached_system_prompt` 模式(`conversation_loop.py:315`);零未发对话的 session 不读磁盘;同一处处理 feature gate + 无 workspace_root 降级。
- **拒绝**:
  - 每 turn 重新调 `format_for_prompt`(破坏 prefix cache 稳定性,与两个参考实现都矛盾)
  - session 创建时 eager 渲染(未发对话的 session 浪费 IO)
- **风险**:无。

### 决策 4: compaction 失效机制 — `_maybe_compact` 主动 callback invalidate

- **选择**:在 `loop._maybe_compact` 成功路径末尾,调用 runtime 注入的 callback `on_compaction(session_id)` → runtime 实现为 `self._memory_snapshots.pop(session_id, None)`。下个 turn `_ensure_memory_snapshot` cache miss → 重新 freeze 读最新磁盘内容。
- **理由**:对齐 hermes `invalidate_system_prompt` + reload(`system_prompt.py:300 _memory_store.load_from_disk()`)+ CC `clearSystemPromptSections()`(`/clear` + `/compact` 触发);compaction 后 prefix cache 已废,正好顺势重读 memory;loop 不直接 import runtime,通过注入 callback 保持模块边界。
- **拒绝**:
  - 不在 compaction 时重读(用户写了 memory 看不到自己写的,体验差)
  - loop 直接调 runtime 方法(打破核心模块边界)
- **风险**:无。

### 决策 5: feature gate 处理点 — 统一在 `_ensure_memory_snapshot` 内

- **选择**:`memory_curation` flag 在 `_ensure_memory_snapshot` 内判定;flag off 时直接返回 `(None, None)`,**根本不读磁盘**;`core.memory_block` / `core.user_profile_block` 段通过 `ctx.memory_block / ctx.user_profile_block` 为 None 自动失活;同 flag 同时 gate `core.memory_guidance` 段(feat-379 已就位)。
- **理由**:单点处理,避免段内 gate + snapshot 内 gate 双重判定不一致;memory_curation off → 零磁盘 IO + 零内存中字符串(隐私 / token 友好)。
- **拒绝**:
  - 段内 enabled_when 判 flag(snapshot 已经渲染浪费 IO,隐私不友好)
- **风险**:无。

### 决策 6: USER.md 注入 — 独立 PromptContext 字段 + 独立段(方案 X)

- **选择**:`PromptContext` 新增 `user_profile_block: str | None`;`core_sections.py` 新增 `core.user_profile_block`(order=960, cache_safe=False, enabled_when=`ctx.user_profile_block`);`wiring.build_prompt_context_from_metadata` 加同名参数。
- **理由**:严格复刻 hermes(`format_for_system_prompt("memory") + format_for_system_prompt("user")` 两段独立 append, `system_prompt.py:238-245`);未来若需独立 gate(`user_profile_curation` feature)零改动;字段成本极低(一个 `str | None`)。
- **拒绝**:
  - 与 memory 合段成一个字段(失去独立 gate 可能性;hermes 也分两段)
- **风险**:无。

### 决策 7: PA `pa.memory_intro` 段处理 — 整段删除

- **选择**:`products/personal_assistant/prompt_sections.py:69-81` `_PA_MEMORY_INTRO` 段连同 Provenance 注释整段删除;`PA_SECTIONS` tuple 同步移除引用。
- **理由**:`core.memory_guidance`(`core_sections.py:262-269`)已包含 hermes `MEMORY_GUIDANCE`(原作于 `agent/prompt_builder.py:150`)的等效内容("you have persistent memory, save durable facts using memory tool");PA 那段额外指示模型"用 read 工具读 MEMORY.md",指向的 `<workspace>/MEMORY.md` 与 MemoryTool 操作的 `<memory_root>/MEMORY.md` 不是同一文件,误导模型走错路径。
- **拒绝**:
  - 改文案保留段(冗余于 core.memory_guidance,且无 PA 专属价值)
- **风险**:无 — `core.memory_guidance` 在 memory_curation on + 有 memory 工具时激活,覆盖原 PA 段的所有有效语义。

### 决策 8: 删 `core.runtime_tools` 段 — 不留 fallback

- **选择**:`core_sections.py` 中 `core.runtime_tools` 段连同 `_render_runtime_tools` 整段删除;`CORE_SECTIONS` tuple 同步移除引用。工具描述完全由 LLM API `tools=[]` 通道送达。
- **理由**:本仓所有 provider 都通过 LLM 代理走 Anthropic / OpenAI-compat 协议,这两种原生支持 tools 参数;`## Available Tools` 段是冗余 + token 浪费 + 隐藏 provider 适配 bug。
- **拒绝**:
  - 留 fallback 段(本 unit spec Q6 用户决定:"不兜底")
- **风险**:若某 provider 适配层未传 tools 通道,tool calling 直接炸 — **这是 provider 适配层 bug,本 unit 不掩盖**(spec scenario 三 / Q6 明确)。

### 决策 9: MemoryTool 隔离修复(Q7 G1)

- **选择**:
  1. `bootstrap.py:143` `MemoryTool(memory_root=None)`(不传)
  2. `MemoryTool._resolve_memory_root` 删除 `if self._fixed_memory_root` 短路逻辑(`memory.py:187-188`);保留 `_fixed_memory_root` 字段仅供测试脚手架显式传入
  3. `MemoryTool._resolve_memory_root` fallback 从 `ctx.session_metadata['workspace_root']` + `['workspace_config_dirname']` 派生 memory_root,**禁止硬编码** `.nano`
  4. 引入 `core/memory/path.py` 小 helper `derive_memory_root(workspace_root, workspace_config_dirname) -> Path`,MemoryTool 与 runtime `_ensure_memory_snapshot` 共用此 helper
- **理由**:本 unit memory 注入读路径与 MemoryTool 写路径必须一致,否则形同虚设;feat-349 spec Q3 "每个 agent 完全隔离自己的 memory" 契约的 code-level 落地。
- **拒绝**:
  - 推迟到独立 bugfix(memory 闭环修复必须有正确 memory_root,推延会让本 unit 失败 — Q7 G3 已否决)
- **风险**:依赖 bugfix-348 hook_metadata 透传 — 决策 1 已注。

### 决策 10: Per-workspace 路径架构原则 + contract 测试

- **选择**:立"per-workspace 资源必须走 `profile.workspace_config_dirname` + ConfigResolver / 共享 helper 派生,禁止硬编码 `.nano` / `.nanoassistant` / `.nanocode`"作为架构原则,写进本 design;落地一条 contract 测试 `tests/contract/test_no_hardcoded_workspace_dirname.py`,grep `src/agent`、`src/personal_assistant`、`src/coding_cli` 下出现的三个字符串,只允许 product `defaults.py` 命中,其他位置报错。
- **理由**:本 unit 在 PR #9 的并行问题(同族架构 bug)上,提前立原则 + 加防回归测试,后续 worker 不会再绕过 resolver / 硬编码。
- **拒绝**:
  - 只修不立原则(防回归差,下次又会有人硬编码)
- **风险**:contract 测试可能误报既有正确用法 — 实施期排查白名单,但保留"产品 defaults.py 之外不能出现"作为 ground rule。

### 决策 11: 老 f-string 模板退役

- **选择**:删除以下文件和常量:
  - `src/agent/core/agent/prompting.py`:`LOCAL_CODING_SYSTEM_PROMPT`、`CODING_SYSTEM_PROMPT`、`DEFAULT_SYSTEM_PROMPT` 等常量(整文件可保留,函数 `build_system_prompt` 不再被 runtime 调,可仅留 `build_chat_messages` 等纯 LLM 消息装配);老 `_DEFAULT_TOOL_SPECS` 删除
  - `src/agent/products/local_coding/prompts.py` 整文件删
  - `src/agent/products/personal_assistant/prompts.py` 整文件删
  - 各 `profile.py` 中 `default_system_prompt` 字段值改 `""`(空串)或显式去掉
- **理由**:runtime 切段式后,这些常量永远不被用;留着会迷惑后续 worker 以为有两条路径并存。
- **拒绝**:
  - 保留作为"override 路径的默认值"(override 路径优先级 1 是 frozen system prompt;空串就行)
- **风险**:某些测试可能引用这些常量 — 实施期搜索引用并迁移到段式产物或显式空串。

### 决策 12: `resolve_effective_prompt` 路径 — runtime 单一入口

- **选择**:`loop.py:155` 既有 `build_system_prompt(...)` 调用整段替换为:
  ```python
  ctx = wiring.build_prompt_context_from_metadata(metadata, ..., memory_block, user_profile_block, ...)
  rendered_system_prompt = resolve_effective_prompt(
      sections=self._prompt_sections,  # 通过 ctor 注入 from app.state
      ctx=ctx,
      override=system_prompt_override or self._frozen_system_prompt
  )
  ```
- **理由**:对齐 feat-379 base.py 决策 9(`resolve_effective_prompt` 是单一解析点,override > section assembly,镜像 CC `buildEffectiveSystemPrompt`);override 路径(before_agent_start hook / 子 agent fork frozen prompt)继续工作。
- **拒绝**:
  - 在 loop 里直接 if/else override(重复决策 9 已存在的逻辑)
- **风险**:`AgentLoop` 需要被注入 `prompt_sections` — ctor 改造涉及 runtime / app 装配,需要确认调用方都更新。

### 决策 13: 沿用 feat-379 决策 10 — Provenance 注释规则

- **选择**:本 unit 新增段(`core.user_profile_block`)定义处带 `# Provenance: new — hermes-adapted from agent/system_prompt.py:236-245 (MemoryStore.format_for_system_prompt + USER.md branch)`;删段(`pa.memory_intro`、`core.runtime_tools`)时同时删整段含 Provenance 的代码,Changelog 段记一笔删除理由。
- **理由**:feat-379 已建立的硬规则,本 unit 沿用即可。
- **拒绝**:无。
- **风险**:无。

### 决策 14: `local_store.py` seed 位置修正

- **选择**:`personal_assistant/config/local_store.py:38` 把 `MEMORY.md` / `USER.md` seed 位置从 `<workspace_root>/MEMORY.md` 改到 `<workspace_root>/.nanoassistant/memory/MEMORY.md`(用 `WORKSPACE_CONFIG_DIRNAME` 常量,**不硬编码字符串**);旧位置的 `MEMORY.md` 即使存在也不再被 MemoryTool / freeze 流程读取,可在文档中提示一次性 cleanup 但**本 unit 不做数据迁移**。
- **理由**:与 MemoryTool / freeze 流程读写位置一致(`<workspace>/<dirname>/memory/`),消除 spec.md 备注里那个"两个 MEMORY.md 文件"问题。
- **拒绝**:
  - 保留旧位置 seed + 不动 MemoryTool 路径(继续矛盾,违背决策 10 原则)
- **风险**:已有 PA agent workspace 里的旧 `MEMORY.md` 是 stale 文件 — 用户感知就是"workspace 根有个空 MEMORY.md 没用",清理是无害操作;本 unit 文档中提示一次。

## 接口与数据流

### 数据结构改动

```python
# core/agent/prompt_sections/base.py
@dataclass(frozen=True)
class PromptContext:
    available_tools: tuple = ()
    available_skills: tuple = ()
    current_datetime: str = ""
    cwd: str = ""
    memory_block: str | None = None
    user_profile_block: str | None = None    # ← 新增字段
    flags: Mapping[str, bool] = field(default_factory=dict)
    scenario: Mapping[str, object] = field(default_factory=dict)
    vars: Mapping[str, str] = field(default_factory=dict)
```

```python
# core/agent/runtime.py
class AgentRuntime:
    self._memory_snapshots: dict[str, "MemorySnapshot"] = {}    # ← 新增

class MemorySnapshot(TypedDict):
    memory_block: str | None
    user_profile_block: str | None
```

```python
# core/memory/path.py — 新增小 helper(本 unit 引入)
def derive_memory_root(
    workspace_root: Path,
    workspace_config_dirname: str,
) -> Path:
    """Per-session memory root derivation. Used by both MemoryTool and runtime."""
    return workspace_root / workspace_config_dirname / "memory"
```

### 关键函数 / 接口签名

```python
# core/agent/prompt_sections/wiring.py
def build_prompt_context_from_metadata(
    *,
    metadata: Mapping[str, Any],
    available_tools: Sequence,
    available_skills: Sequence,
    current_datetime: str,
    cwd: str,
    memory_block: str | None,
    user_profile_block: str | None,           # ← 新增参数
    flags: Mapping[str, bool],
    vars: Mapping[str, str] | None = None,
) -> PromptContext: ...

# core/agent/runtime.py
class AgentRuntime:
    def _ensure_memory_snapshot(
        self,
        session_id: str,
        metadata: Mapping[str, Any],
    ) -> MemorySnapshot:
        """Lazy freeze. Returns cached snapshot; renders + caches on first call."""

    def _invalidate_memory_snapshot(self, session_id: str) -> None:
        """Called by loop._maybe_compact success path to force reload next turn."""

# core/agent/loop.py — _maybe_compact 增加 callback
async def _maybe_compact(
    self,
    *,
    llm_messages: ...,
    session_id: str,
    rendered_system_prompt: str,
    session_file_state: ...,
) -> Message | None:
    ...
    if compaction_succeeded:
        if self._on_compaction_callback:        # ← 新增 callback 注入
            self._on_compaction_callback(session_id)
    ...

# platform/bootstrap.py — default_session_metadata 注入
default_session_metadata["workspace_config_dirname"] = profile.workspace_config_dirname or ""

# platform/tools/builtins/memory.py — _resolve_memory_root 改造
def _resolve_memory_root(self, ctx: Any) -> Path:
    # 1. 测试脚手架显式 _fixed_memory_root 优先(测试用)
    if self._fixed_memory_root is not None:
        return self._fixed_memory_root
    # 2. 生产路径:从 ctx.session_metadata 派生
    metadata = getattr(ctx, "session_metadata", {}) or {}
    workspace_root = metadata.get("workspace_root")
    dirname = metadata.get("workspace_config_dirname")
    if workspace_root and dirname:
        return derive_memory_root(Path(str(workspace_root)), str(dirname))
    # 3. 旧 fallback(workspace 但没 dirname)— 改为 raise,不再静默走 ".nano"
    raise RuntimeError(
        "memory_root cannot be resolved: missing workspace_root or workspace_config_dirname in session_metadata"
    )
```

### 数据流时序

```
[Bootstrap-time, 一次性]
bootstrap_product(profile=PA, repo_root=...)
  → resolved.default_session_metadata["workspace_config_dirname"] = ".nanoassistant"
  → MemoryTool() 无 fixed memory_root

[Session 创建,由 PA Gateway / coding CLI 调用]
runtime.create_session(workspace_root=<agent workspace>, ...)
  → SessionConfig.workspace_root = <agent workspace>
  → SessionConfig.metadata = default_session_metadata + session-specific overrides
  → self._session_configs[session_id] = config
  → self._memory_snapshots[session_id] = (未填,lazy)

[每个 turn,_run_locked]
hook_metadata = dict(config.metadata)
hook_metadata["workspace_root"] = str(session_workspace_root)
hook_metadata["cwd"] = str(session_workspace_root)
hook_metadata["run_origin"] = ...

snapshot = self._ensure_memory_snapshot(session_id, hook_metadata):
  if cache hit: return cached
  else:
    flags = wiring.resolve_flags_from_metadata(hook_metadata)
    if not flags["memory_curation"]:
      cache (None, None); return
    workspace_root = hook_metadata.get("workspace_root")
    dirname = hook_metadata.get("workspace_config_dirname")
    if not (workspace_root and dirname):
      cache (None, None); return
    memory_root = derive_memory_root(Path(workspace_root), dirname)
    store = MemoryStore(memory_root).load_from_disk()
    memory = store.format_for_prompt("memory")
    user = store.format_for_prompt("user")
    cache (memory, user); return

→ loop._dispatch:
  ctx = wiring.build_prompt_context_from_metadata(
    hook_metadata, ..., memory_block=snapshot["memory_block"],
    user_profile_block=snapshot["user_profile_block"], ...
  )
  rendered = resolve_effective_prompt(self._prompt_sections, ctx, override=...)
  → LLM call(system_prompt=rendered, tools=tools_specs)

[Compaction]
_maybe_compact 成功 → callback(session_id) → runtime._invalidate_memory_snapshot(session_id)
下个 turn → _ensure_memory_snapshot cache miss → 重新 freeze → 重读磁盘

[MemoryTool 写入]
MemoryTool.run(args, ctx):
  memory_root = self._resolve_memory_root(ctx)   # 同 freeze 流程派生
  store = MemoryStore(memory_root)
  store.add/replace/remove(...)
  → 写到与 freeze 流程同一文件

[Session 关闭]
runtime.session_shutdown(session_id):
  self._session_configs.pop(session_id, None)
  self._memory_snapshots.pop(session_id, None)    # ← 新增
```

### 不变量

1. **cache_safe 不变量**:`core.user_profile_block` order=960 > 所有 cache_safe=True 段的 order(`assemble_system_prompt` 校验)
2. **memory_root 一致性**:MemoryTool 写入位置与 freeze 读取位置永远是同一物理路径(共享 `derive_memory_root`)
3. **per-agent 隔离**:每个 session 的 memory_root 都由该 session 的 workspace_root 派生,跨 session(跨 agent)不共享(契约对齐 feat-349 spec Q3)
4. **feature gate 单点**:memory_curation off 时不读磁盘 + segment 自动不渲染(`_ensure_memory_snapshot` 单点处理)
5. **段集装配产物 = preview 装配产物**(对 stable 段):runtime 与 preview 用同一组 sections,差异仅在是否包含 volatile 段 + volatile 段是否填真实值

## 风险与回退

### 已知风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| bugfix-348 未合并就启动实施 | 大量 merge conflict,workspace_root 透传链路不完整,本 unit 实现路径不成立 | 实施期 worker 第一步显式验证 PR #9 已合;若未合,milestone 阻塞 |
| compaction callback 注入路径破坏 loop 模块边界 | 设计意图是 callback 解耦,但实施 worker 可能为图省事直接 `from agent.core.agent.runtime import ...` | design 明确 callback 形态;contract test 验证 loop.py 不 import runtime |
| MemoryTool _resolve_memory_root 改造导致依赖它的测试炸 | 既有测试可能传 ToolContext 不带 workspace_root / dirname,fallback 不再静默退路径 → raise | 实施期改测试,要么显式传 `_fixed_memory_root`(测试脚手架),要么 metadata 带齐两个 key |
| `local_store.py` seed 位置改后,既有 PA agent workspace 里旧位置的 `MEMORY.md` 成为 stale | 用户在 workspace 根看到一个老 `MEMORY.md`,以为是当前 memory 但 MemoryTool 不读它 | design.md 决策 14 已明:本 unit 不做数据迁移,文档提示;若实际有用户已在旧位置写 memory,需要在 runbook / release note 写"一次性 cp 到新位置"的指引 |
| 删 `## Available Tools` 后某 provider tool calling 炸(spec Q6 场景三) | tool calling 整体不工作,agent 失能 | spec scenario 三明确"不兜底,暴露问题"。本 unit 不修 provider 适配,reviewer 在回归旅程发现立 issue,下个 unit 修 |
| 段集 cache_safe 顺序违反 | `assemble_system_prompt` 启动时 raise ValueError | feat-379 已建的校验,本 unit 新增段 order=960 满足约束;单测覆盖 |
| Contract test 误报既有正确硬编码用法 | 实施期 worker 卡在测试无法通过 | 实施期 worker 列白名单(`defaults.py`、docs 字符串)排除 |

### 回退方案

- **整体回退**:`git revert` PR;runtime 回到 f-string 路径(老 `build_system_prompt`);memory 闭环再次断开;`## Available Tools` 回归;`pa.memory_intro` 段恢复。回滚干净。
- **部分回退**(若 memory 闭环出问题但段式切换正常):决策 1-5 / 9 / 14 的提交可分别 revert;段式切换、删 runtime_tools、删 pa.memory_intro 等保留。具体可分性靠 milestone 拆分时按"提交粒度"组织。
- **数据回退**:本 unit 不动 MEMORY.md / USER.md 文件内容(只换读取位置);若决策 14 seed 位置变更引发问题,把 `local_store.py` 回到 workspace 根 seed 即可,文件本身不丢。

### 降级路径

- 实施期发现 `core.user_profile_block` 段引发问题(如某 LLM provider 对 system prompt 长度敏感导致超限),可临时把 `enabled_when` 改为永假禁段,不影响 memory_block 段。
- compaction callback 接通有问题时,临时方案:`_invalidate_memory_snapshot` 在 turn 结束 hook 里调一次(每 turn 都重读 — 牺牲 prefix cache 命中,换正确性);本 unit 范围内,正式方案是 compaction 触发。

## Runbook for Reviewer

reviewer 接管时需要起以下服务做回归验收(走 spec scenarios 一/二/三):

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| Kernel API(本 unit 主体跑在它内部) | `kill $(cat .api.pid) 2>/dev/null; rm -f .api.pid` | `read API_PORT < <(scripts/free-ports.sh 1); IM_JWT_SECRET="feat-385-reviewer-r1-$(date +%s)" NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4000 PYTHONPATH=src python -m uvicorn agent.platform.http_api.app:app --port "$API_PORT" > .api.log 2>&1 & echo $! > .api.pid` | `curl -s http://127.0.0.1:$API_PORT/v1/health` 返回 `{"healthy":true}` |
| IM Server(IM 配置页 + 预览端点回归) | `kill $(cat .im.pid) 2>/dev/null; rm -f .im.pid` | `read IM_PORT < <(scripts/free-ports.sh 1); IM_JWT_SECRET="feat-385-reviewer-r1-$(date +%s)" PYTHONPATH=src python -m uvicorn IM.app:app --port "$IM_PORT" > .im.log 2>&1 & echo $! > .im.pid` | `curl -s http://127.0.0.1:$IM_PORT/im/v1/health` 200 |
| PA Gateway(memory 闭环 + 多 agent 隔离回归) | `kill $(cat .gateway.pid) 2>/dev/null; rm -f .gateway.pid` | 见 AGENTS.md 的 worktree Gateway 启动范式(`--foreground + --auto-bind + --config <worktree>/.gateway-config.yaml`);config 含至少两个 agent(不同 workspace_root)以便验证 per-agent 隔离 | Gateway 日志含 "IM bind successful" |

通用清理:

```bash
for f in .im.pid .api.pid .gateway.pid; do
  [[ -f $f ]] && kill "$(cat "$f")" 2>/dev/null; rm -f "$f"
done
```

走 spec scenarios 时附加验证:

1. **memory 跨 session 感知**:agent A 写一条 memory → 关 session → 重开 session → 看 system prompt(用 prompt-preview 或 LLM 实际响应)是否含该条 memory
2. **memory per-agent 隔离**:agent A 写一条 memory → 切换到 agent B(不同 workspace_root)→ 看 agent B 是否看不到该条
3. **memory_curation OFF**:UI 关闭 → 重开 session → system prompt 不含 memory_block 段
4. **compaction reload**:发足够多 turn 触发 compaction → 重开 turn → 看 system prompt 是否反映 compaction 前后的 memory 写入
5. **删 ## Available Tools 后工具调用 OK**:逐工具触发(read / write / edit / bash / memory / skill_manage / send_message 等)
6. **`local_store.py` seed 新位置**:新建 PA agent → 验证 `<workspace>/.nanoassistant/memory/MEMORY.md` 出现(不是 workspace 根)

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-385-M1 | impl | bugfix-348(PR #9)已合 | A | 全 unit 范围:`core/memory/path.py` 新增;`core/agent/prompting.py` 改(删 `LOCAL_CODING_SYSTEM_PROMPT` / `CODING_SYSTEM_PROMPT` / `DEFAULT_SYSTEM_PROMPT` / `_DEFAULT_TOOL_SPECS` 常量,`build_system_prompt` 函数若无引用则删,保留 `build_chat_messages` 等纯 LLM 消息装配 helper);`core/agent/prompt_sections/{base,wiring,core_sections}.py` 改;`core/agent/runtime.py` + `loop.py` 改(snapshot + 切段式 + callback);`platform/bootstrap.py` 改(默认元数据 + MemoryTool 构造);`platform/tools/builtins/memory.py` 改(`_resolve_memory_root`);`products/{personal_assistant,local_coding}/profile.py` 改(`default_system_prompt = ""`,或显式去掉字段);`products/{personal_assistant,local_coding}/prompts.py` 删整文件;`products/personal_assistant/prompt_sections.py` 删 `pa.memory_intro`;`core_sections.py` 删 `core.runtime_tools` + 新增 `core.user_profile_block`;`personal_assistant/config/local_store.py` 改 seed 位置;`tests/contract/test_no_hardcoded_workspace_dirname.py` 新增;受影响测试套件全面更新 | `[reviewer]` 覆盖 spec.md 4 条 Requirement 全部 9 个 Scenario(Req-1 跨 session memory 三个 / Req-2 不退化两个 / Req-3 工具与 provider 三个 / Req-4 preview 一致一个);`[worker]` `pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e"` 全绿;`[worker]` 新增 contract 测试在 src 下 grep `.nano`/`.nanoassistant`/`.nanocode` 只命中 product `defaults.py`;`[worker]` `core.memory_block` / `core.user_profile_block` 段在 memory_curation on + workspace + dirname 齐备时激活,在任一缺失时失活 — 单测覆盖;`[worker]` `derive_memory_root` 单测覆盖 PA / LC 两种 dirname;`[worker]` MemoryTool 写入与 runtime freeze 读取从同一物理路径 — 集成测试覆盖 |

### 单 M1 的理由

按 §4.2 拆分门槛核查:
- 跨独立模块可真并行 — ❌ 改动集中在 `core/agent/` + `platform/bootstrap.py` + `platform/tools/builtins/memory.py` + 两个 product,模块间紧耦合
- 工作量超出单 worker 窗口 — 估算 ~600-800 行(改动跨 10-12 文件,但大部分是机械替换:删常量、改函数签名、调用方更新),临界但单 worker 可承担
- 必须分阶段验证 — ❌ memory 闭环 + section assembly 切换 + MemoryTool 隔离修复语义紧密,任一独立做都不可观测(memory 修了 segment 装配没切等于没修;段式切换没接 memory 等于把 memory 段从 None preview 状态搬到 None runtime 状态,没有用户价值)

→ 默认单 M1,反向门槛触发不到。

### 不拆的另一个理由

按 §4.4 退出标准试金石:每个 milestone 都必须"独立可部署的子系统 / 用户视角能观察到的能力变化"。本 unit 任何子部分单独发布都不达上述标准:
- 仅 MemoryTool 隔离修复 → 用户看不到效果(读不到 memory)
- 仅段式切换 → memory_block 仍是 None,无变化
- 仅删 `## Available Tools` → token 略省,但用户无感

只有三件事一起完成,用户才看到 spec scenarios 描述的"agent 跨 session 记住事"+"工具仍正常调用"等观察。

