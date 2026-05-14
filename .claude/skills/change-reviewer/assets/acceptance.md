<!--
模板说明（定稿后删除本块）

产品视角验收。问"用户拿到这版能干成事吗"，不是"测试是否通过"。
真实走用户旅程，记看到/听到/触碰到的体验，而非代码路径。

发现的问题按严重度处置：阻塞 → 在本 unit 内补；非阻塞 → 开 bugfix lite。
-->

# <type-id> — 验收报告

> 对齐: spec.md / motivation.md 的验收标准

## Verdict

<!-- pass / fail / pass-with-issues -->

## 用户旅程体验

<!-- 主路径 + 边界路径，截图/录屏/对话粘贴。 -->

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| 1 |  |  |  |

## 验收标准覆盖

<!--
逐条复制首文档的验收标准。结果只能是 pass / fail / inconclusive / not-applicable。
第 2 轮起必须继承上一轮所有 fail / inconclusive 项,直到有证据关闭。
任一必验项 fail 或 inconclusive 时,Verdict 不能是 pass。
若验收项引用原型/设计稿/reference/screenshot/视觉一致性,期望来源必须写对应路径或名称,证据必须包含真实产品截图/录屏/对照结论。
- refactor / perf:验收标准是"不变性",验证方式写"走既有行为,与变更前比对"。
- 若某条验收标准不是用户可观察的(协议/参数/内部函数等实现层条目),标 not-applicable,
  备注"疑似实现层标准,应属 design.md",不要试图验证(详见 SKILL §3.1)。
-->

| ID | 验收项 | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|---|
| A1 | <从 spec.md 复制验收标准> | <spec/design/reference 路径或 N/A> | <真实入口/操作步骤/替代验证理由> | <截图/日志/输出/报告位置> | pass / fail / inconclusive / not-applicable |  |

## 上层文档同步

<!--
本 unit 是否需要回头更新项目级文档？验收阶段必须显式检查，避免知识游离。
不需要改的文档也要勾"无需更新"，证明检查过。
-->

- [ ] `SPEC.md`（架构总览）：__需要更新 / 无需更新__
- [ ] `docs/内核设计SPEC.md`（agent 内核）：__需要更新 / 无需更新__
- [ ] `AGENTS.md` / `CLAUDE.md`：__需要更新 / 无需更新__
- [ ] 相关产品 SPEC（CodingCLI / NodeGateway / IM 等）：__需要更新 / 无需更新__

需要更新的，列出 PR/commit 链接。
