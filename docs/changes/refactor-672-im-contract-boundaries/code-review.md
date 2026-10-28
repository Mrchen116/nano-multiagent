# Code Review

## Round 1

- reviewer: 独立 reviewer `/root/static_review`，未参与设计或实现。
- review_mode: `full`。
- executed_base: `ff326c351`。
- validated_at: `648b5439e914d6cf90f85a5296734c0e77e3c7eb`。
- effective_base / effective_through: 同上述固定版本；后续提交由交付 owner 判断失效范围。
- completed_at: `2026-10-28T11:32:00+08:00`。
- checkout: `codex/im-contract-boundaries`；开始时 clean。本轮仅写本报告和 `verification.md`，由主 Agent 提交。

### Findings

```json
[]
```

### 覆盖与判断

- 审查完整 `ff326c351..648b5439e` diff；将旧 `control.ts` 的服务和路由分别与新服务、`control-routes.ts` 逐段对比。不是仅检查新增类型声明。
- 核对全部 21 个主动 RPC 的真实调用者：control、onboarding、conversation-actions、personal-agent、work 与 Gateway Task adapter。对照 `apps/node/src/main.ts:187-292` 的配置、能力、预览、setup、fork、usage、heartbeat、cron、Task handler；`agent.work.permission` 的传输形状与既有 Work 调用及 Gateway 生命周期 gate 相同，本次不改变其接收端实现。`NodeCommandMap`/`nodeResponseTypes` 封闭命令关联，无公开 string fallback；setup/provider 目录和插件内容继续保留动态载荷。
- `node-rpc.ts:24-67` 保留更新 409、离线 503、10 秒超时 504、连接引用与响应名匹配、迟到/重复忽略和 shutdown 定时器释放。`gateway.ts:382-402` 仍先验证当前已注册连接、node identity 与适用生命周期，再交给 RPC 关联；注册、Task 写屏障和上行业务未移给 transport。
- `configuration-input.ts:43-83` 在 HTTP/存储 JSON 边界检查实际消费字段；固定 SQL 查询在 `configuration-records.ts:57-74` 拥有记录声明。`control.ts:129-149` 的公开投影与候选恢复不泄漏 SQL JSON 列；HTTP 候选仍显式选择字段，额外键不进入 operation。省略 approval、nullable reasoning、null prompt/heartbeat 保留、nullable features/work mode，以及历史 null skills 均有对应保护。
- `control.ts:184-468` 保留 operation 身份和指纹、串行锁、二次授权、原 SQL/事务顺序、gateway_applied 恢复、CAS 补偿、PA restore/name/chat 同步和提交后 lifecycle。`configuration-assembly.ts:6-11` 是唯一全容器装配 adapter，服务仅持有 db、三类配置 RPC 与生命周期回调。`requestConfiguration` 将非法回执留在未确认流程；decoder 保留原 payload 及额外 wire 元数据，不重写持久回执。
- 比对 `asciiJson`、`gatewayCandidate`、`candidateFingerprint` 与 Node canonical/fingerprint：未迁移算法、改变排序/转义/字段缺省或哈希输入。`selection` 的 null 兼容防止合法历史值在公开投影崩溃，不改变规范内配置含义。
- 测试迁移未删除原断言；新增传输测试保护关联与生命周期，HTTP 测试保护输入/存储/投影，真实 HTTP/WS E2E 保护 malformed receipt → pending → 同 operation 恢复。编译负例进入 IM 的常规 typecheck。

### Agent Context Implementation Review

- 模式：`agent-context-review` Mode B，限定配置选择、传递与恢复链；不是新增 Prompt 或模型语义设计。间接触发原因：custom_prompt、features、skills/tool_allowlist、model/reasoning 与 PA identity 最终影响模型可见信息。
- 核查 owner HTTP → candidate → durable operation → Gateway wire → Node ConfigurationOperations → `apps/node/src/configuration.ts:78-98` 的 runtime 配置映射；同时检查读取、重试、CAS 补偿与 PA 绑定。来源身份仍由服务端 binding 派生；用户 body 的 personal identity 不成为授权来源。
- Before/After 的受支持配置字段、字段选择、候选规范化、fingerprint、持久恢复及生效调用顺序一致。`parseAgentConfigurationFields`/`decodeNodeResult` 校验后返回原对象，未新增过滤或重新组装模型消息。新增 E2E 的真实出站 apply 与恢复后的公开配置保留 custom_prompt 和有序 fallback；既有 approval/configuration 回归保护选择保真。
- 无存活 Context finding。证据仅支持本次重构不改变有效配置交付；未捕获 provider 请求、未运行真实模型，不声称验证模型理解或任意模型可靠性。Node runtime/prompt 组装与模型执行实现不在 diff 中，无需为同一不变性重复模型评测。

### 验证证据与限制

- 复用 M1/M2 progress 的定向 16 tests、既有 71 tests 及 M1 32 tests 证据；主 Agent 已派发同步后复核，不重复运行全量。
- 当前固定 HEAD 的 `.e2e-refactor-672/build.log` 完成 installer build；`typecheck.log` 已全包 Done；`git diff --check ff326c351..648b5439e` 独立执行通过。
- `.e2e-refactor-672/test.log` 是同步前 772 passed / 1 knowledge-policy 等待断言超时；当前 `test-synced.log` 已记录多个 DSH 集成超时，caller 已停止本次测试进程，保留日志并计划降并发复核。caller 观察到主机 load averages 474.29 / 189.40 / 89.73；高负载是复核线索，尚未证实为所有失败根因。这些结果不能被写作全量绿灯，也不足以归因于本 diff；全局失败判真与交付门禁由主 Agent 继续处理。本审查的空 findings 不替代 CI 通过。

### 结论

指定完整 diff 未发现 maintainer 需要处理的具体代码缺陷。配置纵切与有限 RPC 关联完成；聊天、Work、Channel 上行业务及其 Row 仍属明确剩余范围，不宣称全 IM 类型迁移完成。
