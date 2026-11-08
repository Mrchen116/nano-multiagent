# bugfix-729: Review

## 范围与版本

- 需求及修复依据：[fix.md](fix.md)。Bugfix lite，单个 M1-fix。
- executed_base：`0e7b7cb16`；独立 full validated_at：`bfc49d640614e56a7bf8b2cd08f4d51b3571a4a1`；closure validated_at：`2c39df4e3b1890430758b0863bfbc63f680067e3`。
- 独立审查者：`/root/review_ui_summary`，gpt-6.1-sol / high；未参与受审实现。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 无摘要 UI 发送、PA 双身份、权限/审核/幂等、最终契约 | change-code-review，独立 reviewer，full + closure | pass | 33 文件完整 diff 与调用方；closure 后无存活 finding，最终 delta aligned |
| 模型获得一致指导与公开 UI 内容 | agent-context-review，作者自检 + 独立非视觉静态核对 | pass（声明范围） | 真 DSH adapter 受控 wire 及动态 Skill 后续请求，真实模型实际无摘要卡片；原生单线程/Inbox 回归。无远端 provider raw 请求日志，不声明该层输入验证 |
| UI 自身足以阅读，不重复外部摘要 | frontend-experience-review，作者实施自检 | pass（显示/刷新） | 真实模型生成的完整解释/比较/趋势 UI，正文为空，刷新仍可读；客户端115项窄回归与1078项全量。原生设备未实测，CUA 滑块联动未取得决定性结果，不纳入通过结论 |

## Findings 与关闭

- F1，P2 CONFIRMED：`apps/im-server/src/messaging.ts:512`。HTTP body 的 `interactive:null/false/空字符串/0` 被非 undefined 条件误当作有效内容，存储又跳过假值 UI 校验，持久化空消息。独立临时 fixture 4/4 复现。
- Author resolution：`2c39df4e3` 与存储分支统一为 truthiness 判断，空消息不再借假值绕过；truthy 非法 UI 继续进入原有 decoder/preflight。永久回归放在已有 `interactive-messages.test.ts`。
- 独立 closure：`bfc49d640..2c39df4e3`，核对修前失败、修后15/15通过；F1 closed，无新 finding，保留完整审查的其他结论。

## 流程收口

- 最终 delta：aligned；UI-only 交付、正文可选、空消息拒绝、公开 UI 接收和原权限边界均有对应实现及证据。
- 有效范围与未验证项见 fix.md；不把原生编译、受控 provider、浏览器显示或组件回归混称完整双端真实旅程。
- 全量 Web 1078/1078、Python 135/135、build/typecheck/runtime生成、ruff 与文档检查通过。后端全量实际1183 passed / 1 failed，唯一失败是全量运行中新增并在旧 guard 下加载的 F1 红测；最终定向15/15通过，其他216文件保留。记录跨版本边界，不声称原全量命令成功。
- 最终同步 `origin/develop=0e7b7cb16`，无新增源码；source effective_through `2c39df4e3`。之后仅补证据和归档，不使既有实现/契约结论失效；PR 元数据另记录最终 head。
- 原生源码本轮仅改失败提示文案；本地 generic Simulator 双架构编译通过；未把编译称为原生 UI 实测。远端 iOS gate 随 PR 执行。未 merge、未部署。


## 验收证据更正（2026-11-09）

首轮会话标题“无摘要 UI 验证”及旧工作目录带有目标暗示，撤回其自然行为证明；保留其成功发送/显示的窄结论和原件。用户原话、混淆因素、中性环境补测及证据边界统一记在 [fix.md](fix.md#验收证据更正2026-11-09)。源码与原有独立代码审查/CI 未变，不由一次中性场景外推稳定采用率。


补测独立复核：`/root/review_ui_summary`，gpt-6.1-sol / high，读取5份实际 pre-adapter 请求、observer 源、公开消息及受测 Skill。未发现额外目标提示或输入改写；确认仅一条 UI 公开消息、实际参数省略 text、回执及持久化 source 一致。该单次中性 case 的声明范围通过，原污染 case 继续排除。产品指导本身是被测实现，不能用此结果证明没有新版指导时也会自然如此。

本次后续只更正验收记录与 PR 描述；产品源码、Skill、构建输出与已审契约未改，原代码审查及源码 CI 的结论保留。中性环境因用户请求查看效果而保留，原预览同样继续运行；两个环境各自端口、node、owner、数据和 workspace 独立。
