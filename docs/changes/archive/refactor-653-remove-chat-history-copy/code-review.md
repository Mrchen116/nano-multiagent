# Code Review: refactor-653-remove-chat-history-copy

## Metadata

- reviewer: independent agent `/root/static_review`；未参与本 unit 设计或实现。
- review_round: `1`
- review_mode: `full`
- executed_base: `c097a63219d5d303526c2ede583df39b6f81ff9d`
- validated_at: `72b2ddb001792f1862764b51ba0d68f5179c61c0`
- checkout: `/Users/czj/.codex/worktrees/remove-chat-history-copy/nano-multiagent`
- branch: `codex/refactor-653-remove-chat-history-copy`
- reviewed_at: `2026-10-25T00:40:57+08:00`
- 范围：完整 base..validated_at diff，包括源码、测试、active delta、内置说明和 operations 文档。开始时 HEAD 精确匹配且 clean。

## Verdict

**Pass — no surviving findings.** 未发现具有具体可触发场景与后果的缺陷。

```json
[]
```

## Coverage and evidence

1. **所有副本写入与触发均已移除。** `history.ts:93-102` 构造函数不再注册 session/event；`:244-261` 完成原生 fork、配置事实与持久化后直接返回，不调用导出；`index.ts:283-287` 启动安装 bindings 后不再 recoverExports。原正文投影、append/stat/rebuild、水位、raw 标志及恢复方法全部删除。`rg` 核对 integration/node/PA 产品源码：chat_history/recoverExports 无存活引用，queueExport 只有显式 path 入口。没有保留隐含开关、替代自动导出或清理旧文件的行为。
2. **既有事实与真实消费者保留。** 配置/fork domain、配置快照和 fork 前后 flush 保留；`index.ts` 的 session.fork/session.export 路由及 binding 校验没有改变。PA `src/history.ts:152-175` 继续显式请求 session.export 并把路径交给提炼 Skill。Agent context 的 notes/history/new_context/get_context_remaining 与原生 DSH 会话恢复独立于退役目录；没有发现读取该可读副本的恢复或模型 context 接线。
3. **原始完整切面与延迟读取。** `history.ts:263-300` 保留版本头和全部原生事件，live 在 flush 前捕获 seq，随后读取固定半开区间；prepared observation 使用其固定冷切面，若 query 实际返回 live 则重新取得 Session 并 flush。与锁定 DSH 公开 README 的 seq/snapshot、flush 和 observation.source 契约一致。完整临时写后 rename 仍是唯一发布路径，普通聊天不改变已发布原始文件，失败不把旧路径当新成功结果。
4. **队列简化的并发与失败语义。** `history.ts:302-331` 每 id 单任务合并显式 pending 请求，串行同名临时文件，不同 id 独立。失败且有新显式请求时继续下一轮；无新请求时抛出。finally 删除已完成任务；删除和新 job 的建立之间没有 await，不会误删同 id 的新任务。path 等待整个任务；stop 在配置写入后等待当前队列任务。新增普通 turn 不再触发失败重试，符合删除副本后的目标。
5. **回归保护适当重写。** `history-export.test.ts` 保留 7 项：普通轮次零导出写入/无副本、显式快照、忙队列/跨会话、固定持久上界、发布失败保留旧文件并仅显式重试、冷导出保留旧副本、失败期间新增显式请求、冷查询转 live 的屏障。`history.test.ts:188-217` 改为验证原始 fork 前缀与隔离、无新副本、重启/继续聊天时旧字节不变；native-human-source 仅删除退役正文投影断言，原生来源/权限验证保留。没有删除仍需要的原生恢复保护，也没有新增平行测试文件。
6. **证据复用与限度。** 复用 [M1-remove/progress.md](M1-remove/progress.md) 与 caller 提供的结果。独立读取 `/tmp/refactor-653-export-test.log`：Vitest 4.1.11，00:39:41，1 文件/7 tests passed（最终队列释放简化后）；`/tmp/refactor-653-native-test.log`：00:39:32，真实 DSH history/native-human-source 与 PA history 共 3 文件/6 tests passed。测试使用真实临时文件与真实锁定 DSH subprocess（模型为 fixture）。没有把测试通过扩大为生产、UI 或真模型验收。
7. **文档与 scope。** 两处内置说明不再暗示可读副本存在；operations 一次性迁移保留历史步骤与旧文件保留边界，删除过时的“新 chat history”验收。逐文比对 delta 的真人 envelope Requirement：仅删去副本正文承诺及其专属 Scenario，其余 8 个 Scenario 与原文一致。原始导出 delta 的 5 个 Scenario 与实现匹配，REMOVED 明确删除旧副本 Requirement。current canonical 尚未归并是已知收尾步骤，不当作隐含继续生成副本的要求；归并时还应同步 Gateway 索引的覆盖摘要和计数。

本轮未执行额外测试、全量 CI、服务或生产操作，未修改源码、测试或设计，未派子任务。独立产品验收和最终全量 CI 由 orchestrator 分别记录；本报告只判定指定 diff。report_commit: N/A，按派发仅写报告、不提交。
