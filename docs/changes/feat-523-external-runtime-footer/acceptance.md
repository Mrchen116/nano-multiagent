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
