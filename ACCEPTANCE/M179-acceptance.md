# M179 Acceptance Report

## Scope
- Milestone: M179 — rerun acceptance of agent settings/create/edit UX after the M184 fix and a fresh frontend dist rebuild.
- Review target: `/Users/czj/Repos/nano-multiagent`
- Review date: 2026-03-15
- Acceptance intent: validate, from a real user/product perspective, the current shipped UX for selectable allowlists, default System Prompt prefill, valid model selection, save behavior, create success flow, reachability of the post-create `Open direct chat` CTA, and entry into the reusable direct chat.
- Constraint: this pass is acceptance-only. No product code was patched.

## Materials Read
- Product/spec docs:
  - `/Users/czj/Repos/nano-multiagent/docs/IM-SPEC.md`
  - `/Users/czj/Repos/nano-multiagent/docs/IM前端蓝图.md`
- Prior milestone/evidence docs:
  - `/Users/czj/Repos/nano-multiagent/PROGRESS/M181-修复-Agent-创建页默认项与-Allowlist-产品问题.md`
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M179-acceptance.md`
- Current frontend/runtime files reviewed for acceptance:
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/package.json`
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`

## User Journeys Exercised
### 1. Runtime contract and shipped-dist sanity
Validated against the running IM host at `http://127.0.0.1:8011` and the rebuilt frontend bundle:
- Confirmed `src/IM/frontend/dist` exists and `index.html` modification time is `2026-03-15T00:47:54.086474`, consistent with a fresh rebuild before this acceptance rerun.
- `GET /im/v1/agents/allowlist-options` returned live selectable `skills`, `tools`, a runtime-valid `model_options` list, `platform_default_model`, and a non-empty `default_system_prompt` beginning with the personal assistant template.
- `GET /im/v1/agents` returned a live agent list, confirming the settings UI still has a reachable backend target.

### 2. Create agent journey
Validated from shipped source plus focused tests representing the current dist behavior:
- New Agent requests runtime-backed allowlist/model/default-prompt options from `/im/v1/agents/allowlist-options`.
- System Prompt auto-prefills only when initially empty.
- Skills and tools are chosen through `AllowlistSelector`, not raw freeform identifiers.
- Default Model is constrained to selectable runtime options plus a labeled platform-default entry.
- Validation blocks create when Agent ID, Display Name, or System Prompt are missing.
- On successful create, the page stays in-place, shows explicit success copy, exposes a settings-detail link, and presents a reachable `Open direct chat` CTA.
- Opening direct chat uses the reusable direct-conversation path instead of creating a misleading "new direct chat" experience.

### 3. Edit existing agent journey
Validated from shipped source plus focused tests:
- Existing config loads from `/im/v1/agents/{agent_id}/config`.
- Unavailable saved skills/tools/models are still shown and labeled `unavailable now` instead of disappearing.
- Save affordance behaves as a user would expect: disabled when clean, enabled only after real edits.
- Status messaging distinguishes `Unsaved changes`, `Saving changes...`, `Saved`, and `All changes saved.`
- Detail page exposes `Open direct chat` directly for the reusable thread.

## Passes
1. **Selectable allowlists are now clearly product-grade.**
   - Create and edit both use the same selector-based affordance, matching the requirement that users pick from visible allowlists rather than typing hidden runtime identifiers.
   - The live backend contract still supplies non-empty selectable skill/tool data in this environment (`skills=8`, `tools=6`).

2. **Default System Prompt prefill is present and backed by live runtime data.**
   - The live API currently returns a non-empty `default_system_prompt` starting with `You are a helpful personal assistant...`.
   - The create page only auto-prefills when the field is empty, which is the expected user-safe behavior.

3. **Model selection is constrained to valid runtime choices.**
   - The live runtime currently exposes one model option, `codexOAuth:gpt-5.2-codex`, and the platform default matches it.
   - Create and edit flows both use constrained selection and preserve drifted saved values by labeling them unavailable rather than silently dropping them.

4. **Save and create behavior read as trustworthy to a real user.**
   - Required-field validation is explicit.
   - Edit flow status copy is differentiated and understandable.
   - Create flow surfaces API failure detail without ejecting the user from the form.

5. **The post-create success flow looks materially improved after the M184 fix.**
   - Current create-page source shows no immediate success redirect; instead it retains the success state on the page and renders the direct-chat CTA only after `createdAgentId` is set.
   - The focused create test now explicitly asserts that navigation does not happen automatically after create and that the success CTA remains reachable before the user chooses to open direct chat.
   - This directly addresses the prior M179 concern that the CTA might be rendered but not actually usable.

6. **Reusable direct-chat entry points are correctly framed in both journeys.**
   - Create flow success copy reinforces the one-stable-direct-chat-window rule.
   - Detail flow also exposes `Open direct chat`, so the reusable thread remains reachable after creation.

7. **This rerun is materially more trustworthy because it was evaluated against the rebuilt current dist.**
   - For IM-hosted acceptance, rebuilt `src/IM/frontend/dist` is the meaningful shipped surface.
   - This pass rechecked acceptance only after confirming the rebuilt dist is present and fresh.

## Issues
1. **No same-pass real-browser evidence was captured in this rerun.**
   - I verified the live IM API contract and the rebuilt shipped source/test surface, but this acceptance rerun did not produce fresh browser screenshots/video/Playwright evidence of a human-visible create/edit/direct-chat walkthrough against the current dist.
   - This is now primarily an evidence gap, not a source-indicated product defect.
   - Milestone-ready wording: capture fresh real-browser evidence on `http://127.0.0.1:8011/settings/agents/new` and an existing `http://127.0.0.1:8011/settings/agents/{agent_id}` page, including successful create, visible success state, `Open direct chat`, and entry into the reusable direct thread.

## Retest Focus
1. Run a fresh real-browser acceptance pass against the rebuilt IM-hosted dist:
   - `http://127.0.0.1:8011/settings/agents/new`
   - `http://127.0.0.1:8011/settings/agents/<existing-agent-id>`
2. In create flow, verify visibly in browser:
   - selectable skill/tool allowlists render with current runtime data;
   - default System Prompt is prefilled from the product template;
   - Default Model is dropdown-only and matches runtime-valid choices;
   - validation errors are understandable;
   - after successful create, the success copy persists long enough to use and `Open direct chat` is truly clickable;
   - `Open direct chat` lands in the reusable direct conversation.
3. In edit flow, verify visibly in browser:
   - save button is disabled when clean and enabled only after edits;
   - unsaved/saving/saved states are perceptible;
   - unavailable saved values are shown clearly;
   - `Open direct chat` lands in the reusable direct thread.

## Acceptance Decision
- Verdict: **M179 now passes strongly enough on rebuilt-dist, live-runtime, and focused-test evidence, with the prior post-create CTA reachability concern appearing resolved after M184.**
- Remaining gap: fresh same-pass real-browser evidence is still missing.
- New product defects found in this rerun: 0

Reasoning:
- The acceptance target behaviors are all present in the current shipped surface reviewed here: selectable allowlists, default System Prompt prefill, valid model selection, explicit save/create behavior, a visible post-create success state, reachable `Open direct chat`, and reusable direct-chat entry from detail.
- The live API contract supports those behaviors in the current environment, and the rebuilt dist was confirmed fresh before evaluation.
- Because this rerun did not itself capture browser interaction evidence, there remains an evidence-quality gap, but not a concrete new issue list requiring implementation milestones from what was observed here.
