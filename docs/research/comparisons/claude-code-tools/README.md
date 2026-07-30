# Claude Code Tool Comparisons

> 状态：Research snapshots；对当前缺口的判断等待
> [`D-004`](../../../changes/refactor-486-agent-native-repository-knowledge-system/drift-review.md#d-004claude-code-tools-比较材料仍把已经实现的能力写成缺口)
> 裁决。
>
> 上游 Claude Code commit：当时未记录，不能用当前 checkout 反向代填。

| 页面 | 记录日期 / nano commit | 当时研究的问题 | 当前核实入口 |
|---|---|---|---|
| [`architectural-gaps.md`](architectural-gaps.md) | 2026-04-18 / `f07e9d7f` | 跨工具共性缺口 | `src/agent/platform/tools/`、kernel specs |
| [`bash.md`](bash.md) | 2026-04-18 / `f07e9d7f` | Bash schema、执行和权限 | bash builtin、background-task spec/tests |
| [`edit.md`](edit.md) | 2026-04-18 / `f07e9d7f` | Edit schema 与写入保护 | edit builtin、tool tests |
| [`read.md`](read.md) | 2026-04-18 / `f07e9d7f` | Read schema、分页和类型 | read builtin、tool tests |
| [`write.md`](write.md) | 2026-04-18 / `f07e9d7f` | Write schema 与覆盖保护 | write builtin、tool tests |
| [`task.md`](task.md) | 2026-04-18 / `f07e9d7f` | 子 Agent 接口与后台执行 | agent builtin、background-task spec/tests |
| [`read-dedup-design.md`](read-dedup-design.md) | 2026-04-18 / `211d86d0` | Read mtime 去重设计 | context state 与 read tests |
| [`session-file-state-design.md`](session-file-state-design.md) | 2026-04-19 / `e42d70e4` | 会话级文件状态设计 | context state、read/write/edit tests |
| [`web_fetch.md`](web_fetch.md) | 2026-04-20 / `2be76c27` | Web Fetch 对比与阶段设计 | web_fetch builtin、权限/运行测试 |
| [`web_fetch-prompt-processing-design.md`](web_fetch-prompt-processing-design.md) | 2026-04-20 / `2be76c27` | prompt-based 内容处理 | web_fetch builtin 与测试 |

旧正文保持记录时的观察。若用户确认某项仍是期望缺口，再建立 issue/change；已经进入 current 的能力由代码、
tests 和 [`../../../specs/kernel/`](../../../specs/kernel/spec.md) 承担。
