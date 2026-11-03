# feat-703 Code Review

## Round 1 — full

- Reviewer: `/root/static_review_703`, independent of implementation.
- Snapshot: `1580df55443b4404a85777b707f147ae36575b33 → 6a588bde10f95b2bf8a408c80287b54595bb67ca`.
- Reviewed at: 2026-11-03 16:57 +08:00.
- Scope: complete 21-file implementation diff; current specs, unit spec/design/delta/milestone; affected shared creation/catalog, ConfigOperations, PA identity/source/lifecycle and native Context consumers.
- Checkout: `codex/feat-703-pa-create-agent`; initially clean. No source/test/design edits, no new services or commits.

## Findings

```json
[
  {
    "file": "apps/im-server/src/agent-creation.ts",
    "line": 185,
    "summary": "[P1] Recheck the initiating PA lifecycle after queue/catalog waits",
    "failure_scenario": "A PA create passes gateway.ts lifecycle admission at revision 1, then waits on the shared per-Agent queue or omitted-Skills capabilities RPC. The owner disables the PA before that wait completes. Lines 185–187 recheck only target node availability and still insert/send a new configuration operation, so a new independent Agent is created after its producer has been stopped. Reproduced with an in-memory DB and held ConfigOperations queue: {status:'created',requests:['agent.create'],created:{agent_id:'new-agent'},paLifecycle:{desired:'disabled',revision:2}}. Pass a trusted pre-submit guard into the shared service and revalidate the initiating PA generation/current authority immediately before accepting a new operation; keep receipt recovery of already accepted operations distinct.",
    "review_mode": "full",
    "status": "CONFIRMED",
    "severity": "CRITICAL"
  }
]
```

### R1-C1 evidence and limits

The production ingress guard is `apps/im-server/src/gateway.ts:413-416`; the new handler then crosses `ConfigOperations.serialized` (`control.ts:176-185`) and potentially `gatewayRequest(node.capabilities.resolve)` (`agent-creation.ts:146`) before `ops.create` at line 187. The target owner/online checks do not check the initiating PA. `PersonalAgents.authority` does not check lifecycle; its post-handler recheck also occurs after the effect. The host lifecycle check cannot retract a request already executing inside the separate IM process.

Independent reproduction used existing built HEAD modules, `openDatabase(':memory:')`, the same authenticated account/node/PA fixture facts and a fake applied Gateway configuration receipt. It held `configurationOperations(ctx).serialized('new-agent', () => gate)`, called `requireLifecycle(db,'a',1)` then `ctx.personal.handle(..., 'pa.agent.creation', {lifecycle_revision:1, action:'create', ...})`, changed the PA lifecycle to disabled/revision 2, and released the gate. No configuration operation existed before disable. Observed result:

```json
{"status":"created","requests":["agent.create"],"created":{"agent_id":"new-agent"},"paLifecycle":{"desired":"disabled","revision":2}}
```

This proves the deterministic acceptance/dispatch boundary defect; it is not a real LLM or production-run claim. The same async gap can occur without queue contention when Skills are omitted and the capabilities RPC is in flight. Recommendation is a small producer guard at the actual new-operation boundary, not a new lifecycle state machine or cancellation of an already applied result. Add a regression proving disable during that wait prevents the first `agent.create`, while querying/recovering a previously accepted operation keeps its truthful semantics.

## Coverage

- Shared Web creation/default-Skills/fingerprint/Feature preparation extraction compared with the original route; existing Web operation semantics retained.
- Owner-scoped node catalog, connection/epoch fencing and post-await owner revalidation; target computer independent from PA transport identity.
- Exact host-reserved operation ID association, same-key configuration/node conflicts, rejection/pending/unknown/committed recovery and existing-ID collision.
- Main PA and root-session gating in native ProductBridge and PA product host; original owner-message check rejects observation/other sender/represented message as new evidence.
- One fixed short tool, no dynamic schema changes, on-demand Skill, existing Skill selection and ordinary create approval.
- No DSH private imports, cross-package runtime bypass, second Agent loop, client changes or duplicated apply state engine found.

## Agent Context Review — Mode B

Triggered by new tool/schema/results, on-demand Skill and owner provenance. Consumer: main PA. Covered trusted identity → native fixed tool → ProductBridge → PA host → IM owner/source checks → shared configuration operation; tool/Skill selection and child filtering; loaded guidance, options and status meanings; ordinary history/Skill restoration paths are reused.

The native HTTP fixture in `packages/dsh-integration/tests/personal-security.test.ts:200-243` captures four actual native-runtime HTTP requests. It asserts identical serialized tools/system, a discoverable Skill summary without body in request 1, actual Skill body after load, options fields in request 3 and created result in request 4. This is actual assembly/wire evidence with controlled provider outputs; it does **not** prove real model tool choice, source-ID selection, option agreement or truthful final user wording. The model fixture deliberately has permission skipping; final product evidence must use normal real-model approval.

No separate confirmed Context-interface defect was found. R1-C1 is an execution-authority boundary defect and must be fixed regardless of prompt wording. Final representative model/product journeys were still in progress when this report was written; full verification remains provisional until their report is supplied. No cache-hit-rate claim.

## Validation evidence reused

- Caller-provided versioned run: 72 relevant IM/PA/catalog tests; 50 native PA/context + host + contract tests; build/typecheck; pytest 129 + ruff passed.
- Independently inspected local `.feat703-backend-tests.log`: `vitest run --maxWorkers=4`, 210 files / 1121 tests passed, started 16:48:41, duration 313.09 seconds.
- Independent in-memory lifecycle reproduction above.
- No additional speculative review loop or duplicate broad suite was run.

Verdict: one confirmed blocking finding. Final product acceptance evidence pending separately.

## Round 2 — targeted closure of R1-C1

- review_mode: `closure`
- finding_origin_head / pre_fix_head: `6a588bde10f95b2bf8a408c80287b54595bb67ca`
- validated_at: `f8800afaa8a2b60b9a3577c4cc9ea85e681fd950`
- reviewed delta: `6a588bde10f95b2bf8a408c80287b54595bb67ca..f8800afaa8a2b60b9a3577c4cc9ea85e681fd950`, focused on the new admission callback, associated authority/receipt paths, three regressions and design clarification. R1 full-review coverage remains applicable to unchanged code.
- reviewed at: 2026-11-03 17:06 +08:00.
- focus finding: R1-C1 — **closed**.

The shared service calls synchronous `beforeCreate?.()` at `apps/im-server/src/agent-creation.ts:187`, after the per-Agent queue and any omitted-Skills catalog await and before the first `ops.create`. The callback supplied at `personal-agent.ts:403-406` resolves current server authority, checks the original initiating lifecycle revision and rechecks current access to the original owner message. There is no intervening await before ConfigOperations synchronously authorizes and inserts the operation. This closes the demonstrated late first-acceptance/dispatch gap for disable, binding revocation and source revocation.

An already associated pending/committed/rejected operation takes its existing recovery/result branch before the new callback. A status request without an accepted operation returns `not_started` before calling the shared service. Thus the fix does not turn historical result confirmation into a new creation intention or prevent truthful receipt recovery. The optional callback leaves existing Web creation behavior unchanged.

Validation:
- Independently ran `pnpm exec vitest run apps/im-server/tests/personal-agent-creation.test.ts --maxWorkers=1` on the frozen fix head: **1 file / 9 tests passed**, started 17:05:57, duration 606 ms.
- Three new cases hold the real shared queue, revoke disabled/binding/source authority, then release; each rejects and asserts zero receipt dispatch and zero configuration operation. Existing pending/recreated-service recovery remains green.
- Caller supplied 28 IM creation/config/catalog tests and IM build/typecheck passed; reused without duplicating its broader run.
- Context Mode B delta: no tool/schema/Skill/model-visible result change. The fix enforces the trusted authority at the execution boundary; the prior serialized Context evidence remains applicable.
- Design delta distinguishes transport `unknown` from accepted-operation `pending` and states the effective-authority invariant; it does not silently weaken the original contract.

Surviving code findings in this closure:

```json
[]
```

Verdict: **R1-C1 closed; no remaining confirmed code findings.** Final real-model/product evidence remains pending separately; this code closure does not assert M1 product acceptance.

## Final snapshot retention

At `e106b07bd1db3d20947682de7805ce1fe1d809ab` (rebased PR base `9762ad3b44ca3cb2eebd6f2025fe8f169a544de3`), product source/tests/dependencies/architecture have no diff against the reviewed `f8800afaa8a2b60b9a3577c4cc9ea85e681fd950` snapshot. R1 full review and R2 closure remain applicable; **R1-C1 closed, no surviving code findings**. The independent real-model/product report is now committed in `acceptance.md`; the prior product-evidence gap is closed in verification Round 3. The corrected-delta reconciliation is aligned. Historical findings and evidence limits above remain preserved.

## Round 3 — 用户追加工具开关 · patch review

- reviewer: `/root/static_review_703`，独立 reviewer。
- review_mode: `patch`；`b2b9a8c0dbec963590c58b3847562bbf2e13502d..37b1a70775c40f4162d6a3184658e12f29ec1802`。
- validated_at: `37b1a70775c40f4162d6a3184658e12f29ec1802`；实现提交 `0a11feaa9`。
- executed_base: `492b72603cebc5f904f7001b12e3d4475ce55639`（本次 origin/main）。
- 时间：2026-11-03 18:02 +08:00。范围仅用户追加的配置页独立关闭/重开及相关消费链；main 新增 feat-705 文档不属于本 patch 产品实现。
- retained_from: 原 full review、R1-C1 closure、最终证据对账中未变的身份/来源/目标/请求恢复/创建语义。未重复完整审查或扩大为新架构审查。

### Findings

```json
[]
```

### 检查结果

- `packages/product-contracts/src/capabilities.ts:53-56` 将 agent_creation 移出 fixedTools，Web/iOS 继续消费同一 fixed_tools 目录和白名单。现有配置页选择器因此可撤回它；无需新增字段或控件。
- `apps/im-server/src/personal-agent.ts:462` 在首次 PA candidate 的持久白名单显式加入 agent_creation。active PA/recovered operation 路径不会因启动或重试被补写。新建默认与后续主人取消选择职责清楚。
- `PersonalAssistant.createAgent:117` 在转发前检查当前白名单；显式空数组同样拒绝。undefined 保留现有“未配置白名单”的发现语义，与 runtime ToolSelection 一致。主 PA 身份检查和既有 IM 来源/lifecycle 守卫保留。
- 取消选择沿既有 `agent-config.ts:172-184` 收缩工具面；重开沿完整 configuration.apply；`capability-state.ts:45-70` 根据移除工具和真实 busy 保护拒绝不安全收缩。没有取消已接受配置操作或另建状态引擎。
- Skill 的选择与正文不授予额外执行能力；新增指导要求工具关闭时说明配置页开启路径，禁止借其他工具绕过。工具切换不自动改写 Skill 选择。

### Agent Context Review — Mode B（本次 delta）

Consumer 为主 PA；Surface 为实际可调用工具集合/serialized schema、已加载 Skill 历史及产品派发准入。开启时短 schema 保持原定义，关闭/重开是用户主动配置变更，不混同创建流程内动态加载，也不承诺配置变更时前缀不变。

核读 `packages/dsh-integration/tests/personal-security.test.ts:200-260` 与 `.feat703-toggle-tests.log`：4 文件 / 67 测试通过；fixture 经真实原生 DSH/HTTP 获得 **8 次序列化模型请求**。前4次保留原按需Skill与stable tools/system证明；关闭后第5/6次均无 agent_creation schema，受控模型强制旧调用产生 isError，product.call 数保持2；重开后第7/8次工具序列化值与初始完全相同，product.call 数变3。PA host测试另证明当前空白名单拒绝且没有转发；共享能力测试证明关闭/重开不改变已选择Skill；首次PA测试证明默认名单。

这是实际组装与执行拒绝的机制证据；provider输出仍受控且fixture跳过审批，不能据此声称真实模型已经理解关闭提示或真实配置页旅程通过。该产品增量验收仍待独立 reviewer 报告，见 verification 对应 evidence 项。本次未发现可确认 Context接口缺陷。

结论：**patch code review pass；无新增存活代码问题。** 真实配置页关闭/保存/重开证据 pending，不以静态审查代替。
