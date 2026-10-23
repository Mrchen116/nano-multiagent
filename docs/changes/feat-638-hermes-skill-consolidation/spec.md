# feat-638: 迁移 Hermes 的 Skill 内容整理能力

## 状态

仅登记需求。尚未完成全部需求澄清，未进入设计或实施。本文件不定义模块、工具协议、调度方案或 milestone，也不表示 Gate 1 已通过。

## Relations

- Related: feat-349、feat-446、feat-637

`feat-637` 更新已有自进化提示词。本需求独立记录跨多个 Skill 的内容整理能力，不将两项工作合并成一次实施。

## 原始需求

> 懂了，再新建一个需求，迁移Hermes的内容整理步骤过来。只记下需求不设计。然后回到刚刚的prompt修复需求，还有什么要确定的？

## 已确认的需求

- 将 Hermes 的 Skill 内容整理步骤迁入 Nano。
- 本次只记录需求，不开展技术设计或实现。
- Agent 解读：这里的“内容整理”指跨多个 Skill 检查内容、合并相近能力、提炼重复规则和处理被替代的 Skill。它不同于已有的闲置时间扫描，也不同于以单个 Skill 的使用记录为输入的 F4 复盘。

## 背景与依据

- [feat-349](../archive/feat-349-self-evolving-skills-memory/spec.md) 建立对话后的 Skill／Memory 自进化。
- [feat-446 的需求](../archive/feat-446-skill-view-tool/spec.md) 包含确定性扫描和 F4 跨会话内容复盘。
- [feat-446 的设计决策](../archive/feat-446-skill-view-tool/design.md#决策-4-curator-状态机与触发) 明确拒绝 LLM consolidation pass，理由是每个 workspace 的 Skill 数量少。本需求重新提出此前未采用的能力。
- 当前 [确定性扫描](../../../packages/dsh-integration/src/knowledge/files.ts) 按闲置时间标记和归档；[F4 入口](../../../packages/dsh-integration/src/knowledge/runtime.ts) 以单个 Skill 的历史使用记录触发复盘。当前代码未发现独立的全库内容合并流程。
- 本次对话已核对的 Hermes 基线为 `73efa6753de3ec82fbdbf2e4cb6acefdf46531ec`。参考 [agent/curator.py](https://github.com/NousResearch/hermes-agent/blob/73efa6753de3ec82fbdbf2e4cb6acefdf46531ec/agent/curator.py) 中的可选内容整理流程，而不是仅复制确定性扫描。该基线的模型整理默认关闭。

## 需求意图记录

用户长期使用 Agent 后，可能积累多个内容相近的 Skill。希望系统能够识别这些关系，将有效经验整理为更容易查找和复用的技能内容，而不是只按闲置时间归档。

迁移时需要检查的用户可观察结果：

- 相近技能中的有效知识能够保留，重复内容能够减少。
- 整理后的技能及其支持文件仍可使用。
- 用户能够知道哪些技能发生了变化，以及被合并内容的去向。

以上是根据“迁移内容整理步骤”记录的需求意图，不是已经收口的验收清单。正式 Requirement／Scenario 在后续需求澄清后补齐。

## 后续需求澄清事项

后续启动本需求时再确定以下事项，本次不代替用户作答：

- 启用方式、默认状态和用户控制方式。
- 可整理的技能范围，尤其是手工技能、共享技能和用户明确保留的技能。
- 合并后的归档、恢复、依赖引用与结果反馈要求。

Hermes 的固定归档数量要求不自动成为 Nano 的目标要求。后续应根据实际内容和用户目标判断是否需要合并，不把上游实现直接视为已确认的产品契约。

## 与 feat-637 的边界

- `feat-637` 继续处理现有 Memory、Skill、主 Agent 工具指引的提示词更新。
- 本需求单独处理新增的跨 Skill 内容整理能力。
- 不因本次登记修改 `feat-637` 已确认的工具协议范围，也不立即整理或改写现有技能库。
