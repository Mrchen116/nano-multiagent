# Verification Report: refactor-672-im-contract-boundaries

> Validation snapshot: `ff326c351 → 648b5439e914d6cf90f85a5296734c0e77e3c7eb`

## Round 1 / Metadata

- reviewer: 独立 verifier `/root/static_review`，未参与实现；同时承担独立 code review，复用同一次有效检查。
- verification_mode: `full`；review_round: `1`。
- executed_base: `ff326c351`；validated_at: `648b5439e914d6cf90f85a5296734c0e77e3c7eb`。
- effective_base / effective_through: 同固定验证版本；未外推至后续 source 变化。
- completed_at: `2026-10-28T11:32:00+08:00`。
- requires_full_verification: `false`。
- 现场：caller 提供的共享 worktree，开始时 HEAD 匹配且 clean；未启动服务、未改源码/测试/设计、未创建额外现场，报告由主 Agent 提交。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1/M2 2/2；motivation 场景 3/3 有实现与回归保护 |
| Correctness | 指定范围通过；0 CRITICAL / 0 WARNING |
| Coherence | Followed；配置纵切、RPC owner 与窄依赖均落实 |

本 unit 的静态完整验证通过。全量 JS 同步后运行仍有待主 Agent 判真的 DSH 集成失败；本报告不将其声称为绿灯，PR 交付仍需完成全局检查门禁。

## Completeness

- M1 complete：全部 21 个主动 RPC 有限命令、输入/结果及响应名关联；稳定消费字段校验，扩展内容保留动态；transport 独立拥有连接关联、定时器和 close。编译负例进入常规 typecheck，传输及真实 WS 回归保留。
- M2 complete：HTTP unknown、候选、固定 SQL record、operation、配置 wire 回执与公开 View 分离且实际消费；ConfigOperations 不再接收 ImContext/Gateway/Identity/Messaging。create/apply/recover/compensation/restore 与提交后生命周期路径均保留。
- Spec 覆盖：对照 `docs/specs/im/agents-nodes.md` 的配置中心、版本锁、ACK 丢失恢复、live/mirror、下一轮采用，以及 `auth-tenancy.md` 的管理归属/资源空间、`gateway-relay.md` 的连接和确认恢复边界。未发现缺少实现的目标场景。
- Prototype / Reference：N/A，无客户端变化、无设计原型。
- 明确剩余范围：聊天、Work、Channel 上行业务及其 Row/ImContext 未全面迁移；不包含报告其他项、序列化归属重构、部署或发布。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖与证据 | 状态 |
|---|---|---|---|
| owner 保存与刷新；越权不读写；旧版本不覆盖 | `control-routes.ts:17` requireProfile、`:406` PATCH；`control.ts:184` authorize、`:332` commit | `control.test.ts:408` owner scope；`agent-settings.test.ts:104` 离线写拒绝；`approval-configuration.test.ts:12` 保存/省略/null；`configuration-boundaries.test.ts:7` HTTP/存储/投影 | covered |
| 配置确认丢失/断连后沿同一 operation 恢复；不显示旧值为新保存成功 | `control.ts:242-310` request/resolve/recover；`node-rpc-request.ts:13` 未确认回执处理 | `control.test.ts:324` durable pending/重建服务恢复；`agent-settings.test.ts:149` 断连/待确认；`e2e/control-work.test.ts:323` 真实 HTTP/WS malformed → pending → 同 operation 恢复 | covered |
| 创建结果丢失不重复创建工作区 | `control.ts:312-316` create 与 `:397-415` registration seed/idempotence；Node operation receipt 语义未改 | `control.test.ts:277` canonical identity/一次创建；既有 E2E control-work 创建恢复用例 | covered |
| CAS 失败先恢复并发已确认配置；PA restore 与名称同步不丢失 | `control.ts:364-395` compensation；`:419-468` PA restore、profile/user/binding/chat 事务与生命周期 callback | `control.test.ts:369` 保留并发值/approval 并补偿；`personal-agent.test.ts:61,97` PA 创建与延迟名称恢复；restore 分支与基线逐行核对，无新行为决定 | covered |
| 连接更换、并发、错响应、迟到、停服不串请求 | `node-rpc.ts:24-67`；`gateway.ts:382-402,1034` | `node-rpc.test.ts:14,28,41` 关联/校验/超时/close；既有 node-connection 和 `agent-lifecycle.test.ts:101` 真实 socket 新旧连接保护 | covered |
| 配置字段不改变模型消费及原指纹 | `control.ts:23-95,129-149`；`configuration-rpc.ts:62-78`；`apps/node/src/configuration.ts:78-98` 未改映射 | `control.test.ts:266` 非 ASCII 指纹；`approval-configuration.test.ts:38` IM/Node 一致；新增 HTTP/WS 用例检查 prompt、nullable 字段及有序 fallback | covered；非模型语义评测 |

表内未带目录的服务/测试位置分别相对 `apps/im-server/src/` 和 `apps/im-server/tests/`；配置 wire decoder 位于 `packages/product-contracts/src/`。

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 完整配置纵切；不做全仓 Row 替换 | 是 | `configuration-input.ts:6-27`、`configuration-records.ts:4-52`、`control.ts:97-149` 分别拥有候选、记录和 View；无源码测试断言假扮类型解析 |
| 全部主动 RPC 有限命令和相关输入输出；扩展字段动态 | 是 | `node-rpc-contracts.ts:58-113`；`node-rpc-values.ts:41-122` 与真实调用者/Node handler 对照 |
| transport 只管关联、timer 与 close；Gateway 保留业务权限 | 是 | `node-rpc.ts:5-67` 不访问 db；`gateway.ts:382-402` 授权后 accept |
| 服务仅 db + 配置 request + commit 后 lifecycle | 是 | `control.ts:15-19,172`；`configuration-assembly.ts:6-11` adapter；配置端口限制在三类命令 |
| 解析属于边界；回执保留原 payload；业务身份二次检查 | 是 | `configuration-input.ts:43-83`；`configuration-rpc.ts:62-78` 返回原对象；`control.ts:260-306,332` |
| 不改序列化算法/调用语义，不切协议/数据版本 | 是 | `control.ts:23-95` 与基线对照；Node configuration diff 仅共享类型签名；无 schema、lockfile 或运行时导入变化 |

### Prototype / Reference Contract

N/A。

### Agent Context

复用本轮 `code-review.md` 的 Mode B 限定检查：字段来源、候选/回执/恢复与 unchanged Node runtime 映射一致。未发现实现偏离设计或设计自身不合理；实际 provider payload 和模型理解未运行，也不是本次保行为重构的新增证据要求。未以内部类型声明或 UI 卡片声称模型已正确消费。

## Evidence

- caller/实施者带版本交接：M1 4 文件 32 passed；M2 7 文件既有回归 71 passed；最新定向 16 passed。未重复全量。测试落在现有 owner seam，原保护仅调整 import/装配；新增测试分别保护 transport、HTTP 边界和真实协议接线风险。
- 固定 HEAD：`.e2e-refactor-672/build.log` 包含本 HEAD installer 完成；`typecheck.log` 所有 workspace 包 Done，含 IM 编译负例；独立 `git diff --check ff326c351..648b5439e` 通过。
- 复用现有 `.e2e-refactor-672/pytest.log`：70 passed / 32 deselected；`docs.log`：297 maintained Markdown、68 routes 通过；`ruff-check.log`、`ruff-format.log`、`ios-runtime.log` 通过。同步后的重跑与最终记录由 caller 收尾。
- 全量限制：同步前 `test.log` 为 772 passed / 1 knowledge-policy 等待超时；同步后 `test-synced.log` 已有多个 DSH 集成超时，caller 停止本次测试并保留日志，计划以 `--maxWorkers=2 --no-file-parallelism` 复核。caller 观测主机 load averages 474.29 / 189.40 / 89.73；这不证明所有失败都是资源原因。未把失败标成已排除或本 unit 回归；全局门禁仍待 caller 处理。没有跳过或删除失败测试来制造通过。
- 真实 HTTP/WS 证据来自隔离 IM 子进程和协议测试节点，不是生产、真实 Node 配置执行或模型语义验收。产品验收由独立产品 reviewer 负责。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

无本 unit 实现问题；上述全局 JS 门禁尚未完成，不能据本报告跳过交付检查。

### SUGGESTION（可以修）

无。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| design 声明 IM no spec delta | 完整 diff 无客户端/公开能力、配置有效值/生效时机、身份、协议版本、schema 或指纹语义变化；非法回执仍按 current 未确认操作处理 | 既有配置/权限/恢复回归及新增 HTTP/WS 保真保护 | aligned — no spec delta |

### Uncovered Observable Behavior

无遗漏的受支持行为增量。新增 decoder/入口检查在所属边界拒绝畸形稳定字段，历史 null skills 仍可读取；不构成新产品能力或现行契约改写。无须为内部类型和 owner 拆分增加 canonical spec。

Outcome: **aligned / no spec delta**。

## Round 2 — Final Sync Delta Verification

- reviewer: 同一独立 verifier `/root/static_review`。
- verification_mode: `delta`；review_round: `2`。
- prior_verification_path: 本文件 Round 1。
- executed_base / effective_base: `b8fc5edefcb74ec8a8888aeb7fa245779e644253`。
- validated_at / effective_through: `fc0dca156b3c3cce9602d39e7c47a601ad86b038`。
- fix_delta_range: final sync `32ac1af9d → fc0dca156`，结合 `ff326c351..b8fc5edef` 的共享边界和 range-diff 排除继承主干变化。
- focus: 序列化冲突、control/Gateway import、既有 Unicode 指纹/AAD 保护、product-contracts exports，以及 Task 关闭 owner 对本配置纵切的影响。
- completed_at: `2026-10-28T11:49:00+08:00`。
- requires_full_verification: `false`。
- verdict: **pass；0 CRITICAL / 0 WARNING / 0 SUGGESTION**。Round 1 的完整实现结论保留；本轮不是重新执行全量产品验收。

### Completeness / Correctness / Coherence

| 同步影响 | 实现证据 | 验证证据 | 结论 |
|---|---|---|---|
| 配置候选序列化改用主干正式入口，同时保持历史 DEL 格式 | `control.ts:1,24-29,35,96` 使用 sortedJsonUtf8 + 原 U+007F..FFFF 转义；service、HTTP adapter 和窄依赖仍在 | range-diff；主干 Unicode fingerprint/heartbeat 断言完整保留；final 77 tests | aligned |
| Gateway publication identity 格式与 RPC 关联并存 | `gateway.ts:1-3,572` 使用 sortedJsonAscii；未恢复 canonicalJson；RPC accept 及身份顺序未变 | 新旧生产 diff；final build/typecheck；相关 8 文件全过 | aligned |
| 测试冲突没有删除主干新保护或本 unit 旧保护 | control 同时保留 ChannelKey/sortedJsonUtf8 与配置窄依赖；approval 同时保留 gatewayCandidate 与新路由 import | 两个主干新增 Unicode fingerprint/AAD 测试正文逐字一致；77 tests passed | covered |
| product-contracts export 合并不泄漏/丢失契约 | 根入口保留 canonicalJson 退役，仅追加配置类型/parser；package 保留 serialization 子路径 | 最终 diff、全包 build/typecheck | aligned |
| Task 关闭 owner 不破坏配置能力 guard 与 Gateway.tasks 装配 | 主干 Messaging 外层事务调用既有 Gateway.tasks；activeTaskCount/withdrawsTask 定义与本 unit Task RPC 边界不变 | main 增量及 Gateway/Task 接线核对；没有本 unit 覆盖主干 Task 关闭逻辑 | retained |
| 模型有效配置内容与恢复不因同步变化 | HTTP/候选/records/assembly、RPC map/decoder/request/transport、PA ConfigurationOperations 和编译负例共 11 文件与同步前逐字一致 | 独立文件比较；复用 Round 1 Mode B；final 配置/回执回归 | retained；未新增模型行为验证声明 |

### Evidence / 既有门禁限制的补充

- `.e2e-refactor-672/build-final.log` 完成固定 HEAD `fc0dca156...` installer build；`typecheck-final.log` 全部 workspace 包完成；`test-final-integration.log` 在 11:47:57 开始、7.38 秒完成，8 文件/77 tests passed。
- 本轮独立 `git diff --check b8fc5edef..fc0dca156` 通过；未重复运行已有有效测试，未启动或留下服务。
- caller 交接的先前 bounded 全量为 777 passed/2 failed（145 文件/779 项），并非单次全绿。两个原样复跑日志已核对：`knowledge-low-load.log` 5/5 passed；`disable-low-load.log` 1 passed/6 未选中。前端 1029、Python 100 通过由 caller 的交付记录承接。未改产品、断言或 timeout 阈值；这些证据不证明所有原失败必由负载引起，远端 CI 仍按交付要求执行。
- Round 1 的早期失败/未完成记录是当时快照，保留历史；当前集成证据以上述 final 日志为准。无需因已原样复跑通过的旧失败重开实现或修改本 unit 设计。

### Delta / Spec Reconciliation

- 相对新 base `b8fc5edef`，refactor-672 仍为 **aligned / no spec delta**。主干 refactor-673 对 Task 关闭的 current spec 更新是已继承行为，不计为本 unit delta，也未被本 unit 撤销。
- 无遗漏的对外行为变化、无配置字段/权限/生效时机/恢复或指纹不一致；序列化 owner 迁移沿用新 base 正式契约和历史字节保护。
- 无新增 Context finding；复用 Round 1 的限定 Implementation Review，不将 unchanged 配置链等同于已验证模型理解。
- 无 CRITICAL/WARNING/SUGGESTION；Round 1 full 可保留，结果有效至 `fc0dca156b3c3cce9602d39e7c47a601ad86b038`。报告追加由主 Agent 提交，后续仅文档提交不被称为重新执行过验收。

## Round 3 — M3 Full Verification 与同步有效性

- verification_mode: `full`（新增 M3 全纵切）；M1/M2 只做同步影响核查，保留 Round 1/2 未失效结论。
- review_round: `3`；reviewer: 独立 verifier `/root/static_review`。
- executed_base / effective_base: `94b06908d396c8039d820124c4d86cb32a75eaf4`。
- validated_at / effective_through: `badc559a1937b9b7b34b75df4d5a3ba0f5137e22`。
- implementation_range: `bd0938462..badc559a1`；completed_at: `2026-10-28T13:29:00+08:00`。
- requires_full_verification: `false`；本轮已按完整新增 milestone 核查，修复可限于 finding 关联边界。
- verdict: **未通过；0 CRITICAL / 1 WARNING / 0 SUGGESTION**。
- 未改产品、测试、配置或设计；仅追加本报告与 code-review，由 caller 提交。独立内存数据库复现已关闭，无额外进程/现场。

### Summary / Completeness

| 维度 | 结论 |
|---|---|
| Completeness | M1/M2 retained；M3 架构与生产链落实，但权限稳定字段解码退出标准未完成 |
| Correctness | 2/3 新 Requirement 已覆盖；畸形来源边界有 1 项已复现漏检 |
| Coherence | 事件生产/日志/传输关联、WorkRecords 数据库依赖及投影分工符合设计 |

prototype/reference N/A，无客户端改动。按扩展 motivation/design 逐段追踪 producer、InboxStore、WorkSync、IM 双入口、日志/投影与公开页；没有以类型文件或测试数量替代真实接线核查。

### Correctness

| Requirement / 场景 | 实现与契约位置 | 测试/检查证据 | 状态 |
|---|---|---|---|
| Work 记录从生成到刷新保持真实完整 | `work-events.ts:1-149`；PA work-projection/GlobalAgent；IM `work-records.ts:182-510`；current agent-work 的明细/裁剪/统计/刷新要求 | `e2e/work-production-chain.test.ts` 实际 PA→HTTP/SQLite→公开主子页，大参数/完整结果、未报告 total、刷新及恢复；既有替换事实和恢复保护 | covered |
| Work 同步与重放保持同一身份 | InboxStore commitWork/append/journal；PA WorkSync；IM WorkRecords append 事务与 work-sync hash receipts | 既有 work-sync 的缺口/身份/分段/重启/撤权/completeness；新 alias/扩展字节用例与生产链重复上传 | covered |
| Work 契约边界不扩大访问权限；畸形稳定字段不得推进 | HTTP readWorkBatch、WS Work.append 与 WorkRecords 的 owning profile/session 检查 | 已有 tenancy/撤权和新增 malformed presentation 的 batch/part/WS 拒绝有效；permission options 独立复现可提交、推进且后续消费 TypeError | **WARNING V3-1** |

表内短文件名分别位于 product-contracts/src、personal-assistant/src 或 im-server/src；新增公开链测试位于 apps/im-server/tests。

### Coherence / Delta 与 M1/M2 保留

- 已知生产事件判别联合通过 projectWorkEvent、GlobalAgent/KnowledgeUpdates、InboxStore 原子 checkpoint 与 journal、WorkSync 贯通；unknown 扩展只在接收/历史 envelope 保留，无生产 string fallback。
- WorkRecords 只依赖 db，拥有固定 SQL 记录和公开 view/page；Work facade 保留授权、连接/同步状态及提交后广播。事件/投影/水位 SQL 事务、原 JSON.stringify、身份冲突、PA main 替换与 revoked identity-only 规则对照旧实现未变。
- 新 batch decoder 先校验再提交，chunk 在原字节哈希/UTF-8 检查后进入同一 decoder。旧别名、nullable/省略统计、未知扩展与动态工具 detail 直接返回原对象；新增测试从存储 payload 和公开 item 验证保真。权限 options 尚未达到“实际消费稳定字段均验证”标准。
- M1/M2 的配置与 NodeRpc 没有语义 delta。唯一同步变化为 control-routes 的 skill usage 改用新 base 已有 settingsSectionDisplay；保持主干投影，并未重开配置/恢复/序列化决定。配置 exports 完整保留后追加 Work export，未恢复 canonicalJson。M1/M2 审查结论 retained 至本次 HEAD。
- Context：复用同轮 code review 的限定 Mode B。Work 事件包装、用户投影和共享 presentation 不改变正常字符串身份的模型输入或工具消息；native replace 仍不投影成新完成事实。未验证真实模型行为，也不以静态类型或卡片冒充 provider 交付证据；本次没有新增模型语义决定。

### Issues

**CRITICAL：无。**

**WARNING V3-1：权限 options 的对象/id 形状未进入共享稳定契约。**

- 契约：扩展 motivation 的“畸形事件与无权来源”场景、design M3 decoder 与批量/分段/WS 不推进退出标准。
- 位置：`packages/product-contracts/src/work-event-codec.ts:63-65`、`work-events.ts:68-72`；实际消费 `apps/im-server/src/work.ts:423`。
- 直接证据：独立内存 SQLite 中 session/turn/`permission_request {request_id:'bad',options:[null]}` 经 readWorkBatch→WorkRecords 提交，ACK through_seq=3；保存 pending 权限。路由相同 `.options?.some(o=>o.id===decision)` 表达式对 null 条目抛 TypeError。嵌套 `permission_request:{request_id:'nested',options:'bad'}` 也被 decoder 接受。该批未按目标拒绝，后续权限决定会失败。
- 建议：具名两种表示实际消费的 option 对象/id，在共享 decoder 检查；保留未知额外字段与合法省略。扩展最低接收边界回归，证明畸形 flat/nested 值均不产生事件、权限投影或水位推进，再复用既有合法权限/生命周期保护；无需改设计/current spec。
- 分类：实现未达到设计退出标准；不是设计本身不合理，也不是缺少模型行为证据。状态 CONFIRMED；详见 code-review Round 3 唯一 finding。

**SUGGESTION：无。**

### Evidence

- `m3-integration.log`：10 文件/110 passed，含生产链；PA 首轮/中心边界进度证据按 M3 progress 保留。测试修改仅补齐真实事件身份和合法 payload；Inbox 原子失败/回滚断言未削弱。
- `m3-build.log`：完成固定 HEAD installer；`m3-typecheck.log`：全包 Done，包含 PA/IM 编译负例；`m3-ios-runtime.log` 通过；`m3-pytest.log`：100 passed/28 deselected。
- 独立最窄复现为临时内存数据库/共享 decoder 与实际 WorkRecords，不触及生产、源码或测试；输出 ACK、stored pending permission 和相同 route consumer 的 TypeError。全量后端/前端仍由 caller 收尾，未重复全量。
- 独立 diff-check 当前报告 `work-records.ts:490` 尾随空格，已告知 caller；机械格式门禁尚未清理，不升级成第二个正确性 finding。

### Spec Reconciliation

**目标仍为 no spec delta。** Work event 类型/模块归属变动、数据原值和恢复不变性均可由现行 agent-work 契约承接；没有新增协议版本、schema、模型语义或产品能力。V3-1 是漏掉目标内稳定字段校验，不应通过改 spec 接受畸形权限来关闭。

Outcome: **implementation-mismatch（V3-1 待修）；no spec delta 声明保留。** M3 修复后需限定 patch/closure；M1/M2 与本轮其余有效证据继续保留。

## Round 4 — Targeted Closure V3-1

- verification_mode: `targeted-closure`；review_round: `4`。
- reviewer: 同一独立 verifier `/root/static_review`。
- prior_verification_path: 本报告 Round 3；focus_issues: `V3-1`。
- executed_base / effective_base: `94b06908d396c8039d820124c4d86cb32a75eaf4`。
- finding_origin_head: `badc559a1937b9b7b34b75df4d5a3ba0f5137e22`；fix_delta_range: `badc559a1..197da048e`。
- validated_at / effective_through: `197da048e8975677e8e82f7e0f73f511e7f67687`。
- completed_at: `2026-10-28T13:31:00+08:00`。
- requires_full_verification: `false`。
- verdict: **pass；0 CRITICAL / 0 WARNING / 0 SUGGESTION**。Round 3 其它结论及 M1/M2 retained，不重复 full 验证。

### Finding Reconciliation

| Issue | 实现证据 | 验证证据 | 状态 |
|---|---|---|---|
| V3-1 flat/nested options 漏检 | WorkPermissionOption{id:string,...扩展}；WorkPermissionRequest 与 flat 字段同用该数组；共享 decoder 检查数组、对象、id，允许安全 null | 原 HTTP 边界测试在原实现两项红测；修复后 batch/part 的 400、不提交和不推进断言全部通过；新增编译负例 | **closed** |

实现符合原设计的稳定消费字段检查；没有通过更改 spec 接受畸形数据。公共模型 Context、SQL 投影、权限生命周期与 ACK 时机未改。修复仅覆盖原问题关联字段，未知扩展仍保存原值，null 按原 optional 消费安全处理。

### Evidence

- `.e2e-refactor-672/m3-permission-red.log`：两项新增权限参数化用例在原实现返回 200/through_seq=2，按预期红；原工具畸形用例仍在同一测试 owner。
- `m3-permission-green.log`：3 文件/23 passed（batch/分段、生命周期、实际 PA 生产链）；caller 交接本修复 PA/IM typecheck 通过，编译负例已纳入常规 typecheck。
- 独立源 decoder 最窄检查：4 例畸形 flat/nested shape/id 拒绝；4 例 null/合法带扩展内容保留原 event/fact 引用。没有修改源码/测试或创建现场。
- 独立 `git diff --check 94b06908d..197da048e` 通过，Round 3 指出的空白已清理；报告差异本身也通过 whitespace 检查。
- `m3-frontend.log`：108 文件/1029 passed。M3 的 build/typecheck/iOS/Python 和 110 项首次集成证据按 Round 3 保留；本修复用窄测试/typecheck 承接。后端全量还在 caller 的交付流程中，本报告不提前宣称结果。

### Spec / Context / Completion

**aligned / no spec delta**；V3-1 的 implementation-mismatch 已解除。M3 与设计/现行 agent-work 契约对齐，原权限漏检已关闭，无新增 Context finding。静态门禁对固定修复 HEAD 通过；后续全局 CI 与报告提交由 caller 收尾。仅追加两份报告，未覆盖其它并行文档修改、未提交。
