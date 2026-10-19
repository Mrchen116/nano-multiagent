# Verification Report: feat-616-personal-agent

> Validation snapshot: `e7088f9d5 → cf1befff963e6d251e332c513e8ca6adf1d86619`

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 的主要路径已有实现；恢复契约缺实现，最终真实验收证据未闭合 |
| Correctness | 核心 4 suites / 32 tests 独立通过；3 个具体问题独立复现 |
| Coherence | 官方 DSH / 包边界 / 统一 PA 与受控出口基本遵守；来源入站和分区恢复有实质偏离 |

**Fix before PR：3 CRITICAL / 1 WARNING / 0 SUGGESTION。** 其中第三项 CRITICAL 是尚未完成的 M1 退出证据，不将作者叙述当作完成证明。

- unit_id: `feat-616-personal-agent`
- review_round: `1`
- verification_mode: `full`
- verdict: `fail`
- executed_base: `e7088f9d5`
- validated_at: `cf1befff963e6d251e332c513e8ca6adf1d86619`
- requires_full_verification: `false`（本报告本身已按 full 范围核对；修复后的范围由 caller 按实际 delta 判断）
- reviewer: 独立 reviewer `/root/pa_static_review`，未参与实现。
- 现场：`/Users/czj/.codex/worktrees/feat-616-personal-agent/nano-multiagent`，开始/完成代码阅读时 HEAD 均为候选 SHA、源码无 dirty；未切分支、改源码/测试/设计、启动服务、部署或推送。仅新增本报告和 `code-review.json`；临时探针在 `/tmp/pa-static-review-616/`，没有服务进程。
- 权威：spec 文末目标推进版、统一 PA、新消息/任意历史查询和极简原则；design 当前正文与设计审查 R16 准入。早期逐动作审批、多独立业务 session 与研究快照不作为当前要求。

## Completeness

- Milestone：单 M1，不能标 complete。身份、历史、观察、任务协助、审查/真实回执、受控宿主与 Web 路径已存在；同 owner 恢复缺实现；最终真实产品验收和 W1–W7 部分证据仍待交接。
- Spec：当前 15 项目标版 Requirement 均完成实现映射；下表明确区分已有代码、局部测试与未证明的产品结果，不以测试数量代替完整覆盖。
- Prototype / Reference：design:269–280 的 must-match 表仍适用。静态原型 R15 的既有证明只证明原型；本次不进行主观 UI 验收。真实产品 reviewer 正在独立执行，固定候选尚无可复查的最终真实产品对照报告。

## Evidence

### 本轮独立执行

1. `pnpm exec vitest run apps/im-server/tests/personal-agent.test.ts apps/node/tests/runtime-partitions.test.ts packages/personal-assistant/tests/personal-assistant.test.ts packages/dsh-integration/tests/personal-security.test.ts`
   - 候选 `cf1befff9`，2026-10-19 14:18 本地运行；**4 files / 32 tests passed**。
   - 包含实际锁定 DSH 子进程的受控工具/插件装配、skip 下隐私拒绝、真实本地 HTTP 搜索及 redirect 拒绝、退休会话冷恢复等测试；该测试的 LLM fixture 不是真实 DeepSeek 判定。
2. 临时探针 `pnpm exec tsx /tmp/pa-static-review-616/probe.mts`：内存 IM DB + 真实 Messaging/PersonalAgents/Gateway/Identity/NodeStore/PersonalAssistant，全部合成身份/正文。
   - 真实 `Identity.deviceRecoverDevice`：节点 epoch 变为 2；合法新 principal 的 PA authority 返回 `personal_binding_not_authorized`。
   - 排除来源并屏蔽 sender 后：`sourceAllowed=false`、direct relay queue=1、`admit=true`、NodeStore 内有排除正文。
3. `pnpm exec tsx /tmp/pa-static-review-616/partition-probe.mts`：真实 GlobalAgent 与 NodeStore，模拟独立 PA runtime offline 和一条待处理 PA 来源事件。
   - `recover()` 返回 `personal host offline`；健康 ordinary Agent 的 `session.ensure` 调用为 **0**。没有启动产品服务或模型。

### 复用证据及限制

实施记录 `M1-personal-agent/implementation.md:13–40` 明确区分已运行与待验：较早后端 380 tests、前端 893 tests、Python 非 E2E 62 tests、docs-check 通过；这些全量结果发生在最终 completion/incident 修订之前。本轮派发另提供候选 build/typecheck、受影响后端 27 tests、前端最后 targeted 39 tests 已通过；复用作局部回归背景，不写成最终全 CI。

实施记录描述真实 DeepSeek 隔离旅程：创建、2024 历史查询且不改 unread、向两真人 DM 协调且 DTO 保留 PA actor、合成私密 canary 未外发、原生 followup 和对方回复观察。它同时明确：最终固定 peer notice 仍须 live 重验，迁移/epoch、全部撤权源和 per-PA availability 尚未验证。本轮未读取凭据或将私有原始日志写入报告；真实接收端/三宽度对照由产品 reviewer 补直接证据。

## Correctness

| Requirement / Scenario | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| 固定 PA：创建、命名、重复提交、唯一私聊 | `apps/im-server/src/personal-agent.ts:266–316`；Web onboarding / dialog | IM 创建幂等、owner-only DM 测试；真实创建记录 | 已有实现；迁移/epoch 见 C2 |
| 现有 IM 增量融入：桌面、手机、日常辅助 | `chat-workspace-page.tsx:1161–1270`；`personal-agent-collaboration.tsx:43–54` | 前端 PA / source navigation 测试；最终三宽度产品对照待提供 | 代码具备；C3 evidence pending |
| 接住目标：原 task、观察建议不自动立项、多目标与更正 | `personal-agent.ts:127–198`；`personal-assistant.ts:38–55` | 私人任务更新/真实 done + result 测试；未采纳外部输入不创建 scope 测试 | 局部 covered；两目标真实旅程待补 |
| 原工具审批与内部协作不增加 PA 人工审批 | `personal-security.ts:87–111`；`agent-config.ts:78–95`；`global-mode.ts:35–44` | native DSH skip/能力限制测试；`next()` 原 deny 仍返回 | AND 关口存在；ask/deny 对照、内部成果真实质量待验 |
| 只问必要业务决定/新授权 | `personal-agent.ts:199–210,328–340`；`personal-security.ts:55` | 独立 reviewer schema、needs_owner 不 commit；decision UI 测试 | 代码具备；决策后继续与打断次数待验 |
| 多来源归同目标、识别本人已处理 | `personal-actions.ts:74–76,110–117`；`global-agent.ts:126–177` | 本人先回复拒绝旧 send、当前受众测试 | 部分 covered；来源入站绕过见 C1 |
| 离开仍有下一步：真实安排/等待/完成分开 | `personal-assistant.ts:215–233`；`personal-agent.ts:173–198` | schedule receipt 测试、私有 task done/result 测试；真实 followup 记录 | 局部 covered；busy/restart/双目标待补 |
| 稍后、暂停观察、暂缓目标、排除/清理 | `personal-agent.ts:41–55,150–172,321–358`；`global-agent.ts:147–170` | history 在暂停时可用、排除 query、owner pause/draft-only 和 context retire 测试 | 排除/屏蔽直接入站错误 C1；真实恢复和影响范围待验 |
| 可疑套取双向告知、重复合并、误会/屏蔽 | `personal-agent.ts:215–233,342–351`；`personal-actions.ts:39–41,94,158` | incident 幂等、fixed security notice scope 测试；最后真实 peer notice 重验未完成 | 局部 covered；C1/C3 |
| 本人隐私与外部身份：假授权、撤权、unknown | `personal-agent.ts:23–39,104–120`；`personal-actions.ts:47–76,124–180` | owner source 证据、source/current ACL、unknown 外发、受众变更 | 主要关口 covered；恢复 C2、入站 C1 |
| 私人背景与外部话语保留来源，摘要不升级 owner | `knowledge/runtime.ts:102–112`；`personal-state.ts:16–31`；`personal-security.ts:55` | derived memory 标记与清理 native 测试；host evidence 包含上下文 | 代码保守失效；真实多轮派生/子执行攻击待补 |
| 自动外发检查：改写、故障、多 sink、变化/并行 | `personal-actions.ts:78–180`；`personal-assistant.ts:87–202`；`web.ts:20–57` | IM/task/附件 bytes/Feishu permit/network/redirect、并行 revision 阻断；无原文流式泄露路径 | 主要 sink 有接入；真实安全改写/所有接收端证据待补 |
| 历史任意时期、人物/时间/关键词/分页/出处 | `personal-agent.ts:57–83`；`work.ts:495–679` | 2001 历史查询测试与真实 2024 查询记录；current ACL 每次重查 | 无固定窗口；完整分页/跨页撤权与 UI 往返待补 |
| 草稿/代发/不回复与真实作者、本人 unread | `personal-actions.ts:154–159`；`messaging.ts:306–309`；`message-pane.tsx` | actor/authorized_by 实时 event、原 DM 两人成员不变、history 不改 unread | covered 的具体字段；双方真实 UI 仍待产品证据 |
| 极简体验：自然语言交办/历史/控制，故障不转人工隐私批准 | `personal-security.ts:55,133–164`；`personal-agent-dialog.tsx` | 没有固定历史窗口/逐消息三选一；unavailable 不 commit | 代码方向一致；真实打断/自然语言歧义属 reviewer 判定 |
| 原有 Agent/Channels/iOS API 保持 | 普通 runtime partition、既有 DTO 增量字段与 original tool policy | 普通测试背景；未改 iOS 源码；不能以没有 iOS diff 等同服务端兼容验收 | 普通恢复回归 W1；W7 API evidence pending |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 唯一 PA、现有 task 唯一业务真相 | 基本是 | `personal_agent_bindings` owner/agent 唯一；`pa_assistance` 拼真实 task；私有 completion 更新原 task |
| 同一 PA 理解多源，无强制 external fresh session | 是 | `GlobalAgent.binding/main/receive`；来源内容进入同一 global Inbox |
| 原工具权限与隐私审查 AND | 是 | `PersonalSecurity` 先保留 `next()` deny，sink 另走 frozen proposal；native skip 测试有效 |
| 各实际 sink 冻结内容、重新核权限、真实回执 | 基本是 | IM/共享任务/附件/network/Channels 有具体 adapter；普通 agent.message/stream 外发被拒；unknown 不自动重发 |
| 官方 DSH 与包边界 | 是 | node 通过 client 管独立 supervisor；PA/IM 无新增 DSH import，未新增 HTTP kernel / 第二 loop |
| PA 宿主隔离、插件 mount 前约束 | 是 | `runtime-partitions.ts`、node 分区 home/profile、`assertPersonalConfiguration`；native rejected plugin 未 import 测试 |
| 来源排除/屏蔽在所有入口生效 | 否 | direct relay/admit 不用当前来源/contact policy，C1 |
| 同 owner 恢复、旧 epoch 撤销、新分区准备 | 否 | 无 transition；epoch 改变后旧 binding 不能恢复，C2 |
| 一个分区失败不阻断其他分区 | 否 | GlobalAgent recover 共享失败链，W1 |
| 撤源换新 context、记忆保守失效 | 有实现，仍需旅程证据 | `pa.invalidate` 退休主/子 context、清 memory、documents revoked；恢复中删除全部 schedules 后需证明有效其他目标重新安排及真实状态 |
| per-PA availability 如实呈现 | 未证明且有明确代码缺口 | `main.ts:110–112` PA unavailable 没有 IM 状态报告；`personal-agent.ts:18–21` 只看 node online。列入 C3 的局部故障必验，不能用 node online 当 PA ready |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 创建/固定名字/首次目标一次提交 | R1/W1 | onboarding / personal-agent routes / fixed sidebar | 原型 R15 + 实施真实创建记录；最终 1440/768/390 对照待 reviewer | pending |
| 同目标进展/成果/多目标独立 | R2/W2 | assistance/task projection、collaboration | 私有任务完成测试；两个目标完整真实旅程待补 | pending |
| 搜索/制作/内部成果无重复人工批准 | R3/W3 | original approval AND、受控子工具 | native 搜索等 fixture；真实普通/PA 同策略、成果待补 | pending |
| 决策/授权协调/unknown | R4/W4 | scope/decision/frozen operations | IM delegated DTO 与 unknown 测试；完整对照待补 | pending |
| 等待对象/next check/busy/restart | R5/W5 | persistent schedule refs | schedule 回执/真实一次跟进；重启与延后待补 | pending |
| 暂停/排除/恢复、incident、历史代发 | R6/W6 | source policy/context retirement / fixed delegated label | 原型及局部测试；C1/C2、双方和历史真实往返待补 | blocked |
| 既有顶栏/262px列表/768断点与手机底栏 | R1/R2/W1/W2 | 既有 shell/styles 未改，PA 加在聊天组件 | 原型保真通过不代替产品对照；产品 reviewer 在做 | pending |

## Issues

### CRITICAL（提 PR 前必须修）

**C1 — 排除来源和屏蔽身份不能约束 direct relay admission。**

- 契约：spec:261–264、284–286、352–354；IM delta「联系屏蔽」；design:207–211，要求排除禁止自动/工具读取、当前屏蔽阻断新请求。
- 实际：`apps/im-server/src/gateway.ts:908–945` 只检查普通可联系资格并排 relay；`packages/personal-assistant/src/personal-assistant.ts:57–70` 对来源仅模型风险审核，然后存正文。`pa.observations.read` 的排除/block 过滤并不覆盖该分支。
- 独立复现：来源已 excluded、sender 已 blocked、`sourceAllowed=false`，真实 relay 仍排队、admit=true、NodeStore 持久保存排除正文。模型尚未决定最终发送之前就已破坏禁止摄取边界。
- 建议：从 IM 当前 binding/policy/actor 做可恢复的入站核验，覆盖 direct relay、排队/重放及最终 Inbox 消费；新增同一行为 seam 的回归。不要只改提示词，也不要误挡 canonical owner 控制。确认屏蔽前的 queued 输入和解禁后的不重放契约。

**C2 — 同 owner 凭据恢复会使 PA 永久失权；新节点恢复同一 PA 也未实现。**

- 契约：design:213、251；IM agents-nodes delta 末条要求同 owner 重连、新节点 rebind，epoch 递增拒绝旧节点且保留 canonical PA。
- 实际：`Identity.deviceRecoverDevice:914–936` 增 node epoch；新建的 `PersonalAgents.authority:24–29` 同时要求旧 PA binding epoch 相等。所有 PA 来源/动作 API 都失权。`POST .../personal-agent:271–285` 对已有 binding 直接返回，没更新 node/epoch；node `configuration.ts:101` / partitions.assign 也禁止直接改 immutable identity。
- 独立复现：真实恢复方法成功后，node epoch=2、PA binding 仍=1，新合法 principal 调 `authority` 返回 `personal_binding_not_authorized`。不是假想攻击边界。
- 建议：实现认证同 owner 的显式恢复 transition：停止旧 admission、核对未知 operation、退休旧 epoch/进程、新节点准备专属宿主、更新受信配置与 residency，保留 PA/DM/goal 身份；失败可恢复。保留旧 epoch 拒绝，不能简单去掉 equality。

**C3 — M1 的最终退出证据仍不完整，不能标 full verification pass。**

- 契约：design:306 的 W1–W7 与 R1–R6；设计审查 R16 明确先实施不等于省略最终真实验收。
- 实际：实施记录明确最终独立产品验收、最后 peer notice live rerun、full final CI 等 pending。固定候选未有双目标/忙碌重启/全撤源/普通与 PA ask/deny/内部成果、每 PA 独立故障可用性及最终三宽度 must-match 对照的完整直接证据。现有单元/native fixture覆盖真实 seam，不能推导未发生的旅程。
- 建议：复用本轮32 tests及已有效的版本证据，完成 root 正在进行的最终产品验收、必要负向/恢复场景和当前 CI；报告准确 tested SHA、命令/结果/接收端及限制。尤其 PA 进程 offline 而 node 在线时 UI 不能仍标 active（`main.ts:110–112` / `personal-agent.ts:18–21`），需要真实核验并修复确认的偏离。不是要求重跑无变化的全部原型研究。

### WARNING（提 PR 前必须修）

**W1 — 单个 PA 恢复异常阻断健康普通 global Agent 的恢复。**

- 契约：design:166–169 和 gateway PA delta「PA 运行不可用」要求局部故障不串区，其余消费者/Agent继续。
- 实际：`packages/personal-assistant/src/global-agent.ts:119–123` 在所有 global Agent 恢复前无隔离地 await 全部 PA observations；有一条待处理 PA source event 时，offline PA 的 `main` 抛错，ordinary 未进入恢复循环。也不能把另一 PA 的失败传播为整批已完成。
- 独立复现：真实 GlobalAgent + 一健康 ordinary / 一 offline PA，PA source event pending；`recover` 抛 `personal host offline`，ordinary `session.ensure` 调用=0。
- 建议：按 Agent/partition 处理恢复失败并继续健康分区；保留失败事件 pending，向对应 PA 报告，恢复时重试同事件。补最低层部分失败回归，不新增第二套 loop。

### SUGGESTION（可以修）

无。未将命名、代码风格、未知侧信道或研究中的额外防护作为 findings。

## Handoff

`code-review.json` 给出3项 CONFIRMED full findings（C1、C2、W1）；本报告另记录待完成退出证据 C3。共享现场由 caller 提交报告，report_commit 尚未产生；未推送。修复后优先核这些具体失败条件及受影响范围，产品 reviewer 继续独立验收，不以本报告代替真实 UI/模型体验判断。

## Round 2 — Targeted Closure and Fix Delta

### Metadata and verdict

- review_round: `2`
- verification_mode: `targeted-closure`，同时核修复引入的 source/Channels、restore、设备 epoch、本机分区、per-PA status 与 timer 恢复 delta。
- executed_base / prior head: `cf1befff963e6d251e332c513e8ca6adf1d86619`
- validated_at: `a41c22630578d28f76dcb5bee393cfdc9a7bab29`
- fix_delta_range: `cf1befff9..a41c22630`
- focus_issues: Round 1 `C1 / C2 / W1`；Round 1 其他未失效判断保留。
- verdict: **fail — 2 CRITICAL / 0 WARNING / 0 SUGGESTION**，均为新增/受影响 Channels 边界的直接复现问题。
- requires_full_verification: `false`。新增问题局限在已派发的跨包修复路径，无需重开未变化部分的全量审查。
- Code findings: `code-review-r2.json`；Round 1 原 JSON 完整保留，不把原问题自动删除。
- C3 的最终产品证据由 root / 独立产品 reviewer 继续闭合，本轮未重复将“产品报告未出”列为代码 finding，也不宣称整体交付已通过。

### Historical issue closure

| 原问题 | 本轮证据 | 状态 |
|---|---|---|
| C1：直接 relay / queued input 绕过来源排除和屏蔽 | Gateway.relayMessage 先 `messageAllowed`；PersonalAssistant.admit 先请求 IM `pa.source.admit`、false 时不 review/store；新增真实 IM policy 测试和 PA revoked input 测试通过 | **closed**，Web/已持久来源的旧失败条件已关闭；Channels 实际接入另有 R2-C1 |
| C2：device epoch 恢复后 PA 403，且无同 owner restore | Identity.rotatePersonalEpoch 随设备事务旋转 binding/失效 permits，snapshot 包含 PA；真实 `deviceRecoverDevice` 后新 epoch 的 authority 成功。bindDevice 独立实际执行保存 marker epoch=2、旧分区目录消失、新分区保留 durable marker；restore HTTP 测试核同 PA/DM、新 owner node、旧 principal 失权与幂等 | **closed**，不通过移除旧 epoch 检查关闭问题 |
| W1：PA offline source recovery 阻断 ordinary | GlobalAgent 对 observations 和每 Agent 的恢复分别 catch；原独立探针重跑时 ordinary `session.ensure=1`、PA 错误留给 onError；新回归测试通过 | **closed** |

### Delta implementation and evidence

| 受影响边界 | 检查结果 |
|---|---|
| `pa.source.admit` 与当前来源/contact policy | IM 从认证 binding+真实 message 解析，不接收模型 owner；调用在独立输入审核前。Web 旧绕过关闭；Channels mapping 依赖的真实 mirror 写入不兼容，见 R2-C1 |
| 外部 actor / incident / block | 外部 source ID 不再被当成 shadow owner；incident actor/展示改用来源身份。该新身份尚未贯通 egress block，见 R2-C2 |
| 同 owner restore / ConfigOperations restore | 先 server fence 旧 node/binding、pending+stale、失效未发 permit，再由新 node `agent.create` 真回执提交 active；保留 PA/DM/goal，workspace 取新端，不复制旧本地历史。新测试覆盖错误 owner、旧 principal 拒绝和同目标重试 |
| 同设备 epoch / snapshot / local partition | 已独立执行真实 Identity 和 bindDevice（合成 HTTP result），新 config personal epoch 正确且 old home 分区重命名保留原资料；旧 node token 拒绝沿原测试保留。不是生产/真实新节点迁移验收 |
| per-PA status | node onReady/onUnavailable/relay ready 都报告分区 status；IM 按 binding epoch 使用记录；server 测试证明 node 仍在线时 PA unavailable 并可恢复。没有用 ordinary node health 代替 PA 状态 |
| 撤源后有效 timer | GlobalAgent 在新 binding ensure 后调用 restoreFollowups；helper 只恢复非暂停/非完成且 scope 存在、未撤销、所有目标来源仍允许的 assistance；不可用目标清除旧 next_check/schedule。具体真实调度恢复旅程仍由产品验收补证；本轮未发现新增确定性 timer 缺陷 |
| corrected delta / canonical specs | 本 fix delta 未修改契约正文，仍实施已批准 design；**no spec delta**。尚未归并 canonical，未以改 spec 适配问题实现 |

### Independent execution

候选 HEAD 在本轮代码阅读与测试时均为 `a41c22630`、源码 clean；仅写报告，没有修改实现或测试。

1. `pnpm exec vitest run apps/im-server/tests/personal-agent.test.ts apps/im-server/tests/identity.test.ts packages/personal-assistant/tests/personal-assistant.test.ts packages/personal-assistant/tests/global-agent.test.ts packages/personal-assistant/tests/external.test.ts apps/node/tests/device-binding.test.ts`
   - 2026-10-19 14:33，**6 files / 74 tests passed**。复用 caller 所报较早全量 386 tests / build/typecheck 作为背景，不冒称本轮重跑全量。
2. `/tmp/pa-static-review-616/round2-probe.mts`：真实 Identity 恢复后 epoch=2，新 PA authority 成功；真实 ExternalChannels + Messaging.sendMessage 对正常外部 DM 的 mandatory mirror 失败，异常 `personal_reviewed_delivery_required`，receive=0。
3. 原 `/tmp/pa-static-review-616/partition-probe.mts` 重跑：ordinary ensure 从0变为1，旧 W1 关闭。
4. `/tmp/pa-static-review-616/local-epoch-probe.mts`：真实 bindDevice + 临时本地 HTTP fixture，动作 prove/recover-device/prepare/recover，保存 epoch=2；新分区 durable marker 内容与旧分区一致，旧目录不存在。临时 HTTP server 和目录在 finally 关闭/清除；没有产品服务或模型调用。
5. `/tmp/pa-static-review-616/round2-block-egress.mts`：真实 PersonalActions，既有有效 scope 下先插入 sourceActor 对应的 external block，再准备、审核、提交新 Feishu payload，实际结果仍为 `sending`。

### CRITICAL

**R2-C1 — Channels 输入被新增 mandatory flush 阻断，`pa.source.admit` 到不了真实接入。**

- 契约：保留既有 Channels 行为、真实外部身份与当前来源核验；设计允许可受控外部 DM，而不是全部阻止正常联络。
- 位置：`packages/personal-assistant/src/external.ts:91–95,252–254`；`apps/im-server/src/messaging.ts:90,479–483`。
- 证据：flush 对 incoming mirror 调普通消息写 API，目标是非 canonical shadow、sender_type=user；现 PA access(write) 拒绝非 owner DM，下一层还拒绝 PA 的 user sender。因此新增的同步前置让正常 PA Feishu 输入在 receive 前必然失败。当前 external test mock 了整个 `im` 函数，未覆盖此跨包契约。
- 独立复现：真实两个类组合，正常 DM 返回 `personal_reviewed_delivery_required`，接收调用0；无网络平台依赖。
- 建议：为可信 incoming mirror 设窄入口，绑定当前 node/PA/channel/source、真实 external actor、幂等原消息及无 relay 副作用；保留普通 PA 外发与 owner 冒充拒绝。补真实 IM handler 与 Channels 的边界回归，不能仅继续 mock IM 写成功。

**R2-C2 — External block 身份未参与实际 transport commit，已屏蔽对象仍能收到后续目标消息。**

- 契约：IM PA delta「联系屏蔽」要求阻断新请求/投递及相应待办许可；design 同会话安全通知也不得绕屏蔽。
- 位置：`apps/im-server/src/personal-agent.ts:42–45` 引入 `external:<shadow>:<sender>` 身份；`personal-actions.ts:59–63` 仍只对 shadow participants 查 block。
- 证据：shadow participants 是 owner 与 PA，永远不等于新 external actor；policy revision 能淘汰旧 proposal，但新 proposal 捕获新 revision 后仍通过，所以已有目标的定时/主动协调可以继续外发到被屏蔽对象。
- 独立复现：使用真实冻结动作/审查/commit，实现原样返回 `sending`。没有假设模型主动绕过：审核包也未包含该 block 事实。
- 建议：将经过认证的 transport 接收者映射到同一 canonical external actor，在 prepare 与 commit 核当前 block/许可，覆盖 incident 和既有目标继续发送；不能把 owner 的 shadow sender 当外部收件人。

### Handoff

Round 1 的3项代码 finding 已有逐项 closure 证据；本轮2项新增 CONFIRMED 问题不能用旧 finding 关闭结论覆盖。报告只对应固定 `a41c22630`，后续 root 改动不在本轮结果内。未提交/推送，由 caller 归入下一候选。
