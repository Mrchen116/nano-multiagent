# bugfix-431: runtime skill resolution 与 preview 不一致

## Relations

- Related: refactor-406 (preview skill resolver 已修同源，runtime 调用点漏同步)
- Related: feat-385 (preview/runtime system prompt 同源主题)

## 原始报告

> http://127.0.0.1:8011/settings/agents/product-manager 明明 system prompt preview 中带了一堆 skill，但是 LLM proxy 中 logs/session/2026-06-24_10-33-51_136_sess_6a330eb47fbaac98/2026-06-24_10-33-51_136-req-anthropic_messages.json 为啥就一个。agent 给我分析：原因是 runtime 和 preview 走了两套 skill resolver。
>
> 我查到的事实：
> - `product-manager` 在 IM DB 里确实保存了 12 个 skill： `change-design-author`、`change-orchestrator`、`change-impl-worker`、...、`systematic-debugging`、`skill-creator`。
> - 这条 LLM proxy log 也确实是 `product-manager` 的 session： `Current working directory: /Users/czj/nano-assistant/workspace/product-manager`
> - 但实际发给模型的 `<available_skills>` 里只有： `/Users/czj/.codex/skills/.system/skill-creator/SKILL.md`
>
> 根因在代码上是：
> - Preview 路径在 src/agent/sdk/kernel.py 里用了 `_WorkspaceDirnameSkillResolver`，会查： `<workspace>/.nanoassistant/skills` + `~/.nanoassistant/skills` + `~/.claude/skills` + `~/.codex/skills`
> - 真实运行路径在 src/agent/core/agent/runtime.py 里调用： `resolve_available_skills(..., config_resolver=self._config_resolver)`
> - 但 `build_kernel()` 构造 `AgentRuntime` 时没有传 `config_resolver`，所以 `self._config_resolver` 是 `None`。
> - `config_resolver=None` 时会退回默认 Codex 搜索路径，见 src/agent/core/skills/discovery.py：`~/.codex/skills`、`<workspace>/.codex/skills`、`<workspace>/.nano/skills`。
>
> 所以真实执行时，它只在默认 Codex roots 里按 `product-manager.skills` 过滤。12 个里只有 `skill-creator` 在 `~/.codex/skills` 里找得到，其他通过 `~/.nanoassistant/skills -> repo/.claude/skills` 暴露出来的 PA skills 没被 runtime resolver 看见。
>
> 结论：不是你配置错了，也不是软链没生效；这是一个 bug：**capabilities/preview 已修到 PA resolver，真实 runtime skill resolution 漏修了同样的 resolver 注入。**

## 澄清记录

- Q1: 这个 bug 的修复范围是只覆盖 personal_assistant，还是也要覆盖 coding_cli 的 runtime skill resolution？
  A(原话): 你问问题之前能不能带着脑子先分析下 CLI 哪有 preview？
  Agent 解读: 范围只覆盖 personal_assistant。preview 是 IM 配置页功能，只有 PA 有；CLI 不存在这个对比维度。

- Q2: 修复后的成功标准，是不是"agent 真实对话时 `<available_skills>` 里出现的 skills，与 IM 设置页 system prompt preview 中展示的 skills 完全一致"？
  A(原话): 是，并且两者应该同源，不能是两个完全独立的实现，否则以后小改动又不一致。
  Agent 解读: 成功标准是 runtime skill resolution 与 preview 同源，不能是两套独立实现。

- Q3: 如果 IM 配置里保存的某个 skill，在磁盘上实际不存在，runtime 应该怎么处理？
  A(原话): ok
  Agent 解读: 与 preview 一致，对不存在的 skill 名静默忽略。

## 现象与复现

1. 在 IM 设置页给 `product-manager` agent 勾选 12 个 skills（含 `change-design-author`、`change-orchestrator`、`change-impl-worker`、…、`systematic-debugging`、`skill-creator`）。
2. 打开该 agent 的"系统提示词预览"，展开后能看到这 12 个 skills 全部被列出。
3. 和该 agent 进行真实对话，查看 LLM proxy 请求日志：
   - `Current working directory: /Users/czj/nano-assistant/workspace/product-manager` 确认是同一 agent；
   - 实际发给模型的 `<available_skills>` 段里只有 `/Users/czj/.codex/skills/.system/skill-creator/SKILL.md`，其余 11 个 skill 均未出现。
4. 结果：preview 展示的技能集合 ≠ runtime 真实注入系统提示词的技能集合，agent 运行时看不到用户配置的大部分 skills。

## 影响范围

- **受影响用户**: 所有在 IM 配置页给 PA agent 勾选 skills 的用户。用户以为 agent 已经具备这些 skills，实际运行时大多不可用。
- **受影响产品**: `personal_assistant` Gateway 路径。`coding_cli` 不存在 preview 场景，但 `build_kernel` 构造 `AgentRuntime` 的调用方式同样未传 resolver，只是 CLI 的技能集合与 PA 不同，暂未触发相同症状。
- **严重程度**: 中高。功能未按配置生效，属于配置与实际行为不一致，导致 agent 能力缩水。
- **数据损坏**: 无。skill 文件本身未丢失，只是 runtime 未发现它们。
- **根因横跨模块**: `agent.sdk` (`build_kernel` / `_WorkspaceDirnameSkillResolver`)、`agent.core` (`AgentRuntime._resolve_session_available_skills`)、`agent.platform` (`SkillRootResolver` / `resolve_available_skills`)。

## 根因分析（RCA）

### 表面：runtime 和 preview 用了两套 skill resolver

- **Preview 路径**（已正确）：`src/agent/sdk/kernel.py:assemble_prompt_preview` 使用 `_WorkspaceDirnameSkillResolver`，搜索根为 `<workspace>/.nanoassistant/skills` + `~/.nanoassistant/skills` + `~/.claude/skills` + `~/.codex/skills`，能解析到全部 12 个 skills。
- **Runtime 路径**（错误）：`src/agent/core/agent/runtime.py:_resolve_session_available_skills` 调用 `resolve_available_skills(..., config_resolver=self._config_resolver)`；但 `build_kernel()` 构造 `AgentRuntime` 时未注入 `config_resolver`，`self._config_resolver` 恒为 `None`。
- `config_resolver=None` 时 `src/agent/core/skills/discovery.py:default_skill_search_roots` 回退到默认 Codex roots：`~/.codex/skills`、`<workspace>/.codex/skills`、`<workspace>/.nano/skills`。12 个 skills 中只有 `skill-creator` 落在 `~/.codex/skills`，其余 11 个通过 `~/.nanoassistant/skills → repo/.claude/skills` 暴露的 PA skills 均不可见。

### 为什么这种错能进来

1. **ConfigResolver 退役后的 dead field**：`refactor-406` 解散 `agent/products/`、退役 `ConfigResolver` 后，`AgentRuntime.config_resolver` 字段未同步移除；新 2 层路径下没有任何地方给它赋值，于是恒为 `None`。
2. **M3fix 只修了 preview 症状**：`refactor-406-M3fix #3`（commit `2ec7b059`）发现 preview 因 `runtime._config_resolver = None` 导致技能段空白，于是把 preview 改为使用 `_WorkspaceDirnameSkillResolver`。但同一调用链上 runtime 的真实路径 `_resolve_session_available_skills` 没有被同步修改。
3. **缺少端到端同源测试**：现有契约/单测没有覆盖"preview 中展示的技能集合 = runtime 真实 LLM 请求 `<available_skills>` 集合"这一端到端场景，导致 preview 与 runtime 分歧拖到线上才暴露。

### 原始设计意图

- `refactor-406` 设计决策 4 明确 Kernel 提供中立 `list_skills(workspace_root)` 查询，PA 工厂通过 `build_kernel(skill_search_roots=...)` 传入部署级共享 roots。
- `refactor-406-M3fix #3` 注释明确：preview 必须与真实会话同源，使用 `_WorkspaceDirnameSkillResolver`（per-call workspace_root + 部署 skill_search_roots）。
- 因此修复必须保住的不变量：
  - **runtime skill resolution 与 preview 必须同源**，不能是两套独立实现；
  - **不能复活 `ConfigResolver`**（`refactor-406` 明确决策）；
  - **kernel 保持 product-neutral**：只搜索 `build_kernel` 被告知的 roots，PA 工厂继续负责传正确的 `skill_search_roots`。

## 修复方向

1. **统一 resolver 来源**：让 `AgentRuntime` 在 2 层路径下也持有一个与 preview 同源的 skill resolver。最自然的做法是在 `build_kernel()` 构造 `AgentRuntime` 时，注入一个由 `workspace_config_dirname + skill_search_roots` 构成的 `SkillRootResolver`（复用 `src/agent/sdk/kernel.py` 的 `_WorkspaceDirnameSkillResolver`），替换掉当前恒为 `None` 的 `self._config_resolver`。
2. **保持现有调用点不变**：`AgentRuntime._resolve_session_available_skills` 与 `_resolve_session_available_skills_from_config` 已经调用 `resolve_available_skills(..., config_resolver=self._config_resolver)`，只需保证注入的 resolver 正确，无需重写调用逻辑。
3. **补同源回归测试**：新增端到端测试，断言"对同一 agent 配置，preview 渲染出的 skills 集合 = runtime 真实 LLM 请求中 `<available_skills>` 的 skills 集合"，防止未来两边再次漂移。
4. **清理 dead field 或明确语义**：视实现复杂度，考虑移除 `AgentRuntime.config_resolver` 这个已退役的字段，或将其语义改为 `SkillRootResolver`，避免继续误导后续维护者。
