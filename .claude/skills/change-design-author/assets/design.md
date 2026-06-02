<!--
模板说明（定稿后删除本块）

本文档回答：怎么做（架构 / 接口 / 数据流 / 权衡）。
禁止：用户需求重述（→ spec.md / motivation.md）、行级实现细节（→ 代码）。

实现期发现 design 不完美：
- 只影响当前 milestone：直接改本文 + 在 milestone 的 progress.md 记一笔。
- 影响后续 milestone：必须在下方 Changelog 追加一条，否则后续 milestone 启动时只读 design 会漏掉。

可自由发挥：模块拓扑图、时序图、数据流图、状态机、对比表 —— 凡能让读者更快理解架构的都欢迎。骨架是地板不是天花板。
-->

# <type-id>: <短描述> — 技术方案

> 对齐: spec.md / motivation.md v<n>

## Changelog

<!-- 按时间倒序追加。格式：YYYY-MM-DD (Mx): 一句话 — 详见 Mx/progress.md -->

## 现状分析

<!--
本 unit 启动前对代码仓的调研结果，是后续所有决策的事实基础。
四个子段缺一不可（如某段确实无内容，显式写"无"）：

- **涉及范围**：本 unit 改动会落在哪些目录/文件，它们当前职责是什么。
- **既有约束**：来自 AGENTS.md / 分层规范 / 既有约定的硬约束，决策不能违反。
- **可复用能力**：项目里已经存在的相关实现，明确"用 / 改 / 不用"+ 理由。
- **相关历史**：docs/changes/ 下近期改过同一区域的 unit 及其对本 unit 的影响。
-->

### 涉及范围

### 既有约束

### 可复用能力

### 相关历史

## 架构总览

<!-- 整体形态。强烈建议配 before/after 或拓扑图。 -->

## 关键决策

<!-- 每条：选了什么 / 为什么 / 拒绝了什么备选。 -->

## 接口与数据流

<!-- 对外 API、模块间调用、关键数据结构。 -->

## 契约层增量 (delta-spec)

<!-- §4.8：本 unit 对长青契约层 docs/specs/<包>/spec.md 的增量状态。逐包一行。
     有对外行为变化 → 产 docs/changes/<unit_dir>/specs/<包>/spec.md，这里指向它；
     纯内部无变化 → 写 "no spec delta"。规范见 docs/SPEC_GUIDE.md「契约层增量」。 -->

- kernel: <specs/kernel/spec.md | no spec delta>
- im:     <specs/im/spec.md | no spec delta>
- gateway: <specs/gateway/spec.md | no spec delta>
- cli:    <specs/cli/spec.md | no spec delta>

## 风险与回退

<!-- 已知风险、降级路径、回滚方案。 -->

## Runbook for Reviewer

<!--
必填段。列出本 unit 涉及的所有常驻服务 + reviewer 接管时的启停命令。
reviewer 走旅程前会按这里"无脑重启清单内服务",避免 stale-binary 让证据失真。

约定:
- 只列本 unit 真正改动到的常驻服务,不要把整个产品的所有服务都列上(会误伤其他人的环境)
- 给出"停 / 启"两条命令,确保 reviewer 能照搬执行
- 数据库 / 消息队列 / 第三方依赖等不归本 unit 改的服务不要列
- 如果本 unit 只改前端静态产物 / 文档 / 库代码,没有常驻服务,显式写"无常驻服务"
-->

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
|  |  |  |  |

## Milestones

<!--
每行一个 milestone。默认单 M1；拆分要举证（见 SKILL §4）。子目录数量必须 = 表行数。
退出标准列分两轨，每条标 verifier：
- [reviewer] 用户可观察的能力变化 / 不变性，来自首文档验收标准，reviewer 走旅程验。
- [worker]   实现层验收标准：单测 / 构建 / 性能 / 保真点，worker 在 milestone 内验，
             并会被 orchestrator 抽进 PR body 供架构师 PR review。
-->

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

