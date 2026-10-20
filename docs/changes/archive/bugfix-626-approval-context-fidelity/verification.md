# Verification Report: bugfix-626-approval-context-fidelity

## Round 1

### Metadata

- reviewer: `/root/static_review`，独立于实现。
- verification_mode: `full`，同时核对当前 delta reconciliation。
- executed_base: `b5c1e97901467767a32efc66e83869181242f477`
- validated_at: `40cd54ddf81c5c7262d1d2f69cb83b5dd3287bad`
- reviewed_at: `2026-10-20T15:14:15+08:00`
- requires_full_verification: `false`；待补项可针对动态证据续验，前提是冻结产品树不变。

### Summary

| 维度 | 结果 |
|---|---|
| Completeness | 实现及确定性回归已覆盖；M1 动态验收和收尾 CI 尚未完成证据闭环 |
| Correctness | 已检查的 Requirement/Scenario 与实现一致，无确认实现偏离 |
| Coherence | 遵循 Gate 2 修订后 design；受限宿主适配有明确依据 |
| Verdict | 静态核验通过；Full unit 尚不能宣布所有退出标准完成 |

当前 1 CRITICAL（未完成的退出证据），0 WARNING，0 SUGGESTION。CRITICAL 是门禁状态，并非已确认代码缺陷。

## Completeness

唯一 M1 已实现普通审批取数撤销、CC 既有边界保留、Codex profile/admission/output 对齐、来源规范化与去重。简化流程不要求 worker tasks/progress；`M1-fidelity/implementation.md` 有受影响测试 keep/rewrite-merge/extend 处置和适配依据。

已读取 `/tmp/nano-626-red.log` 与 `/tmp/nano-626-red-context.log`，分别存在旧额外授权/污染及 parser、profile、来源、恢复反例失败；green focused 23 项与 final context 15 项通过。全量 `pnpm test` 对应 `/tmp/nano-626-full-tests.log` 已完成 106 files / 476 tests passed。窄测结果有重叠，不相加作独立样本数；未重复运行全量。

M1 所需真实模型 PA 旅程尚未交付报告；完整本地等价 CI、最终 canonical 归并和远端 CI 在本报告快照也没有完成证据。原型/前端 reference：N/A，本次不改客户端。

## Correctness

| Requirement / Scenario | 实现位置 | 回归和证据 | 状态 |
|---|---|---|---|
| 长期 PA 历史不放大普通工具审批 | `src/policy/approval.ts:127`，`classifier.ts:14`，`codex.ts:73`（均位于 dsh-integration） | `personal-security.test.ts:9` 两策略原生 DSH fixture：巨量数据库哨兵不进 prompt、额外取数为 0、允许/禁止动作与发送屏障；red/green 日志 | 静态/fixture covered；真实旅程待补 |
| 主会话压缩后沿用有效历史 | `src/policy/sources.ts:131`，`codex.ts:67`，`codex-context.ts:86` | `approval-sources.test.ts:86` 保留原生 PTC root 条件；`codex-approval-lifecycle.test.ts:26` 父历史改写不残留旧授权 | covered |
| CC Inbox 原话与实际发送来源 | `src/policy/sources.ts:7`、`:145`、`:177`；CC 规则资产无 diff | `approval-sources.test.ts:34`、`:68`、`:102`；实际 sent/held、私稿、可信来源/恢复均覆盖 | covered |
| Codex 连续动作、父更新及预算压力 | `src/policy/codex-context.ts:86`；`codex.ts:66`、`:83`、`:116` | `codex-approval.test.ts:18`、`:29`、`:37`、`:47`；lifecycle/native 测试的 delta/fork/rebuild/取消/真实 90 秒 | covered |
| Codex 来源与去重 | `src/policy/sources.ts:21`、`:175`；`codex.ts:66` | `approval-sources.test.ts:34`、`:137`：每消息、恢复、distinct call、正文单次；上游 User/Tool/ProtectedAssistant 映射对照 | covered |
| Codex output 与完整 action | `src/policy/codex-context.ts:10`、`:87`；新增 output asset | `codex-approval.test.ts:8`、`:18`：bare allow/deny、embedded、默认值、非法类型、动作放不下失败 | covered |
| PA 外部直接请求/observer | `packages/personal-assistant/src/personal-assistant.ts:62`；`global-agent.ts:193` 无 diff | 既有 personal-assistant/personal-attention 测试保留在已通过全量内；独立 input review 与 observer 路径仍分开 | 静态/回归 covered；真实接线待补 |
| PA 私人工作/主人 DM/其他受众 | `src/policy/approval.ts:117`（dsh-integration）；`apps/im-server/src/personal-actions.ts:86`、`:104`、`:120` 无 diff | `personal-assistant.test.ts:33`、`:42`、`:77`、`:143`；最终提交屏障及原授权取证保留 | 静态/回归 covered；真实接线待补 |

## Coherence

| design 决策 | 核对结论与代码依据 |
|---|---|
| 1 撤销普通审批额外证据 | 一致；入口/request/transcript/action 和专用说明均已移除，PA 自己的取证接口保留 |
| 2 CC 固定规则与 Inbox 适配 | 一致；CC 资产未改，默认 sources 不应用 Codex per-message 投影，失败分流未改 |
| 3 profile 与 final admission | 一致；`codex-context.ts:90-129` 与固定 profile/enforcement 对照。所有选中 assistant 均为 ProtectedAssistant；消息裁剪保留 origin 与正文首尾 |
| 4 复用及预算恢复 | 一致；delta preserve，fresh/rebuild 可 recovery；实际剩余窗口与原生请求 guard 保留，删除 0.65 缩放。上游 fresh parent checkpoint 明确使用 Allow，非首次全量必先失败 |
| 5 必要宿主限制 | 一致；沿用 DSH 原生 Agent 公共接口，工具仅 host-owned stat/read/list。文件效果只读不等于网络/进程隔离；未开放 shell，不声称 ThreadOwned/Independent/预测机制 |
| 6 输出 prompt/parser | 一致；与上游 assessment 默认值、包装支持、invalid type 失败对照。DSH 无公开 schema 参数的限制明确记录 |

仅 dsh-integration 源码/测试和规则资产变化，没有越过 PA/Channels/IM 依赖边界，没有 private runtime import、额外执行循环或数据库迁移。PA 独立检查仍可能受自己的全量证据体积影响，本 unit 不宣称解决它。

## Issues

### CRITICAL

- C1 — `design.md:104` 的 M1 全部退出标准尚无完整动态/收尾证据。静态和 fixture 不能证明 CC/Codex 两次真实 PA 文件操作确实经过分类器、实际文件和最终交付成功，也不能替代非主人 participant/observer/主人 DM/外发四类独立接线的产品观察。由独立产品 reviewer 完成并附 classifier source、输入规模、产物及交付证据；收尾 owner 补齐 build/typecheck、其余适用本地 CI 与远端 CI 结果。在此之前保持 active，不将本报告的静态通过写成 Full 门禁全部完成。若只有证据追加，可保留本静态结论并定向关闭 C1，无需重复全量。

### WARNING

无。

### SUGGESTION

无。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| 普通工具审批当前有效上下文 / PA 长期历史 | `approval.ts:127`、`classifier.ts:14`、`codex.ts:73` | `personal-security.test.ts:9` 两策略 | aligned |
| 主会话压缩后延续 / CC 与 Codex 各自规则 | `sources.ts:131`、`codex-context.ts:86`、`codex.ts:83` | approval-sources PTC/恢复；codex lifecycle/profile/admission | aligned |
| PA 消息安全独立 | 保留 `personal-assistant.ts:62` 与 `personal-actions.ts:120`；普通入口删除注入 | 既有 PA/IM 与 personal-security 回归 | aligned |

### Uncovered Observable Behavior

无遗漏的独立产品行为：Codex parser/profile/admission 的恢复是上述固定策略要求的实现展开，PA 入站/外发没有策略变更。受限调查和 Legacy 宿主边界已在 design 中披露。

Outcome: `aligned`。canonical 归并 owner 可直接采用已核对 delta；若之后校正改变其语义或增加未覆盖行为，再针对实际 delta 复验。最终同步 main 后的 effective_base/effective_through 由收尾 owner 记录，本报告不预先声称有效到未知集成树。

## Round 2 — 定向证据闭环与集成树保留

### Metadata

- verification_mode: `targeted-closure`；focus: Round 1 C1、canonical reconciliation、用户新增仅审核生产轨迹。
- executed_base / effective_base: `ff5fbc8f52ca1f4fb098f1e62d906c845895f990`。
- validated_at / effective_through: `7dce653ef393e5fac8cb242b5cf92ddeff363a20` 加当前 canonical/实施证据文档差异。
- 产品验证版本仍为 `40cd54ddf81c5c7262d1d2f69cb83b5dd3287bad`；独立检查产品源码、测试、规则资产没有变化。
- reviewed_at: `2026-10-20T15:24:24+08:00`；requires_full_verification: `false`。

### Verdict

**本地 gate pass：0 CRITICAL / 0 WARNING / 0 SUGGESTION；C1 closed。** 完成归档和创建 PR 的前置验证；远端 CI 为 `awaiting remote CI`，属于创建 PR 后的门禁，不作为归档前的循环阻塞。Round 1 将本地动态证据和远端 CI 合写为 C1，本轮按 workflow 的先归档、再 PR、再远端 CI 顺序校正其阶段归属。

### Closure evidence

| 核对项 | 实际证据 | 结论 |
|---|---|---|
| 同 PA 的 CC/Codex 真实普通文件任务 | 独立产品 reviewer `M1-fidelity/regression.md`，`f9bc24aaf`；已记录实际文件、IM 持久化回复、两次 `bash/classifier_allow`、模型请求与百万字符旧库哨兵不进入审核 | covered；有明确版本、方法、定位和限制，保留独立产品判断 |
| PA 非主人 participant / observer / 主人 DM / 外发接线 | 同产品报告六类 Scenario 对账、独立 input/action 代理请求、receipt/群消息及独立检查记录 | covered；既有 PA 检查没有被普通审批替代；503/已持久化配置观察未冒充成功响应且后续 Codex 真实成功 |
| 压缩、预算、fork、取消 | 冻结版本确定性 native/lifecycle 测试与 476 项全量 | retained；没有把 fixture 说成真实模型压力验收 |
| 本地等价 CI | 已读 `/tmp/nano-626-{build,typecheck,full-tests,python,ruff,docs}.log` 完成结果；后端 476、Python 62/31 deselected、ruff/check/format、docs；Web build/test/audit 日志：936 tests，critical audit 通过（存在 5 项 low），iOS 路径不适用 | covered；未重复已有效的全量 |
| 新增线上原始失败轨迹仅审核 | `M1-fidelity/production-replay.md`；私有目录的 driver、两原始前缀、request 计数与 result；独立重算见下 | covered，仅限离线真实模型审核回归 |
| canonical 归并 | `docs/specs/gateway/agent-capabilities.md` 当前 diff 中新增 Requirement/三个 Scenario 与已审 delta 的正文精确匹配 | aligned，无新行为遗漏或语义扩张 |
| final sync | `b5c1e9790..ff5fbc8f5` 只增加 feat-625 design-review 文档；集成 HEAD `7dce653e` 的产品树与 `40cd54ddf` 相同 | Round 1 代码/契约/回归结论 retained |

### 生产轨迹回放的独立核对与边界

独立以结构相等比较确认两个 JSON 的 header、全部事件前缀、待审 action 均直接来自私有原始 session；截点最大 seq 分别是 6223/6358。输入文件 SHA 与报告相符。通过锁定 DSH public export 独立 `Session.create` 后 `deriveMessages()` 得到 125/177 条；压缩事件保留，没有改为数据库聊天全文。未运行任何原动作。

驱动 CC 只调用 `classify`，Codex 只调用 `CodexApproval.review`；原 Agent 没有 submit/followup 或 executor 调用，并有工具执行拒绝、product.call 拒绝和主 Agent request 拒绝屏障。两次模型结果分别 allow，记录 input 为 46,451 / 28,304 uncached，toolAttempts=0，未出现工具屏障日志。`mainAgentContinued=false` 和 `actionExecuted=false` 是驱动声明字段，支持依据是上述调用结构及实际零工具尝试，不能把声明字段单独包装成额外遥测。

Inbox live 标记来自启动时间假设下的重建，不是原进程内存快照。两截点启动后 PTC Inbox 数均为 0，未发现因此缺失 live 的已知子调用；直接 Inbox 各 10/19。其余记录仍 restored，身份/会话事实保持。证据支持这两次原失败动作在当前代码和指定真实审核模型下获得有效判定，不能证明任意动作获准、原动作执行、生产已部署或逐字节复现失败瞬间请求。私有原文没有写入本报告。

### Corrected Delta Reconciliation — final

三项 delta 仍全部 `aligned`；实际 canonical 已原样归并，不新增或漏掉用户可观察行为。Round 1 静态一致性保留。当前无未关闭本地 issue；PR 后等待并核实远端 CI，届时若代码变更再按影响复验。
