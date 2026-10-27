# perf-666 Code Review

## Round 1

- reviewer: `/root/static_review`，未参与实现。
- review_mode: `full`
- executed_base: `a78e9498560f6943e934bc29a68e0ac9918270f1`
- validated_at: `25c6d866fb2423fdb0e2d941deabe48a33dd7f76`
- reviewed_at: `2026-10-27T12:08:00+08:00`（分钟级）
- scope: 上述完整 diff、受影响的消息投递与身份权限调用链、motivation/design/current specs，以及性能实验原始脚本和输出。共享现场中另有主流程修复的 feat-665 blueprint 文档改动，不属于本次固定版本审查。

## Verdict

**Approved — 0 confirmed / 0 plausible findings。**

```json
[]
```

这是固定版本代码审查结论，不代替完整 CI 或真实产品验收。

## Evidence and coverage

1. **流式 buffer 生命周期。** `packages/personal-assistant/src/single-thread.ts:436-496` 在首片安排 50ms timer，4096 code units 提前触发，ACK 期间仅累积待发文本；flush 中每批取走当时的首尾索引和正文，下一批在前批 ACK/失败处理后发送。end 等待 flush 完成才删除 stream 并 reconcile，reconcile 原有 stream 存活检查继续阻止 completed 抢跑；modelCheck 先 flush，stop 取消订阅后 flush，cancelAgent 清理 timer 和待发正文。慢 ACK、失败和最终 durable answer 的路径未见新增重放或缺失。
2. **输出边界。** 每批仍检查 turn inputs、delivery 的 sending 状态、fallback attempt 数和 explicit-delivered 标记；群聊仍在 stream 入口抑制草稿，最终 NO_REPLY/HEARTBEAT_OK 处理未改。buffer 的 pending publication 在外发前持久记录，避免未到 timer 的内容被 modelCheck 误当成未发布；ACK 丢失后的最终全文覆盖仍由既有 message_completed 路径承担。
3. **服务端窄投影与权限。** `apps/im-server/src/gateway.ts:870-900` 的 sender ID 推导与 `Messaging.actor` 相同。窄查询保留 message sender、conversation、lifecycle、delivery status；随后的 node/Agent 归属、payload 与 message 双 lifecycle、PA ownerConversation 及 conversation write 访问检查均保留。message_delta 幂等写入、running 检查、正文拼接与事件发布逻辑不变，非 delta 继续走完整 message 投影。
4. **watchdog 等价性。** `apps/im-server/src/server.ts:315-340` 用相同 TEXT created_at 的倒序 LIMIT 1 代替 MAX，保留无事件 fallback、严格 `< cutoff`、仅 running、正文保留和失败事件。`schema.sql:418-420` 的 latest/partial 索引对应查询，未新增第二份活动状态或数据格式转换。
5. **联系人保真。** `apps/im-server/src/contacts.ts:7-87` 的候选过滤与原 SQL 等价；详情按 ID，列表每批 100 个候选并寻找第 51 个可见匹配项。owner 查询按 owner_id 取首个真人，仍由 canAccessSpace 判定 owner 资格；真人 self/active、普通 Agent 空间资格、active PA 公共联系资格与 PA 展示裁剪保留。personal_agent_bindings.agent_id 的 UNIQUE 约束避免 JOIN 放大。Unicode 搜索仍为 JavaScript toLowerCase/includes；cursor、kind、可见性过滤和第 50 项 next_cursor 保持原契约。
6. **实现复杂度和职责。** 新 contacts 模块仅共享列表/详情的装配与资格逻辑，未引入缓存、跨包相对依赖、DSH 私有导入、额外后台状态或新的运行循环。diff 与设计范围一致。

## Validation

独立在 validated_at 执行：

- `pnpm exec vitest run packages/personal-assistant/tests/model-fallback.test.ts apps/im-server/tests/contacts.test.ts apps/im-server/tests/watchdog.test.ts`：3 files / 10 tests passed，2026-10-27 12:06，本机 2.86s。覆盖慢 ACK 合并、ACK loss、final 顺序、modelCheck/stop/cancel、Unicode/隐藏候选分页、实时 owner 资格和 watchdog 边界。
- `pnpm exec vitest run apps/im-server/tests/e2e/server.test.ts packages/personal-assistant/tests/interactive-replies.test.ts packages/personal-assistant/tests/agent-lifecycle.test.ts`：3 files / 15 tests passed，2026-10-27 12:07，本机 11.19s。覆盖真实服务 HTTP/WS delta 幂等与完成历史、显式发送结束哨兵抑制、生命周期停用清理等既有保护。
- `git diff --check executed_base..validated_at`：passed。
- 核对 `M1-hot-paths/evidence/performance.md` 及 `/tmp/perf-666-evidence/.perf-666-benchmark.ts`、`.perf-666-stream.ts`、`.perf-baseline-single-thread.ts`、`/tmp/perf-666-benchmark.log`、`/tmp/perf-666-stream.log`。同进程基线源码对照、数据生成、完整性断言、SQL 结果集合比较和 EXPLAIN 支持报告的有限结论。未把合成内存库/relay 实验推断成生产 RTT 或并发性能。

## Context impact assessment

读取 `agent-context-review` 与通用规范，沿 `apps/node/src/main.ts:391` → integration ModelPolicy/model-fallback 的 host check 消费链核对。变更触及发布事实等待时点，但未改 prompt、工具定义、输入/历史选择、Skill/Memory、注入文本或 fallback 的信息内容；modelCheck 仍返回持久 publication 是否存在，新增先 flush 修复缓冲引入的时序差异。本次不触发完整 Implementation Context Review，无新增模型可见 Context finding。上述测试为传输/宿主行为证据；未捕获真实 provider 输入，不声称验证了模型的全局行为可靠性。

## Remaining delivery evidence

主流程负责完整本地/远端 CI 及独立真实产品验收；本报告未以尚未完成的 CI 作为代码缺陷，也未据此宣称整个 unit 已可交付。

## Round 2 — evidence closure / retained

- reviewed_at: `2026-10-27T12:25:00+08:00`（分钟级）。
- review_mode: `closure`，仅核对证据收口与版本适用性，不重复完整代码审查。
- implementation validated_at retained: `25c6d866fb2423fdb0e2d941deabe48a33dd7f76`。
- executed_base retained: `a78e9498560f6943e934bc29a68e0ac9918270f1`。
- final-sync snapshot: `54b1214c8d52dc1645df3b526756b9b2d2353a2a`；effective_base: `69d01e4557bcc87a5f7194dcb947c7473ead20d9`；acceptance/validation evidence commit: `4a8734d02bf48ab1201957cd4428caaf50dad328`。
- final effective_base: `1e2b6dbf6d1b2590a9cee7a6d09171852814ca41`；effective_through: `f907e2978fd53c7d0e0f6663bc51110e19629ce1`（经文档与证据 delta 失效判断后）。

**Approved retained，findings `[]`。** 独立核对 25c6 → 54b 的 changed paths 仅为 feat-665 原始附件链接说明、feat-667 文档和本 unit 两报告；54b → 4a873 仅新增 acceptance/validation。产品源码、schema、测试、构建配置及依赖未改，Round 1 的 correctness、权限、buffer 生命周期与 Context 影响结论继续成立。

核对独立 acceptance Round 3、validation record 及其原始日志；并从 `responses-events.jsonl` 重新计算 270 个唯一 delta、最终 1,868 字、增量拼接=completed=HTTP history、01–50 编号恰好一次，补齐真实渐进输出证据。后端受控全量复跑 142 files / 766 tests、前端 108 files / 1031 tests、Python 70 tests，以及 build/typecheck 等本地验证已通过。首次默认并发的 workspace-tools 90s timeout 与单独 35.31s 通过均保留；资源竞争仍只是解释假设，不作为确定归因。

本地代码审查和证据收口无未闭项。远端 CI 按交付流程在 PR 后执行，不作为本轮本地审查循环的前置，也不声称已经通过。后续若仅移动本 unit 到 archive、修正移动后的相对链接及追加收尾/CI 事实，可保留本代码结论；须核对实际 diff，若引入源码、契约或验证条件变化则按真实 delta 复审。

最后同步补核：4a873 → f907 仅 feat-667 的 design、design-review、delta-spec 与 M1骨架4份文档；25c6 → f907 的产品/测试/构建路径仍无差异。上述结论继续retained，actual validated_at/executed_base不变。
