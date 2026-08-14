# feat-523 — 验收报告

> 对齐: `spec.md` 验收标准
>
> Validation snapshot: `6683c3f10 → 1c15711ba32bf0eaaa1238a3871dc1599fa784f4`

## Verdict

**pass**

**Highest Required Action:** `pass`

在专用、非生产的 Feishu 测试身份下，正常用户消息收到了一条普通最终回复；模型和 context 百分比都只出现在该回复正文之后。测试 profile 的外部 footer fixture 是显式开启的，默认运行配置没有被改写。

## User Journeys Exercised

1. **Feishu ordinary final reply (exact validated head).** Restarted the isolated IM + Gateway + Feishu listener from `1c15711`, ran `scripts/e2e-feishu-probe.py`, then read the test user's real P2P conversation. The fresh final Bot post at 2026-08-14 22:57 CST (position 356) was:

   ```text
   Received — `nano-e2e-feishu-probe-09d6d5dde41448c1` (Feishu, 22:57 CST). I'm here and working normally. Anything you'd like me to do?

   deepseek:deepseek-v4-flash · 3%
   ```

   The message was a single ordinary Bot post following the user's probe; no second standalone footer bubble appeared.

2. **Internal shadow boundary.** The same isolated-stack runner checked the corresponding Web IM shadow and reported the original assistant text only, without the external footer. This is the required shadow check from the reviewer runbook; the external Feishu observation above is the primary user-visible evidence.

3. **Default-off control (same review).** Before the dedicated fixture was added, the same isolated test profile was restarted with its default-off config and a real Feishu normal reply stayed as plain body text. The new fixture makes the enabled precondition explicit without altering production/local defaults.

The Mac was locked when attempting a second native-client capture, so this report records the independently read real-platform message evidence rather than duplicating a screenshot. The orchestrator has the visual capture from the same isolated flow for user handoff.

## Reference Artifacts Reviewed

N/A — the unit has no frontend prototype, visual reference, or must-match layout contract. Its visible contract is the final Feishu message text in `spec.md`.

## Issues

None.

## Side Findings

- The current dedicated profile exercises the only shipped external channel (Feishu). Scenarios referring to a future second external channel have no current product surface to exercise; their shared-policy guarantee remains covered by the unit's automated delivery/config checks rather than a fictional client.

## Acceptance Criteria Coverage

### Requirement: 外部 channel 的最终回复可显示运行信息 — group conclusion: pass

| Scenario | Expected source | Verification method | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 已启用时显示模型和上下文占用 | `spec.md` | Journey 1: real Feishu normal message on the enabled isolated fixture | Fresh Bot message at 22:57 CST, position 356: `deepseek:deepseek-v4-flash · 3%` | pass | Both fields are under the reply body, separated by one blank line. |
| 中间消息不显示页脚 | `spec.md` | Journey 1 normal path; inspected the full fresh user/Bot exchange | The exchange contains the user probe and one ordinary Bot final post only; no separate progress/control/approval message or second footer post | pass | The ordinary path produces exactly one final user-visible post with the footer. Special messages are not user-triggerable in this dedicated ordinary-message profile. |
| 运行信息不完整时不显示虚假占位 | `spec.md` | Supporting automated provider-metadata fixture; no user-facing control can make the hosted test provider omit one terminal datum | M1 test evidence records the incomplete-data cases; ordinary real-platform response proved the primary delivery surface | not-applicable | The GIVEN is provider terminal metadata, not a user-selectable external-channel state. |

### Requirement: 页脚按外部 channel 配置控制 — group conclusion: pass

| Scenario | Expected source | Verification method | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 默认不暴露运行信息 | `spec.md` | Journey 3: real Feishu normal reply before the dedicated enabled fixture was added | Fresh plain Bot reply at 22:51 CST, during this review's default-off run | pass | No model or percentage was shown. |
| 全局开启覆盖所有外部 channel | `spec.md` | Journey 1: only currently shipped external channel | Fresh enabled Feishu post at position 356 | pass | Feishu is the sole current external channel; future-channel wording has no second product surface to operate. |
| 单一外部 channel 可以覆盖全局设置 | `spec.md` | Supporting typed-config/delivery test fixture; there is no second current external platform for a product comparison | Unit test evidence in `M1-gateway-runtime-footer/evidence.md` | not-applicable | The configuration override is operator-controlled and the required contrasting second channel does not currently exist. |
| 单一外部 channel 可以独立开启 | `spec.md` | Supporting typed-config/delivery test fixture; the dedicated Feishu fixture demonstrates the enabled consumer result | Journey 1 plus `M1-gateway-runtime-footer/evidence.md` | not-applicable | The independent-enable precondition is not exposed as a user action in the dedicated test chat. |

### Requirement: 内部 Web IM 保持原有消息体验 — group conclusion: pass

| Scenario | Expected source | Verification method | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 内部 Web IM 不显示外部页脚 | `spec.md`, reviewer runbook | Journey 2: linked isolated shadow check after the enabled Feishu final | Runner observed plain original assistant text in the corresponding shadow | pass | External footer did not cross into the internal shadow message. |

## Upstream Documentation Sync

- [x] `SPEC.md` (cross-package architecture): no update needed; this is a Gateway-only presentation policy.
- [x] `docs/specs/gateway/` (evergreen behavior): needs canonical merge of `specs/gateway/external-channels.md` delta during orchestrator closeout.
- [x] `AGENTS.md` / `CLAUDE.md`: no update needed.
- [x] `docs/specs/CONTRIBUTING.md`: no update needed; the documentation system itself did not change.

---

# Round 2 — 2026-08-15

> Validation snapshot: `6683c3f10 → c4d411dd8aef8faaf72839602cdbe4d90e18672d`
>
> Revalidation mode: full. This round supersedes Round 1's ordinary-text-footer
> presentation evidence: the user-required surface is now a native Feishu
> interactive card.

## Verdict

**pass**

**Highest Required Action:** `pass`

The enabled, non-production Feishu journey delivers one native card for the
ordinary final answer. In the Feishu client the answer is in the card body and
`deepseek:deepseek-v4-flash · ctx 2%` is in its compact bottom note, separated
by a rule. No standalone footer message was present. The corresponding
isolated Web IM conversation displayed the original answer body without that
model footer.

## User Journeys Exercised

1. **Dedicated Feishu ordinary final reply.** I first stopped any stale stack
   for this reviewer worktree, then started a new isolated IM + Gateway +
   dedicated Feishu listener from `c4d411dd8` using the runbook's
   `e2e-up.sh --feishu`. IM health and both reviewer-owned service PIDs were
   live before sending the probe. `scripts/e2e-feishu-probe.py --timeout 120`
   passed against the non-default test profile.
2. **Native-client visual inspection.** I opened the dedicated `测试agent`
   chat in the installed Feishu client and inspected the fresh
   `nano-e2e-feishu-probe-4746711c8514b54e` reply. It is a single white native
   card: its upper area reads `Received: ... — message delivered successfully
   over Feishu. Ready when you are.`, followed by a horizontal rule and the
   bottom note `deepseek:deepseek-v4-flash · ctx 2%`. The visual capture was
   made in that client during this review; it is intentionally not committed
   as a repository artifact.
3. **Internal Web IM shadow.** I signed into the isolated Web IM as the
   documented test user, opened the newly created `e2e · feishu` conversation,
   and observed the exact same reply body only: no `deepseek:...` model note
   is appended to the assistant bubble. The existing Web IM disclosure
   `5.4k tok · ctx 2%` remains in its own expandable internal process panel;
   it is not the Feishu-card footer and the reply body itself stayed plain.

The probe also binds the fresh nonce to exactly one final `interactive` reply
and checks the linked shadow body, so the real client observation is not being
mistaken for a second detached footer bubble or an unrelated historical card.

## Reference Artifacts Reviewed

N/A — no prototype, reference screenshot, or must-match visual design was
provided. The product-visible contract is the card layout in `spec.md` and
the native client inspection above.

## Issues

None.

## Side Findings

- Web IM retains its pre-existing expandable token/context panel. It neither
  adds the external model footer to the body nor changes the required Feishu
  card presentation, so it is not an issue in this unit.

## Acceptance Criteria Coverage

### Requirement: 外部 channel 的最终回复可显示运行信息 — group conclusion: pass

| Scenario | Expected source | Verification method | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 已启用的飞书最终回复是一张带运行信息的原生卡片 | `spec.md`; `design.md` Runbook | Journeys 1–2: dedicated profile, real test-user message, then installed Feishu client | Passed `e2e-feishu-probe.py`; native client saw one body/rule/note card for nonce `4746711c8514b54e` | pass | The card note contains both model and `ctx 2%`; no independent footer post was visible. |
| 已启用的其他外部 channel 显示运行信息 | `spec.md` | No second external channel exists in the shipped dedicated product environment | The only real external client is Feishu | not-applicable | This is a future-channel contract, not a user journey that can be fabricated during this review. |
| 中间消息不显示运行信息 | `spec.md` | The dedicated ordinary-message client journey has no user control that produces progress, approval, or control states | Fresh journey produced exactly its final card and no standalone footer message | not-applicable | The unexposed special-message preconditions are covered by durable delivery tests; they cannot be honestly claimed as a separate manual client journey here. |
| 运行信息不完整时不显示虚假占位 | `spec.md` | Provider terminal metadata cannot be chosen by the test user | N/A | not-applicable | No user-facing control can force a real provider to omit exactly one terminal fact. |
| 飞书卡片正文超出单卡可发送大小时保持一张可读卡片 | `spec.md` | No supported user action creates a deterministic oversized final reply in this dedicated fixture | N/A | not-applicable | The mandatory real-client normal-card path passed; overflow remains a deterministic implementation-level condition. |

### Requirement: 运行信息按外部 channel 配置控制 — group conclusion: pass

| Scenario | Expected source | Verification method | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 默认不暴露运行信息 | `spec.md` | The unit has no end-user or test-chat control for changing Gateway startup configuration | N/A | not-applicable | This is an operator configuration precondition, not an action the dedicated Feishu user can perform. |
| 全局开启覆盖所有外部 channel | `spec.md` | No second shipped external client is present | Feishu enabled journey above | not-applicable | A single real Feishu client cannot demonstrate a future second channel. |
| 单一外部 channel 可以覆盖全局设置 | `spec.md` | No operator-facing control is exposed in the dedicated chat | N/A | not-applicable | Platform precedence is a Gateway configuration contract, not a manual chat action. |
| 单一外部 channel 可以独立开启 | `spec.md` | No operator-facing control is exposed in the dedicated chat | Enabled Feishu fixture used by Journey 1 | not-applicable | The fixture proves the user-facing enabled result but cannot establish a separate global/override setup journey. |

### Requirement: 内部 Web IM 保持原有消息体验 — group conclusion: pass

| Scenario | Expected source | Verification method | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 内部 Web IM 不显示外部页脚 | `spec.md`; `design.md` Runbook | Journey 3: actual browser login to the isolated IM and newly created shadow conversation | The assistant bubble is only `Received: nano-e2e-feishu-probe-4746711c8514b54e — message delivered successfully over Feishu. Ready when you are.` | pass | There is no `deepseek:...` card footer in the body; the Web IM's pre-existing internal process panel is distinct. |

## Upstream Documentation Sync

- [x] `SPEC.md` (cross-package architecture): no update needed; this remains a Gateway presentation behavior.
- [x] `docs/specs/gateway/` (evergreen behavior): needs the unit's canonical modified delta merged during orchestrator closeout, replacing the old text-footer wording with the Feishu-card contract.
- [x] `AGENTS.md` / `CLAUDE.md`: no update needed.
- [x] `docs/specs/CONTRIBUTING.md`: no update needed; documentation-system behavior did not change.
