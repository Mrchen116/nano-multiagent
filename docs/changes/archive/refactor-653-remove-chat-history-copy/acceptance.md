# refactor-653-remove-chat-history-copy — 验收报告

> Round 1；mode=full；2026-10-25（Asia/Shanghai）
>
> executed_base: `c097a63219d5d303526c2ede583df39b6f81ff9d`
>
> validated_at: `72b2ddb001792f1862764b51ba0d68f5179c61c0`

## Verdict

**pass**。blocking / major / minor = 0 / 0 / 0；Highest Required Action: pass；needs_re_review=false。

## 用户旅程体验与实际范围

运行前确认指定 HEAD 与干净工作树；按 caller 要求使用 Node 24.22.1 执行全仓 `pnpm build`，退出码 0，再运行本 worktree 新构建的 RuntimeClient。未重复全量 CI。

按批准 Runbook，通过真实 DSH 的 initialize、session.ensure、submit、lookup、observe、fork、export、shutdown 及重启接口驱动。fixture 只提供确定性模型回复，关闭 intelligent_ui、task_graph、memory_curation、skill_creation；无外部模型、生产服务或消息外发。直接读取原始导出和 workspace 文件系统，不以自动测试通过代替产品观察。

两轮聊天、分支和重启后继续对话均完成；原生历史可查询，分支原始文件包含正确继承前缀和独立新增消息。用户不再看到自动生成的可读副本，手工预置的旧文件保持原字节，符合本次取消维护而不删除历史的目标。原始导出返回的路径可直接读取；延迟读取仍为完整旧切面，显式刷新得到新内容。无客户端变更，视觉评价及 viewport N/A；不声称真实模型质量、PA 提炼 Skill、UI 或生产已验收。

## 实际观察证据

### E1：普通聊天及新 workspace

隔离 home/cwd `refactor653-review-udnY8g`，会话 `acceptance-source`。依次提交 REVIEW_ONE（含有效 2×2 PNG）和 REVIEW_TWO，各次 lookup terminal=completed。查询真实第二轮 assistant message id 供后续 fork。两轮后 `.nanoassistant/chat_history` 的 stat 返回 ENOENT；显式导出后仍 ENOENT。

实际原始文件逐行 JSON 解析成功，共 25 行；头为 `type=nano-dsh-history, version=1`，内嵌原生 header version=4、id=acceptance-source。再完成 REVIEW_AFTER_POINT，原路径全文与先前导出逐字节相等，证明普通聊天没有刷新原始快照。

### E2：fork 和独立增长

从第二轮真实 assistant message fork，分支 id `session-21b532de-0db0-4612-a56c-32782d111b8a`，完成 REVIEW_BRANCH 并显式导出。实际文件 36 行，包含 REVIEW_ONE、REVIEW_TWO、REVIEW_BRANCH，不含源分支点后的 REVIEW_AFTER_POINT。此时整个可读副本目录仍不存在。

源会话随后完成 REVIEW_SOURCE_AGAIN；源 observe 不含 REVIEW_BRANCH。原会话和分支均保持可用。

### E3：旧文件冻结与原生重启恢复

在隔离 workspace 手工创建 `.nanoassistant/chat_history/acceptance-source.jsonl`，内容为 `legacy copy\nUNCHANGED` 加末尾 NUL，字节 hex=`6c656761637920636f70790a554e4348414e47454400`。继续源聊天及显式导出后，该文件逐字节相同。

正常 shutdown，再以原 bindings initialize/ensure。源 observe 仍含 REVIEW_ONE 和 REVIEW_SOURCE_AGAIN；随后源与分支分别完成 REVIEW_RESTART_SOURCE、REVIEW_RESTART_BRANCH。分支重新导出 46 行，保留 REVIEW_ONE 和 REVIEW_RESTART_BRANCH，不含 REVIEW_RESTART_SOURCE 或 REVIEW_AFTER_POINT。源重新导出含 REVIEW_RESTART_SOURCE。

每一步检查旧文件字节不变，目录清单始终仅 `acceptance-source.jsonl`，没有创建分支可读副本；最终 shutdown 后也相同。恢复没有读取或重写这份人为内容的旧文件。

### E4：失败保持旧快照，显式重试成功

保留已完成分支原始文件，在其 `.tmp` 路径创建目录阻断发布准备。session.export 返回 `RpcError: EISDIR: illegal operation on a directory, open ...jsonl.tmp`，没有返回成功路径。失败后旧原始文件与此前逐字节相等。移除临时障碍并显式请求，成功返回可读取路径，全文与已完成切面相等；旧可读副本及目录清单仍不变。

本轮驱动退出码 0。两次隔离运行均正常 shutdown，finally 删除自己创建的 home/cwd；临时驱动及结果记录在证据归入本报告后删除，没有遗留服务。

## Reference Artifacts Reviewed

N/A：无视觉原型或 must-match。已读 motivation、design Runbook、delta 与 current routing-delivery 相关条款；current 仍描述旧副本生成，需按下方收尾归并。

## 问题清单

无；未创建外部 issue。

## 验收标准覆盖

| 来源 / Scenario | 验证方式与证据 | 结果 |
|---|---|---|
| motivation：普通聊天及重启 | 真实连续 submit/observe、shutdown/initialize 后继续原会话；E1、E3 | pass |
| motivation：fork 后继续并导出 | 从真实消息 fork，读取实际原始文件并比较前缀/源分支隔离；E2、E3、E4 | pass |
| delta：连续轮次导出完整且不重复 | E1、E2，成功读取完整原始 JSONL，workspace 无副本 | pass |
| delta：延迟提炼读取完整原始快照 | E1 逐字节稳定；E3 再次显式导出包含新消息 | pass |
| delta：分支导出包含自己的完整历史 | E2、E3 | pass |
| delta：导出失败后显式重试 | E4 | pass |
| delta：重启不维护旧可读副本 | E3，旧字节和目录清单均保持不变 | pass |

delta 真人 envelope requirement 中其余来源时间、飞书、shadow、群聊、用户正文、旧历史、非 PA 入口场景沿用当前契约且不属于本 unit 行为增量；本轮未声称实测这些通道。已删除的可读副本 requirement 以 E1–E3 的不生成/不修改结果验收。并发与持久化切面底层测试由 worker 证据承担；本轮原子发布的产品观察限于延迟完整文件读取和失败保留旧文件，未以 UI 或存储系统内部取证扩大结论。

## 上层文档同步

- [x] `SPEC.md`：无需更新，跨包架构和原生事实源未变化。
- [x] `docs/specs/gateway/routing-delivery.md`：需要 orchestrator 按 delta 收尾归并；目前 current 仍保留生成可读副本条款。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

按 caller 要求只写本报告，不改源码、测试、设计或 canonical 文档，不提交。report_commit=N/A，交主 Agent 集中交付。
