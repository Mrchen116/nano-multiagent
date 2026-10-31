# Verification Report: refactor-679-agent-context-optimization

> Original validation snapshot: baseline HEAD `4b27d962c1cc09a27a567619bd5cabc3db2ee934` → **dirty pre-fix implementation**. Latest scoped repair recheck is recorded below; a final freeze was not assessed in this round. Destination branch is `unit/feat-676`, not main.

**Provisional independent verifier report, not final gate approval.** The latest scoped repair recheck below supersedes the original defects only for paths independently rerun. The retained historical body refers to witnessed pre-fix code; a separate final frozen review remains necessary. The reviewer did not modify implementation, tests, design or delta-specs.

Fresh independent context uses the approved current-model inheritance substitute because this SDK cannot select model/effort; **this is not a claim that `gpt-6.1-sol/high` was configured**. Responsibilities remain separate: this report checks implementation/spec/design consistency; it does not replace the parent’s real-product acceptance.

## Latest scoped repair recheck — not a final verdict

The parent explicitly limited this round to the two earlier CRITICAL counterexamples and one business-semantic WARNING. All rechecks used the approved inherited-model substitute and Node v24.22.1. Evidence and replayable actual-native setup are in [review-witnesses C/D](<docs/changes/refactor-679-agent-context-optimization/review-witnesses.md#c-scoped-node24-repair-recheck-not-a-final-gate>); [code-review](<docs/changes/refactor-679-agent-context-optimization/code-review.md#latest-scoped-repair-recheck--not-a-final-gate>) records the same bounded disposition.

| Scoped requirement | Independently rechecked result |
|---|---|
| Independent authorized input during authority outage | Ordinary human Feishu/web input reaches provider with current D9, even Task feature off; pending originals are excluded and remain prepared |
| Fail-closed automatic Task input and recovery | Task-only produces no provider and no extra prepare in the bounded idle observations; changed rechecks once; authority restoration consumes the stable original natively exactly once |
| Revocation/consumption in preexisting unread cursors | Actual public-source Global/Inbox old cursor returns no never-consumed revoked Task and no directly consumed duplicate; saved ordinary history is preserved |
| Native hard Task-tool gate | Actual feature-off allowlisted apply is denied before product offline; after authority catch-up in the same session, one new apply reaches product exactly once |
| Original notice semantics | Actual generator states explicit old/new assignee roles, directed old/new relation and dependency endpoints, references and directly affected owners |

The native hard-gate omission was caught during this recheck and repaired by the parent. A second real native counterexample then exposed a cached unavailable flag sticking after feature-off recovery; it was also independently reported, fixed with current per-tool snapshot revalidation, and the exact counterexample rerun succeeded. These intermediate defects and their evidence remain recorded, not erased.

**Scoped disposition: earlier three counterexamples and both repair-chain residuals are repaired in the paths rerun; 0 unresolved scoped findings.** Latest full scoped native job `bash-2f630a1037a04d46` exited 0 with relevant artifact hashes unchanged before/after. This does not independently close M1, the full 20-scenario execution matrix, true-model/product evidence, child cold isolation or any final frozen review. No final PASS or PR recommendation is authorized.

## Historical pre-fix summary

Everything from this historical summary through the original outcome below describes the first review snapshot. Its issue counts and marked deviations are superseded only where the scoped result above explicitly rechecked them; other entries were not reevaluated in this round. The final-gate evidence status must be established separately.


| 维度 | 结果 |
|---|---|
| Completeness | 20/20 active-delta scenarios mapped to production and inspected tests; 0/1 M1 independently signed off pending final freeze and exit evidence |
| Correctness | 3 confirmed pre-fix implementation defects; all other mappings are static evidence, not final execution PASS |
| Coherence | Main architecture followed; original-message business content, terminal revocation projections and independent-input degradation deviate |

**2 CRITICAL implementation issues, 1 WARNING implementation issue and 1 WARNING evidence/freeze gap. Fix/close before PR. No PR recommendation or final PASS.**

## Completeness

- Milestones: [M1-context-flow](<docs/changes/refactor-679-agent-context-optimization/design.md#L770-L784>) is the sole milestone. Its implementation is present across IM, Node, PA and integration, but **0/1 independently signed off**; R1–R6/W1–W5 require final evidence handoff. This is an evidence status, not a claim that no work is implemented.
- Active deltas: [IM Task Graphs](<docs/changes/refactor-679-agent-context-optimization/specs/im/task-graphs.md>) has 6 scenarios; [Gateway Task Graphs](<docs/changes/refactor-679-agent-context-optimization/specs/gateway/task-graphs.md>) has 10; [Agent Capabilities](<docs/changes/refactor-679-agent-context-optimization/specs/gateway/agent-capabilities.md>) has 4. All 20 are mapped below.
- Read the approved [design](<docs/changes/refactor-679-agent-context-optimization/design.md>), [Gate 2 review](<docs/changes/refactor-679-agent-context-optimization/design-review.md>), current [architecture](<SPEC.md>), current Gateway/IM task contracts, current PA/capabilities contracts, and actual dirty implementation plus untracked additions. No parent conclusion substitutes for this review.
- Prototype / Reference coverage: **N/A**. No frontend prototype/reference must-match contract is introduced; this unit changes backend/context behavior, not a new visual contract.
- Executed independently: only two explicitly authorized narrow witnesses, both exit 0: native ordinary external input with disabled Task feature and disconnected center; public-source partial-read cursor followed by terminal Task revocation. Details and built-input fingerprints are in [review-witnesses](<docs/changes/refactor-679-agent-context-optimization/review-witnesses.md>). No full regression, extra HTTP stack, production access or unrelated model suite was duplicated.

## Correctness

“Inspected” below means the test source was reviewed, not that this reviewer ran it. “Pending final evidence” is not a code defect or an execution PASS.

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| IM: 改派双方获知 | [task-notifications](<apps/im-server/src/task-notifications.ts#L21-L52>) | [task-context-live](<apps/im-server/tests/task-context-live.test.ts>) inspected | **偏离**: unlabelled mentions do not state from whom to whom |
| IM: 要求或关系更新 | [task-notifications](<apps/im-server/src/task-notifications.ts#L23-L51>) | [task-context-live](<apps/im-server/tests/task-context-live.test.ts>) inspected | **偏离**: relation endpoints/business direction absent; requirement-update entry exists |
| IM: 暂缓／关闭逐层传达 | [task-notifications](<apps/im-server/src/task-notifications.ts#L25-L29>) | [task-context-live](<apps/im-server/tests/task-context-live.test.ts>) inspected | Static mapping present; final evidence pending |
| IM: 结果向上反馈 | [task-notifications](<apps/im-server/src/task-notifications.ts#L28>) and [delivery guidance](<packages/dsh-integration/src/task-execution.ts>) | [task-execution](<apps/im-server/tests/task-execution.test.ts>) and [task-feedback](<packages/dsh-integration/tests/task-feedback.test.ts>) inspected | Static mapping present; actual fixed-chat delivery evidence pending |
| IM: 成员失去任务处理资格 | [access authority](<apps/im-server/src/task-context-access.ts>), [sync](<packages/personal-assistant/src/task-context.ts>), [native removal](<packages/dsh-integration/src/task-context.ts>), [Inbox revoke](<packages/personal-assistant/src/inbox.ts#L233-L235>) | [IM revocations](<apps/im-server/tests/task-context-revocations.test.ts>), [native originals](<packages/dsh-integration/tests/task-context-originals.test.ts>), reviewer cursor witness | **偏离**: saved unread cursor can first expose revoked Task |
| IM: 无业务变化与通知后的行动 | [taskNotices](<apps/im-server/src/task-notifications.ts#L42>), [transactional relay/index](<apps/im-server/src/messaging.ts#L568-L618>) | [IM live](<apps/im-server/tests/task-context-live.test.ts>) and [migration](<apps/im-server/tests/task-context-migration.test.ts>) inspected | Static no-op/idempotent mapping present; final execution pending |
| Gateway: 停止通知延迟消费 | [execution fence](<packages/dsh-integration/src/task-execution.ts>), [Task stop authority](<apps/im-server/src/task-graphs.ts#L838>), [context driver](<packages/dsh-integration/src/task-context.ts>) | [native task-context sync](<packages/dsh-integration/tests/task-context-sync.test.ts>) inspected | Static passive-original/fence mapping present; final real behavior pending |
| Gateway: 外部变更与离线恢复 | [fixed-cut messaging](<apps/im-server/src/messaging.ts#L568-L618>), [durable PA sync](<packages/personal-assistant/src/task-context.ts>), [native pre-step](<packages/dsh-integration/src/task-context.ts>) | [PA >32 sync](<packages/personal-assistant/tests/task-context.test.ts>), [native sync](<packages/dsh-integration/tests/task-context-sync.test.ts>), reviewer no-Task/offline witness | Task fail-closed mapping exists; **independent-input availability regression confirmed** |
| Gateway: 内部对象重建而事实未变 | [Task state driver](<packages/dsh-integration/src/task-execution.ts>), [original-ID evidence](<packages/personal-assistant/src/task-context.ts>) | [native originals](<packages/dsh-integration/tests/task-context-originals.test.ts>) inspected | Static stable-ID/evidence mapping present; final execution pending |
| Gateway: 首次等待及校验失败 | [IM Task mutation](<apps/im-server/src/task-graphs.ts>) and [schedule evidence](<packages/dsh-integration/src/schedule-evidence.ts>) | [Task execution](<apps/im-server/tests/task-execution.test.ts>) inspected | Static owner/root/enabled/future validation mapping; final execution pending |
| Gateway: 安静等待与安排失效 | [Task execution driver](<packages/dsh-integration/src/task-execution.ts>) | [execution limits](<packages/dsh-integration/tests/task-execution-limits.test.ts>) and [reminder batch](<packages/dsh-integration/tests/task-reminder-batch.test.ts>) inspected | Static all-tasks/quiet-wait mapping; final execution pending |
| Gateway: 关联 Schedule 被删除 | [durable deletion service](<packages/personal-assistant/src/schedule-deletions.ts>), [Node UI/tool wiring](<apps/node/src/main.ts#L285-L293>) | [deletion service](<packages/personal-assistant/tests/schedule-deletions.test.ts>) and [native deletion](<packages/dsh-integration/tests/schedule-deletion-native.test.ts>) inspected | Static independent repair mapping; parent native/restart evidence pending |
| Gateway: 提前答复与定时复查 | [schedule-source fold](<packages/dsh-integration/src/schedule-evidence.ts>), [Task driver](<packages/dsh-integration/src/task-execution.ts>) | [reminder batch](<packages/dsh-integration/tests/task-reminder-batch.test.ts>) and [native deletion](<packages/dsh-integration/tests/schedule-deletion-native.test.ts>) inspected | Static stale-trigger and coalescing mapping; final execution pending |
| Gateway: 一轮结束仍有可执行责任 | [automatic continuation driver](<packages/dsh-integration/src/task-execution.ts>), [Task guidance](<packages/dsh-integration/src/features/task-graphs.ts>) | [task execution](<packages/dsh-integration/tests/task-execution.test.ts>) and [child context](<packages/dsh-integration/tests/task-child-context.test.ts>) inspected | Static all-owned doing/waiting, genuine-continuation-only mapping; final wire/behavior pending |
| Gateway: 保存等待说明或提交结果 | [effective result delivery hints](<packages/dsh-integration/src/task-execution.ts>) | [task feedback](<packages/dsh-integration/tests/task-feedback.test.ts>) and [child context](<packages/dsh-integration/tests/task-child-context.test.ts>) inspected | Fixed-chat/child-parent guidance exists; real delivery pending |
| Gateway: 续期、回执重放与发送未确认 | [Task delivery guidance](<packages/dsh-integration/src/task-execution.ts>), [Global durable publication](<packages/personal-assistant/src/global-agent.ts>) | [task feedback](<packages/dsh-integration/tests/task-feedback.test.ts>) and [Global recovery](<packages/personal-assistant/tests/global-agent.test.ts>) inspected | Static no-op/retry/unknown mapping; actual no-duplicate delivery pending |
| Capabilities: 首次处理请求与能力更新 | [current pre-step order](<packages/dsh-integration/src/context-order.ts>), [effective feature context](<packages/dsh-integration/src/agent-config.ts>) | [actual provider order](<packages/dsh-integration/tests/context-order-provider.test.ts>), [context defaults](<packages/dsh-integration/tests/agent-context-default.test.ts>) inspected | Native/HTTP capture fixture exists; actual window/summary and real-model evidence pending |
| Capabilities: 去重与按需读取 | [English policy sources](<packages/dsh-integration/src/policy/sources.ts>), [PA defaults](<apps/im-server/src/personal-agent-defaults.ts>), [root-only projection](<packages/dsh-integration/src/context-visibility.ts>) | [context defaults](<packages/dsh-integration/tests/agent-context-default.test.ts>) and [child context](<packages/dsh-integration/tests/task-child-context.test.ts>) inspected | Static source/policy preservation; Memory/Skill affected-matrix evidence pending |
| Capabilities: 用户删除独立或 Task 关联的 Schedule | [durable deletion](<packages/personal-assistant/src/schedule-deletions.ts>), [Node settings delete](<apps/node/src/main.ts#L285-L293>) | [deletion service](<packages/personal-assistant/tests/schedule-deletions.test.ts>) and [native deletion](<packages/dsh-integration/tests/schedule-deletion-native.test.ts>) inspected | Separate schedule-change and Task-repair records exist; real-user/real-Agent scenarios pending |
| Capabilities: 重试、恢复和停止边界 | [deletion intents](<packages/personal-assistant/src/store.ts>), [recovery](<packages/personal-assistant/src/schedule-deletions.ts>), [passive Task execution sources](<packages/dsh-integration/src/task-execution.ts#L16>) | [deletion crash recovery](<packages/personal-assistant/tests/schedule-deletions.test.ts>) and [native deletion](<packages/dsh-integration/tests/schedule-deletion-native.test.ts>) inspected | Durable phases separate missing/unavailable; final restart/stop execution pending |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| Runtime only via declared public integration exports; no second loop/private patch | Static inspection: yes; final dependency contract pending | [integration](<packages/dsh-integration/src/index.ts>), [Node](<apps/node/src/main.ts>), [owned sessions](<packages/dsh-integration/src/owned-sessions.ts>) |
| Reorder only current native runtime-context then skill-catalog; preserve source/history and independent memory | Static inspection: yes; final window/summary/memory matrix pending | [context order](<packages/dsh-integration/src/context-order.ts>), [provider fixture](<packages/dsh-integration/tests/context-order-provider.test.ts>) |
| One original transactional business notice, same original ID, no duplicate private snapshot/wake | Transport mapping yes; business facts incomplete | [task notices](<apps/im-server/src/task-notifications.ts>), [message index](<apps/im-server/src/messaging.ts#L568-L618>), [native Task input](<packages/dsh-integration/src/task-context.ts>) |
| Authoritative fixed cut, durable ingest before cursor, claimed-candidate revalidation; consumed history preserved | Mostly yes; alternate unread snapshot revocation incomplete | [PA Task context](<packages/personal-assistant/src/task-context.ts>), [native filter](<packages/dsh-integration/src/task-context.ts>), [Inbox cursor](<packages/personal-assistant/src/inbox.ts#L293-L317>) |
| Independent-input degradation allowed; unavailable Task originals/automatic steps remain pending without hot loop | No at witnessed pre-fix snapshot | [unconditional native prepare](<packages/dsh-integration/src/task-context.ts#L21-L25>), [witness A](<docs/changes/refactor-679-agent-context-optimization/review-witnesses.md#L10>) |
| Full doing/waiting prompt only genuine auto-continuation; child hides inherited root-only guidance, canonical evidence remains | Static mapping present; child cold-resume final execution pending | [Task driver](<packages/dsh-integration/src/task-execution.ts>), [visibility](<packages/dsh-integration/src/context-visibility.ts>), [owned child rehydration](<packages/dsh-integration/src/owned-sessions.ts>) |
| Native future schedule evidence; separate durable user deletion and Task repair | Static mapping present; final native/product evidence pending | [schedule evidence](<packages/dsh-integration/src/schedule-evidence.ts>), [deletion service](<packages/personal-assistant/src/schedule-deletions.ts>) |
| English Nano-owned text; Task is not consent; worker P2 distinct from reviewer P2R | Static inspected policy mapping yes; real behavior pending | [policy sources](<packages/dsh-integration/src/policy/sources.ts>), [capability defaults](<packages/dsh-integration/src/agent-config.ts>) |

### Prototype / Reference Contract

N/A — no frontend prototype or reference contract. The explicit runtime/provider/product evidence contract remains mandatory and is not waived by this N/A.

## Historical pre-fix issues

### CRITICAL（提 PR 前必须修）

1. **Independent external conversation is blocked by unrelated IM Task synchronization.** [Native pre-step:21–25](<packages/dsh-integration/src/task-context.ts#L21-L25>) calls authoritative sync for every root. The actual native witness has `task_graph=false`, empty Task state and a normal Feishu question; it terminates with `CENTER_OFFLINE_NO_TASKS` before the provider. Preserve the [approved independent-input degradation](<docs/changes/refactor-679-agent-context-optimization/design.md#L157-L191>) while keeping old Task originals/automatic steps pending and non-spinning. Add/review both the independent-input and stale-Task cases. Evidence: [witness A](<docs/changes/refactor-679-agent-context-optimization/review-witnesses.md#L10>).
2. **Revoked unconsumed Task survives a frozen unread cursor.** [Inbox revocation:233–235](<packages/personal-assistant/src/inbox.ts#L233-L235>) does not terminalize snapshots; [cursor read:293–317](<packages/personal-assistant/src/inbox.ts#L293-L317>) first returns the Task after revocation despite `check.sources=[]`. Invalidate/filter affected unread fragments and saved-but-unconsumed read projections without rewriting consumed native history; cover public-source partial-read/revoke and direct-consume deduplication. Evidence: [witness B](<docs/changes/refactor-679-agent-context-optimization/review-witnesses.md#L56>).

### WARNING（提 PR 前必须修）

1. **Business notices omit required relation endpoints/direction and reassignment roles.** [Notice generator:21–51](<apps/im-server/src/task-notifications.ts#L21-L51>) says generic updated/reassigned and stores only one task reference. Include both relevant task identities, old/new relationship business direction, and explicit from-old-to-new assignee wording. Preserve one original message, qualified mentions and old/new parent-owner attention. This is an implementation mismatch, not justification to weaken the [active IM delta](<docs/changes/refactor-679-agent-context-optimization/specs/im/task-graphs.md#L11-L24>).
2. **Final source freeze and M1 execution evidence not handed over.** Before a final verifier decision, provide baseline→final source fingerprint including untracked files; narrow/final default regression and runtime dependency/docs-check results; child/deletion/restart fixtures; isolated real-stack R1–R6; true-model scenarios; first/running/offline/**actual window or summary** provider captures; and the affected Memory/Skill/PA-source matrix or valid baseline locators required by [design:778–783](<docs/changes/refactor-679-agent-context-optimization/design.md#L778-L783>). This is missing verification evidence, not an invented production defect. Do not merge or claim PASS from static mapping or transport stubs alone.

### SUGGESTION（可以修）

None beyond required closure above. Avoid spec changes that merely normalize confirmed defects.

## Corrected Delta Reconciliation

Mode is full design/spec consistency plus active-delta correction assessment; no delta was edited by this reviewer.

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| [IM: 改派双方获知 / 要求或关系更新](<docs/changes/refactor-679-agent-context-optimization/specs/im/task-graphs.md#L18-L24>) | [notice generator](<apps/im-server/src/task-notifications.ts#L21-L51>) omits required business facts | [IM live fixtures](<apps/im-server/tests/task-context-live.test.ts>) inspected; repair/retest pending | **implementation-mismatch**; delta already states approved intent |
| [IM: 成员失去任务处理资格](<docs/changes/refactor-679-agent-context-optimization/specs/im/task-graphs.md#L37-L41>) | [Inbox snapshots](<packages/personal-assistant/src/inbox.ts#L233-L317>) bypass terminal direct-context revocation | [exact public cursor witness](<docs/changes/refactor-679-agent-context-optimization/review-witnesses.md#L56>) executed | **implementation-mismatch**; keep consumed-history distinction in delta |
| [Gateway: 外部变更与离线恢复](<docs/changes/refactor-679-agent-context-optimization/specs/gateway/task-graphs.md#L13-L18>) + retained [local autonomy](<SPEC.md#L22>) | [unconditional sync](<packages/dsh-integration/src/task-context.ts#L21-L25>) overreaches Task fail-closed boundary | [native no-Task/offline witness](<docs/changes/refactor-679-agent-context-optimization/review-witnesses.md#L10>) executed | **implementation-mismatch** against approved design/current invariant; no delta weakening needed |
| Other active Gateway Task/Capabilities and IM scenarios | Production/test mappings above | Test sources inspected; execution/product handoff pending | Statically mapped; final alignment **not yet verified** |

### Uncovered Observable Behavior

No intended new observable behavior requiring an additional active-delta requirement was identified. The unconditional offline-conversation block is an unintended regression of a retained invariant, not a new desired behavior to document. Child projection, ordering, default guidance, original Task context, Schedule deletion and fixed-chat delivery are covered by active deltas/design and existing current contracts.

**Historical outcome: implementation-mismatch (pre-fix snapshot).** The latest scoped disposition above records independently rechecked repairs, not a replacement final unit verdict. No independently established delta-mismatch; final frozen evidence and gate are still required before recommending PR.
