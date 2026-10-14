# bugfix-602: 补齐任务工具调用描述

> 快速开发事后记录；active。实现、真实 Agent 验证及独立 code review 已完成，用户亲测确认尚未发生，未归档。

## Relations

- Related: feat-569、refactor-581、feat-584

## 原始报告

用户原话：

> 任务工具容易试错的问题，分析根因，并和/Users/czj/Repos/opensource-hub/raft-source学习他们怎么做

确认快修范围的原话：

> 把调用规则补进工具及参数描述，那你也让subagent通过快修的形式改下，这个要实际验证实际agent是否确实能理解并遵循，可能要多轮调整。

用户已明确要求实施和真实 Agent 验证。系统提示词暂时不改；不改变任务业务语义、ACL、事务、审批默认或 provider 实现。没有补造需求澄清或用户验收。

## 现象 / 复现

原实玩主 Session `7ff87cba-e056-48de-b63d-26daa143752b` 保存三步计划时，先 `create` 夹带 `operations`，再 `apply` 缺 `change_note`，随后用裸 `client_ref` 连边，连续得到三次业务拒绝；第五次写调用才完成正常的 create + apply 路径。前几次边的方向也写反，成功调用才纠正。

原调用的真实模型为 `deepseek:deepseek-v4-flash`。原请求下发的 schema 只有 `action` 必填；三份错误参数都可通过该 JSON schema。当前源服务的隔离重放得到相同拒绝，失败没有半写入或重复节点。

## 根因

工具 description 没说明 create 只建根节点、复杂计划须随后 apply。五种动作的字段摊在一个 schema 中，未说明每动作必填/可选/禁止混用；`change_note` 没有 apply 必填说明。`@client_ref` 曾在 operations 长段中出现，但定义与引用字段缺就近解释，示例也没有连边。from/to 只写了兄弟节点约束，没写前置→后续方向。

原任务图意图来自 feat-569：讨论后保存、渐进更新 DAG/探索结构，不根据图自动调度。current 契约是 [Gateway task graphs](../../specs/gateway/task-graphs.md)。本修复保留稳定图/节点 ID、资源归属、变更说明、原子 revision 和幂等契约。现有 DSH schema 迁入定位为 `129b083613`；本次未据此断言该问题是相对更早实现的新回归。

## 修复

只修改两个文件的七处 description 字符串：工具 description，及 action、change_note、operations、client_ref、from、to。action 给出五动作字段矩阵；operations 提供两个节点及正确方向连边示例；定义名不带 @、引用带 @，且只引用本批此前已创建的节点。

系统提示词原文保持。JSON schema 的类型、枚举和 required、工具名和 allowlist、服务端与审批实现均不变。当前非 strict Anthropic 转换裁掉根级 oneOf/if；因此本轮不加入无法传达的根条件 schema，也不引入 DSH patch 或新工具架构。

## 验证

- 第一版文案即通过三个独立 global Agent 的真实 IM→Node→DSH→模型→任务服务路径；每例干净 Session/workspace/knowledge，没有在用户任务里教授工具语法。三例各一次 create + 一次 apply，参数拒绝均为 0，SQLite 持久图均为一根、三子节点、两条正确方向依赖。
- 实际 LLM_PROXY 请求逐例核对七处文案均存在，task system prompt 与原实玩完全一致。
- 原图增量修改结果、session/graph IDs、验证命令与证据入口见 [M1-fix/progress.md](M1-fix/progress.md)。真实 Agent 实测不等于用户亲测；尚无用户确认。
- `pnpm build`、独立 Web 标准构建、任务权限/capabilities/IM 协作聚焦测试均通过。没有新增锁死文案的永久测试；保留既有权限/持久状态覆盖，本次真实模型检查作为运行证据。

## 收尾状态

主会话派发独立 full code review 已通过，findings `[]`，详见 [code-review.md](code-review.md)。PR/CI 由主会话交付；用户确认尚未发生，canonical delta 归并与归档保留待完成。未合并或部署。
