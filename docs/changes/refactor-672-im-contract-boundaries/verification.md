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
