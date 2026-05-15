# M2-memory-skill-store-tools — Progress

## Summary

本 milestone 实现 core/memory/（MemoryStore）、core/skills/（SkillWriter 写侧）、两个 builtin 工具（skill_manage / memory）、resolver.user_memory_root()。

---

### R1 — core/memory: MemoryStore CRUD + 文件锁 + 原子写 + 来源索引

- Context: spec L60（两固定文件）、L61（来源索引）、R5（并发写安全）要求设计 MemoryStore。hermes 参考 §5 确认了 § 分隔符、fcntl 文件锁、原子写（fsync + os.replace）模式，但 hermes 的条目格式是纯文本（无来源索引），需要在此基础上扩展 source comment 格式。
- Decision: 每条目在文本后追加 `<!-- source: {"session_id":..., "timestamp":...} -->` 注释行；锁粒度为 .lock 文件 + fcntl.LOCK_EX；写入时整文件重写（in-memory 为权威）；字符限制以序列化后总长度计算。
- Rationale: source comment 格式对 review agent 透明（不影响文本内容展示）；整文件重写保证串行一致性；同目录 tempfile 确保 same-filesystem rename。
- Evidence:
  - Tests: 18/18 通过。覆盖 add/replace/remove/read/persist/reload/format_for_prompt/char_limit/atomic_write/invalid_target。
  - Entry: N/A（纯 core 逻辑，无 HTTP 入口，R4/R5 的工具层测试覆盖真实入口）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（纯后端单元）
  - Visual/Interaction: N/A
- Rollback: 回退到 plan commit 9536a373
- Commits: C1=eb5b87d7, C2=521a2edd, C3=（本条记录所在提交）
- Next: R2 — SkillWriter 写侧

### R2 — core/skills: SkillWriter create/edit/patch + 校验 + cache 失效

- Context: hermes §4 确认 name regex `^[a-z0-9][a-z0-9._-]*$`、frontmatter 7 条规则、100k char 内容上限、原子写模式。design 决策 R6 明确本项目不做 security scan。`SkillRegistry` 需要扩展 `invalidate_cache()` 方法。
- Decision: `SkillWriter` 写侧 + `SkillRegistry.invalidate_cache()` 扩展；name 校验、frontmatter 校验（name/description 字段 + body 非空 + description ≤1024）、内容大小 ≤100k。
- Rationale: hermes 已验证这套校验逻辑足以防止模型写出无效 skill；atomic write 与 R1 一致。
- Evidence:
  - Tests: 31/31 通过。覆盖 create/edit/patch/name regex 8 case/frontmatter 5 bad/good name/content 太大/cache 失效。
  - Entry: N/A（纯 core 逻辑，R4 工具层测试覆盖真实入口）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 回退到 R1 C3 20642fc8
- Commits: C1=a1908015, C2=23c85ef3, C3=（本条记录所在提交）
- Next: R3 — resolver.user_memory_root()

### R3 — platform/config/resolver: user_memory_root()

- Context: design 决策 3 要求 memory 目录走 ConfigResolver 解析（不硬编码），路径 `<workspace_root>/<workspace_config_dirname>/memory/`，无 workspace 时返回 None。
- Decision: 在 `workspace_config_root()` 基础上追加 `/memory` 子目录；无 workspace 则返回 None，调用方按需处理。
- Rationale: 复用现有 workspace_config_root() 逻辑，改动最小；与 user_skill_roots() 的 workspace 路径模式一致。
- Evidence:
  - Tests: 6/6 新增测试 + 9/9 原有 resolver 测试通过。覆盖 PA profile、LC profile、无 workspace、无 dirname。
  - Entry: N/A（纯路径逻辑）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 回退到 R2 C3 599f9866
- Commits: C1=316bf4e6, C2=44d0d5b0, C3=（本条记录所在提交）
- Next: R4 — skill_manage tool

### R4 — platform/tools/builtins/skill_manage: Tool 包装

- Context: design 决策 5 要求 skill_manage 作为 platform 层薄包装调用 core/skills SkillWriter。hermes §4 确认 schema：action ∈ {create,edit,patch,delete,write_file,remove_file}。本项目不做 delete/write_file/remove_file（设计简化），保留 create/edit/patch/view/list。
- Decision: `SkillManageTool` 接受 `skill_root + registry` 注入；`run()` 捕获所有 ValueError 返回 `{"success": False}`；`__init__.py` 导出 SkillManageTool 和 MemoryTool（但不加入 builtin_tools() 默认集合，M3 负责注册）。
- Rationale: 工具不应抛异常——LLM 工具结果用 success/error 字段，而非 Python exception；M3 负责路径解析和注册符合分层职责。
- Evidence:
  - Tests: 19/19 通过。覆盖 create/edit/patch/view/list/duplicate/无效参数/unknown action。
  - Entry: N/A（工具层，M3 集成测试覆盖 HTTP 入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 回退到 R3 C3 417e2ea6
- Commits: C1=4354c803, C2=91f5edd3, C3=（本条记录所在提交）
- Next: R5 — memory Tool

### R5 — platform/tools/builtins/memory: Tool 包装

- Context: hermes §5 确认 schema {action: add|replace|remove, target: memory|user, content, old_text}，无 read action（通过 system prompt 注入读取）。本项目在此基础上扩展 source index（每次写入从 ToolContext 读 session_id + 当前时间）。memory_root 从 ToolContext.session_metadata["memory_root"] 解析（M3 注入），fallback 到 workspace_root 或 cwd。
- Decision: `MemoryTool(memory_root=None)` 构造（可固定 root 用于测试）；run() 每次创建新 MemoryStore 实例（无跨调用 state，保证并发安全）；serialize_result 输出 JSON 或错误字符串。
- Rationale: 每次 run() 创建新 MemoryStore 而非缓存：MemoryStore 内部已处理磁盘读取，工具层无需维护状态；这也确保并发工具调用不共享 in-memory 状态（工具是无状态的）。
- Evidence:
  - Tests: 21/21 通过。覆盖 add/replace/remove/两 target/§ 分隔符/source index/only-two-files/unknown action/memory_root from metadata。
  - Entry: N/A（M3 负责 HTTP 入口集成）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 回退到 R4 C3 25ed5499
- Commits: C1=59355117, C2=e989dda9, C3=（本条记录所在提交）
- Next: milestone 完成，准备合并到 unit/feat-349

<!-- 每个 roadpoint 完成后追加 -->
