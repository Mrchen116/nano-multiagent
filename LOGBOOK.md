# LOGBOOK (经验 / 预防规则)

- 约定：本文件只记录可复用的经验（坑/风险/预防规则/操作手册），不记录每个 Roadpoint 的实现思路与过程性决策。
- Roadpoint 的方案、证据、回滚点与提交哈希请写到：`PROGRESS/<milestone_id>-<简述>.md`。
- 迁移：历史工作记录已归档到 `PROGRESS/legacy-logbook-work-notes.md`。
- Hook 加载断言规则：涉及 `load_hooks_from_directories` 的测试不要写死“已加载模块总数”，应断言关键模块（source/file_path/event）存在，避免内置 hook 增减引发脆弱回归。
