# bugfix-527: 自动 Skill 历史选择与来源修正

## Relations

- Related: feat-349
- Related: feat-446
- Related: feat-502
- Related: feat-519

## 原始报告

> 这个问题先别管。**历史状态异常**：两个自动生成的 Skill 原先可用，后来没有保留在显式名单中。
> **来源记录错误**：自动生成的 Skill 被记录成了 F1 手工创建。
>
> 这两个是明确问题对吧。先解决这两个。“两个自动生成的 Skill 原先可用，后来没有保留在显式名单中。”这个是为啥

> 所以以后自动生成的是不是就会在allowlist中？我想问这是之前历史遗留的问题，还是说新代码还有问题

> 如果新代码没问题，直接改下数据库就行，不用改代码

> 对

## 澄清记录

- Q1: 是否同时把现有两个 Skill 的来源记录从 `F1` 回填为 `F3`？
  A(原话): 对
  Agent 解读: 只回填已经由运行日志确认来自后台自动 Review 的 `remote-host-health-check` 与 `forall-prod-machine-status`，不扫描或改写其他历史 Skill。

## 现象 / 复现

2026-08-03，`forall` 的两次“看看两个机器啥状态”会话分别达到后台 Skill Review 阈值。LLM Bridge 原始响应显示，两个后台 Review 随后分别调用 `skill_manage(action="create", scope="agent")` 创建：

- `remote-host-health-check`；
- `forall-prod-machine-status`。

两者创建时，`forall` 尚未保存非空 Skill 名单，按当时的默认发现语义立即可用；使用记录显示它们随后各被成功读取四次。之后保留下来的配置从空/缺席名单演变为只含 PA 全局内置 Skill 的非空名单，两个工作区 Skill 不在其中。旧版本按“空名单为默认发现、非空名单为显式 allowlist”推断选择意图，因此它们退出该 Agent 的有效 Skill 集合。当前设置页如实显示 `WORKSPACE 0/2`。

现有生产备份能证明：2026-08-03 的 `forall` 配置尚无持久化 Skill 名单；2026-08-06 已变为只含 `nanoassistant-docs` 与 `lark-doc` 的非空名单；2026-08-09 前又扩为完整 PA 全局内置 bundle。第一条全局 Skill 由哪个历史入口写入已无配置操作审计可查，不能继续归因。2026-08-10 的配置操作只把既有非空名单显式标记为 `explicit_allowlist`，没有在该次操作中删除两个工作区 Skill。

当前版本已经用独立的 `skills_selection_mode` 区分默认发现与显式 allowlist。聚焦回归确认：成功创建 Skill 会产生 `skill_created` 事件；事件能到达 Gateway handler；`default_discovery` 由发现机制立即看到新 Skill；`explicit_allowlist` 会把新名称追加到名单。因此“生成后退出名单”是该 Agent 的历史持久状态，不是当前 Allowlist 代码缺陷。本单只修复 `forall` 的确认状态，不增加扫描式自动启用，不扩大其他 Agent 的显式名单。

第二个现象仍可在当前代码稳定复现：后台 self-improvement Review 调用 fork 时没有声明 `skill_creation_source=F3`；fork 只继承父会话 metadata 并补 `run_origin=background_task`。`skill_manage(create)` 建立使用记录时读取不到来源字段，遂按默认值 `F1` 持久化。因而自动 Review 创建的 Skill 在统计中被误报为手工从零创建。

## 根因

历史选择异常来自旧选择模型的表达能力不足，而非当前创建链失效：旧配置只有 Skill names，没有独立的选择模式。创建时的空/缺席 names 表示“按发现集合全部可用”，后续任何把它写成非空子集的配置变化都会同时把语义收窄为显式 allowlist。两个自动生成 Skill 只依赖默认发现生效，并未物化进 names，因此在该历史收窄中被排除。feat-519 已用 `skills_selection_mode` 消除这项歧义，并要求创建事件在默认模式下保持发现、在显式模式下追加名称。修复必须保留显式 allowlist 的权威性，不能把磁盘上所有既有工作区 Skill 扫描式补回。

来源错误来自 F3 意图没有贯穿后台 fork 的创建边界。Skill 生命周期原本区分 F1 手工创建与 F3 per-turn 自动 Review 创建；但现有实现只在使用记录层消费 `skill_creation_source`，没有由 self-improvement 生产者向 fork metadata 写入 `F3`。现有测试分别覆盖 Review 触发、`skill_manage` 来源消费和 Skill 使用统计，却没有覆盖“后台 Review → fork → create → usage record”的来源贯通，所以默认 `F1` 未被发现。

修复必须同时满足：未来仅由 Skill 自动 Review 创建的记录标记为 `F3`；memory-only Review 不虚构 Skill 来源；其他普通 fork、用户创建和历史蒸馏语义不变；现有两个已确认记录只做定向回填。

## 修复

实施阶段回填。

## 验证

实施阶段回填。
