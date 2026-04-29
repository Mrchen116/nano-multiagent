# 模板使用说明

按变更类型选模板复制到 `docs/changes/<type-id>/`。

| 变更类型 | 根目录文档 | 每个 milestone |
|---|---|---|
| feat | `spec.md`, `design.md`, `acceptance.md` | `tasks.md`, `progress.md` |
| refactor / perf | `motivation.md`, `design.md`, `acceptance.md` | `tasks.md`, `progress.md` |
| bugfix lite | `fix.md` | `tasks.md`, `progress.md` |
| bugfix full | `incident.md`, `regression.md` | `tasks.md`, `progress.md` |

## 填写硬约束（违反 = 打回）

1. **原始需求/原始报告必须原样保留**。不要改写、翻译、概括。粘贴用户原话或截图。
2. **澄清是交互式的**。`spec.md` / `incident.md` / `motivation.md` 的"澄清记录"段未与用户对完前，**禁止**生成下面的"用户场景/验收标准/根因/目标状态"等结论性内容。一轮一轮问，每轮记录 Q/A。
3. **不要越界**。每份模板顶部 `<!-- 模板说明 -->` 块写明禁止讨论什么。最常见越界：在 `spec.md` 阶段问"用什么库、放在哪个模块"——这些属于 design。
4. **可自由发挥**。模板只列**必填骨架**。鼓励额外加：模块拓扑图、时序图、对比表、状态机、附录、示例对话等——任何让读者更快理解的内容都欢迎。骨架是地板不是天花板。
5. **定稿后删除模板说明块**。`<!-- 模板说明 -->` 注释在文档稳定后删掉，避免噪音。
6. **关联其他 unit 用 Relations**。详见 `../readme.md` "变更单元之间的关联"。

## 给 agent 的提醒

如果你正在填写 spec/incident/motivation 而想问"用 SQLite 还是 JSON / 走 SSE 还是 WebSocket / 放哪个模块"——**不要问**。这些属于 design。在 spec 阶段只问能改变"用户感知"的问题。
