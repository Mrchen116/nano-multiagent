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

<!-- 每个 roadpoint 完成后追加 -->
