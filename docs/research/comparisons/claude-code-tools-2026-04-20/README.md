# Claude Code Tool Comparisons — 2026-04-20 Snapshot

> 快照截止日期：2026-04-20。组内页面记录于 2026-04-18 至 2026-04-20，只描述各自记录时的比较结果，
> 不代表当前缺口清单。
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

旧正文保持记录时的观察。若要判断某项今天是否仍是缺口，重新核对 current code、tests 和
[`../../../specs/kernel/`](../../../specs/kernel/spec.md)；确认仍需处理后再建立 issue/change。
