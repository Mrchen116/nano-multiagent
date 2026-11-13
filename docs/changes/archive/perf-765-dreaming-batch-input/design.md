# perf-765: As-built Design

本文在实现后根据实际代码、用户反馈和隔离对照整理。

## 实现范围

- Base `4b4c43229`，原实现及 Skill 同步截至 `bc9d93942`，审查修正见 review.md。
- 涉及 dsh-integration 的 Dreaming 与文档记忆，以及 personal-assistant 的内置 nano-memory Skill。没有纳入其他未提交改动。

## 调用链与关键决策

1. `memory-sources.ts` 在 Global 和子任务两条取材路径调用 `batchToolResult`。有真实 History 定位的普通工具结果最多保留 8,000 UTF-8 字节，保留首尾、裁剪标记和定位。Inbox、conversations、send_message 及无法可靠回查的记录保留原样。整批选材仍处理剩余材料和来源游标。
2. `dreaming.ts` 将入选主轨迹和任务摘要、来源目录、角色及首页组装为首轮输入。 `dreaming-agent.ts` 按 UTF-8 边界切为至多 8,900 字节的文本块，作为同一用户消息交付，按实际组装形状估算输入。整合可通过 source_history 回查获准原始来源，维护会话换窗通过 history 恢复原始输入。
3. `memory-documents.ts` 负责记录起始提交，检查仓库状态、根入口和支持的文件形态，观察实际保存与提交。宿主向同一整合会话反馈待修复项，最多三次。正常结束后仍存在仓库问题时，宿主尝试恢复起始提交、还原 tracked 文件并清理本批新增的未跟踪文件。普通模型失败、取消和来源失效保留实际状态。本批成功后才登记来源进度。
4. `nano-memory/SKILL.md` 与首轮输入、定点回查和宿主 Git 恢复行为对齐。

## 兼容性和失败边界

既有来源和任务摘要缓存继续按来源版本与资格使用。旧运行记录仍可查看。此次未引入一次性部署迁移。恢复 tracked 文件以起始提交为准，已有的暂存或未暂存 tracked 修改也会被还原。宿主如实报告恢复未完成。

## 验证

- 同一冻结来源、同一起始记忆、同一真实模型的隔离重放，基线 `4b4c43229` 对候选 `aebf07378`。两组均成功提交，来源游标推进相同，主要事实保留。
- 模型请求 111 → 66，工具调用 242 → 118，总 token（含缓存及压缩）14,636,417 → 8,551,377，耗时 39:27 → 22:22。14 → 15 页变更。两版对旧页的后续状态提示位置有差异，均可从导航找到现行状态。
- 单次对照，未控制服务端缓存。使用历史快照，两组均以相同方式把原先超长首页末段移到链接页。此批没有子任务摘要，子任务裁剪另用自动化测试验证。工作台反馈和收尾授权来自本次对话。
- 本机证据目录 `zen-dreaming-ab-20261113.p629Ke`，摘要见该目录的《验收对照》。真实模型运行资源已回收，私有证据保留供复核。
- 独立代码和 Context 审查及最终自动化验证见 [review.md](review.md)。

## Canonical 文档影响

[Delta-spec](specs/gateway/agent-capabilities.md) 对应 [Gateway Agent Capabilities](../../../specs/gateway/agent-capabilities.md) 中 Dreaming 整理行为。
