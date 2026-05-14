# M2-memory-skill-store-tools — Tasks

## 目标

实现 `core/memory/`（`MemoryStore`）、`core/skills/` 写侧（`SkillWriter`）、两个 builtin 工具（`skill_manage`、`memory`）、`platform/config/resolver.py` 新增 `user_memory_root()`。

## 退出标准（来自 design.md Milestone 表）

- `skill_manage` 的 create/edit/patch 正确落盘到 `<workspace>/.<ns>/skills/` 且触发发现 cache 失效
- `memory` 的 add/replace/remove 作用于 `memory`/`user` 两 target，`§` 分隔 + 每条目带来源索引、文件锁 + 原子写
- name regex / frontmatter / 大小上限校验生效
- 两工具 + store 单测全绿

## 测试策略

后端纯逻辑 + 工具 API，无前端交互。

- **R1（MemoryStore）**：单元测试覆盖 add/replace/remove/format_for_prompt/文件锁/原子写/来源索引
- **R2（SkillWriter）**：单元测试覆盖 create/edit/patch/校验/cache 失效
- **R3（resolver.user_memory_root）**：单元测试扩展 test_config_resolver.py
- **R4（skill_manage tool）**：工具层单元测试
- **R5（memory tool）**：工具层单元测试

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | core/memory/: MemoryStore CRUD + 文件锁 + 原子写 + 来源索引 | DONE |
| R2 | core/skills/: SkillWriter create/edit/patch + 校验 + cache 失效 | DONE |
| R3 | platform/config/resolver: user_memory_root() | DONE |
| R4 | platform/tools/builtins/skill_manage: Tool 包装 | DONE |
| R5 | platform/tools/builtins/memory: Tool 包装 | DONE |

## UI 状态矩阵

N/A（纯后端）

## 浏览器验收

N/A（纯后端）
