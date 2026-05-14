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

<!-- 每个 roadpoint 完成后追加 -->
