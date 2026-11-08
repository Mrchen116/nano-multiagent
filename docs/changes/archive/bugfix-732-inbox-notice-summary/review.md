# bugfix-732: Review

## 范围与版本

- 用户要求与实现记录：[fix.md](fix.md)；单 milestone M1-fix。
- executed_base：`94d663626299b2cd69c99e9740d0c3e6607b2574`。
- 初轮 validated_at：`06241aebb9743f8ce07acf81055f53c192de3597`。
- 修正 closure validated_at：`39e9b140fc733252d168deab164bfbdcaa5114b8`。
- 名称路由 patch validated_at / effective_through（最终产品树）：`2c99cfb0d988d41bcaf30c39a2fcc699975c8c99`；effective_base 仍为 executed_base。最终 fetch 无新增 develop 增量；其后仅记录/归档，相关结论 retained。
- 独立审查者：Codex subagent `inbox_summary_review`（gpt-6.1-sol / high），未参与实现，使用 change-code-review 与 agent-context-review。

## 审查结果

| 问题 / 要求 | 能力与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 会话名称、未读数、实际 @、短引用可直接 read，移除强制 check | 独立 Code + Context 实施审查 | pass（closure 后） | 完整 diff、生产 IM/PA 来源、Global ingress、describe、references、read/prepare/commit；最终专项 34 files / 293 tests passed |
| 模型请求/工具执行中多消息合并；后续批次再次提醒 | 独立 Code + Context 实施审查 | pass | reviewer 独立运行 native 合并、busy send、PA background：3 passed / 1 skipped；DSH pending coalescing 未变 |
| 摘要不消费正文、发送前复核、观察背景关系和期限 | 独立 Code + Context 实施审查 | pass | native 受控 llm/stream 捕获与现有 PA/Global 全套；旧草稿 held，正文按需，observer/participant 与十分钟期限保持 |
| 最终 Global / PA current delta | 独立 corrected-delta | aligned | closure 对照实际修正与契约；`39e9b140f..2c99cfb0d` 的三文件 patch 独立通过，mixed IM/external describe 按拥有者路由分组，corrected-delta retained aligned |

证据只证明真实 DSH 子进程中的确定性装配与行为，捕获点为受控 llm/stream；未验证真实模型选择、provider wire、Token 节省量或生产端到端。

## Findings 与关闭

- R1-P2 / CONFIRMED：初轮 Inbox 直接按 `mentioned_agent_ids` 计 @，但生产卡片回复也并入该字段，导致误报。作者新增独立显式提及数据，完整覆盖 IM relay、PA observation 与 Global ingress，原寻址/唤醒字段不变。旧持久卡片没有显式字段时计零；Workflow 系统返回明确无显式提及。服务与 Inbox 回归覆盖后，独立 reviewer 在 `39e9b140f` 定向 closure 确认 closed。无存活 findings。

## 本地检查

- 最终专项：34 files / 293 tests passed；IM 卡片与 PA 来源、整个 personal-assistant 及 native Inbox。
- 完整 workspace build（含本地 installer candidate，未发布）、typecheck、iOS TypeScript runtime、文档完整性：通过；显式提及修正后受影响包重建与最终 typecheck 通过。
- Python：135 passed / 28 deselected；ruff check 与 format 通过。
- 前端：113 files / 1078 tests passed；critical audit 通过。
- 最终路由修正后：native Inbox / Global / PA attention / relay admission 四文件 67 tests passed；其余 293 项结论对应未变路径 retained。
- 完整后端不是绿：首轮在修正期间运行，出现目录临时检查进程清理、workspace-tools 超时、model setup/policy 等失败；该轮也曾加载修正前构建而运行修正后两项 IM 断言（两项最终已在 293 tests 中通过）。不把这轮作为冻结树完整验证；已停止该被后续提交取代的全量运行。三项目录/插件单独复验为 1 passed / 2 failed / 14 skipped（capabilities 临时检查清理失败、workspace-tools 120s 超时），没有修改这些链路或宣称本地全量绿。最终 PR CI 另行核对。
- 原始本地日志保存在 `/Users/czj/.codex/reports/bugfix-732-inbox-notice-summary/`，不提交运行日志。

## 流程收口

重要目标与最终 delta 已获独立通过，最终相关检查通过。全量本地失败如上保留，限定本次范围，不为目录/插件故障扩大实现。归档后创建 develop PR 并核对远端 CI。没有迁移、生产部署或合并授权。

## PR 反馈 patch

- validated_at：`a1085e6bff546e09dcfef7509b9040eafa40b670`；patch base `05696b6fc`，executed_base / effective_base 仍为 `94d663626`。
- 独立 reviewer `inbox_summary_review` 对 3 文件 delta 的 code + Context patch 审查通过，无 findings；通知仅移除 requires_attention 和指定短语，PA 两字段保留，无 spec delta。内部 check/触发/持久状态未改，原聚合、读取、消费及发送复核结论 retained。
- 受影响包重建、完整 native Inbox 文件 4 tests passed（15.21s）。之前 `05696b6fc` 的远端完整 CI 通过；本 patch 推送后的 CI 独立运行，不将旧绿状态表述为新 head 已通过。

## PR 反馈：所有 Global 提供会话类型

- validated_at / effective_through（产品树）：`d1d0ad5e81501052727f083f93878f7dafb3eb13`；patch base `a06014597`，executed_base / effective_base 仍为 `94d663626`。
- 独立 `inbox_summary_review` 对 5 文件 code + Context patch 审查通过，无 findings；conversation_type 来自原入站元数据，所有 Global 一致提供 direct / group，PA 额外保留 delivery，提醒继续过滤 requires_attention。
- corrected-delta aligned；Global spec 两处增量与实现一致。聚合、消费、短引用和发送复核链路未改，原结论 retained。
- 受影响包重建、32 files / 270 tests 与文档完整性检查通过。最终 push 仅在产品提交之后补审查记录，新 head CI 单独运行。
