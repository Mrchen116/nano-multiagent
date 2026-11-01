# Nano Memory：逐项研究后的修订方案（v2）

日期：2026-10-28。设计文件，不是已经实现的运行系统。

本包修订此前 nano-memory-v1 与 Nano-Memory-统一方案中关于入口模板、目录、cases 和 Dreaming 输入的部分；不是要求一次性推翻既有 Memory、Task 或上下文引擎。

## 阅读顺序

1. [逐项决策](01-decisions.md)：本轮每个疑问的证据、取舍与决定。
2. [证据与边界](02-evidence.md)：竞品原文、代码、用户调研之间的区别。
3. [目录与文档规范](design/layout-and-documents.md)。
4. [Global Dreaming](design/global-dreaming.md)：调度、历史摄入、换窗、失败恢复。
5. [实现检查单](design/implementation-checklist.md)。

## 可直接交给本地 Agent 的材料

- templates/entry/PA.MEMORY.md：PA 的常驻入口模板。
- templates/entry/SPECIALIST.MEMORY.md：独立专家的常驻入口模板。
- templates/documents/：按用途区分的正文模板，不是统一事实表。
- prompts/：共同读写规则、PA／专家差异规则、记忆整理作业规则。
- skills/nano-memory/SKILL.md：按需读取的组织与更新方法。

## 约定

记忆位置固定为 `<长期 Agent 已有 workspace>/.nanoassistant/memory/`。模板是产品素材，不把整个本包复制进每个 Agent 的记忆。按可信角色选择入口，替换占位符、去除解释性注释，无依据的栏目不填。当前 Markdown 是可见知识；Git 用于版本，不另设隐藏事实权威。只用普通工具消费正文，必要的写入保护由宿主实现。

已核对 Nano main `a5724f2124acc345783f5b91f293f62204881902` 的上下文接入与依赖，锁定的 dsh-agent-context 为 `v0.3.0-rc.5`。未运行 Nano，不声称所有历史适配接口或行为验收已完成。
