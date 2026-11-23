# Nano Change Units

通用目录、编号、文件归属、Relations、活动状态和归档规则见 [Change Unit Storage](https://github.com/Mrchen116/dev-workflow-skills/blob/main/docs/changes/README.md)。阶段与门禁从 [Nano 开发流程](../development/change-workflow.md) 进入。

本仓活动 unit 位于 `docs/changes/<unit>/`，达到交付标准后整目录移入 `archive/`，决定不再按原计划完成的工作见 [退役索引](retired/README.md)。被替换的独立文档另存于 [docs/archive](../archive/README.md)。

## 命名与编号

先 `git fetch origin`，按 [Nano 分支规则](../development/change-workflow.md#开发基线与-pr-目标) 核对本地与远端现有 unit。定位已安装的 [change-spec-author](https://github.com/Mrchen116/dev-workflow-skills/blob/main/skills/change-spec-author/SKILL.md) 实际源码目录，从 Nano 仓库根目录执行：

```bash
python3 /path/to/dev-workflow-skills/skills/change-spec-author/scripts/next_unit_id.py <type>
```

脚本在当前 Git clone 的 worktree 间原子保留编号，迁移后继续尊重已有的 `<git-common-dir>/nano-multiagent/change-unit-ids` 记录。跨机器碰撞按 [通用编号约定](https://github.com/Mrchen116/dev-workflow-skills/blob/main/docs/changes/README.md#命名与编号) 处理。

## 一次性部署提示词

需要由部署 Agent 将旧数据、配置或目录状态一次性迁移到新设计时，固定使用 unit 根目录的 `deployment-prompt.md`，从 `design.md`（lite 为 `fix.md`）链接。无迁移需要不创建空文件；归档时随整个 unit 保留，不因进入 archive 而失效。

提示词须写清：

- 旧状态、目标状态、适用版本/环境/对象范围，以及目标实现已具备的前提；仅有设计或提示词不代表可执行。
- 执行时机与服务停启、配置写回的先后关系；必要备份、最小修改步骤、必须保留的数据和无关配置。
- 完成判据与验证方法、中断后的继续方式、失败恢复方式，以及如何依据部署记录和现场状态避免重复执行。
- 区分隔离环境中的功能/幂等性/失败恢复验证与正式环境的有限迁移结果核对；生产默认只读，不把发送消息、生成卡片或完整功能回归列为例行部署要求。确有不可替代的生产验证时写明必要性、对象、次数与停止条件，并遵循 [生产验证边界](../../.claude/skills/prod-fleet-deploy/references/runbook.md#生产验证范围与停止条件)。

每项验证注明执行环境和直接完成判据；隔离验证引用目标版本的证据或写入交付前的验收安排，生产核对限定所需计数、不变量或小样本及观察截止条件。生产例外验证须单列必要性、对象、最多次数、停止条件与明确授权状态，不能仅写“按部署授权完成真实验收”。没有写入式生产测试不应成为迁移完成的缺项；迁移本身的数据完整性和健康条件仍须满足。

这份文件保存部署要求，不单独授权操作生产；在用户授权部署包含该实现的版本时，由 [prod-fleet-deploy](../../.claude/skills/prod-fleet-deploy/SKILL.md) 发现并遵循。一次性历史整理不转化为冗余的产品启动迁移或长期兼容代码；正常产品行为仍由实现负责。执行环境、版本、对象范围、备份位置和结果写入受保护的本地部署记录，不把秘密或原始生产数据写回 unit。

## 历史迁移

根目录旧 `TASKS/`、`PROGRESS/`、`ACCEPTANCE/` 已停止接收新内容并整体迁入 [`docs/archive/legacy-development-records/`](../archive/legacy-development-records/README.md)。旧 milestone id 只代表当时的 TDD control-tower 流程，不能机械映射成 change unit。
