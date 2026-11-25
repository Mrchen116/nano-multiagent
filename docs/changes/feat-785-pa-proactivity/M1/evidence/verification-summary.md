# `feat-785` M1 Implementation & Real-Stack Verification Evidence

## 1. Environment & Scope

- **Worktree**: `/Users/czj/.t3/worktrees/nano-multiagent/unit-feat-785-pa-proact-198281fb52fe0ec0` (`unit/feat-785-pa-proactivity`, base `origin/develop` `db7167c9d`)
- **Isolated Runtime Stack**: `./scripts/e2e-up.sh --profile daily --wt "$WT"` with `NANO_E2E_LOGICAL_CLOCK_SOCKET="$WT/.e2e-clock.sock"` and monotonic `NANO_E2E_INITIAL_LOGICAL_CLOCK_MS`
- **Live-LLM Model Route**: `codexOAuth:gpt-6.2-sol` via local bridge (`http://127.0.0.1:4000`)
- **Bound Personal Assistant Run Identity**:
  - `pa_agent_id`: `pa_ee944e66187f`
  - `pa_conversation_id`: `c_dtxxgc`
  - `group_id` (observed team group): `c_xjb8g1`
  - `pa_main_session_id`: `9946e13e-beed-4cbd-9830-d3077606e316`
- **Evidence Storage Boundary**: All temporary screenshots (`/tmp/feat-785-screenshots/*.png`), JSON output (`/tmp/feat-785-24h-report.json`), and isolated `.dsh-runtime/` / `.gateway-workspace/` files were kept outside Git tracking and cleaned up per `docs/development/worktree-runtime.md`.

## 2. 5-Checkpoint 24h Live-LLM Proactivity Acceptance (`scripts/verify_pa_proactivity_24h.py`)

Command executed:

```bash
NANO_E2E_LOGICAL_CLOCK_SOCKET="$WT/.e2e-clock.sock" \
  NANO_E2E_INITIAL_LOGICAL_CLOCK_MS="$INITIAL_MS" \
  ./scripts/e2e-up.sh --profile daily --wt "$WT"
python3 -u scripts/verify_pa_proactivity_24h.py --wt "$WT" --output /tmp/feat-785-24h-report.json --timeout-sec 360
```

Result: **Exit 0 (`"all_passed": true`)**.

| Checkpoint | Logical Time (`Asia/Shanghai`) | Verified Positive Value & Restraint Claims | Observed Metrics |
| --- | --- | --- | --- |
| **Warmup** | `2026-11-27T21:30+08:00` -> `21:50` | Natural owner chat established daily `09:10` morning alignment schedule against logical clock without pre-filling daily schedule. | `pa_main_session_id = 9946e13e-beed-4cbd-9830-d3077606e316` |
| **Checkpoint 1** (`quiet_accounting`) | `23:00` -> `23:15` -> `00:05` -> `00:20` | Recorded explicit Nano 3-min Demo commitment as progressive DAG (`1` graph, `5` nodes); `00:05` reschedule updated existing task & native schedule in place without duplicating graphs; `23:15` and `00:20` `<proactive-review-wake>` passes sent `0` outbound messages, created `0` premature `proposed` cards, and created `0` family cards. | `graphs_at_2315 = 1`, `proposed_at_2315 = 0`, `proposed_at_0020 = 0`, `silent_after_2315_and_0020 = true` |
| **Checkpoint 2** (`dreaming_and_nightly`) | `2026-11-28T03:05+08:00` -> `03:15` | `Dreaming` consolidated `MEMORY.md` (`697` chars) at `03:05` local natural-day anchor; `<proactive-nightly-wake>` received inline `<updated-formal-memory>` (`session.v4.jsonl.zstd#seq=292`), prepared `[Pending Morning Brief]` in `notes`, created `2` high-signal `status="proposed"` cards (`验证独立创作者的多平台发稿痛点`, `由 PA 起草 Nano 三镜头分镜和旁白`) with `proposal.{rationale, on_approve}`, honored family non-proposal boundary (`0` family cards), and sent `0` nighttime messages. | `memory_chars = 697`, `updated_formal_memory_inlined = true`, `proposed_count = 2`, `family_cards = 0`, `night_outbound_messages = 0` |
| **Checkpoint 3①** (`morning_combined_brief`) | `2026-11-28T09:12+08:00` | Existing `09:10` recurring schedule consumed `[Pending Morning Brief]` and sent **1** cohesive message (`217bb1ce515c48e99566556a95c02510`) combining prepared 3-shot Demo substance, `2` live `task_cards`, and an open priority-alignment invitation without creating a second morning schedule or pre-filling the owner's day. | `morning_message_count = 1`, `task_cards_count = 2` |
| **Checkpoint 4** (`pre_schedule_observation_sync`) | `10:00` -> `12:25` (group) -> `12:32` | Owner announced Demo first-cut completion in observed group `c_xjb8g1` at `12:25` (inside normal `10m` batch window); `12:30` `schedule` pre-step forced `product.proactive.sync_observations` (`Fresh observation sync completed before this scheduled check` verified in session trace), updating progress without sending a stale nudge. | `sync_banner_verified_in_trace = true`, `scheduled_turn_steps = 4` |
| **Checkpoint 5** (`single_shot_doing_and_idle`) | Post-noon `approve_task` + `6s` hold | Approving PA-assigned `proposed` card (`tg_e563229f` / `n1`) triggered single-shot `doing_wake` injecting `Current Task context:` with North-Star metadata (`7` wake steps), delegated/delivered research findings, and settled cleanly to `idle` with **`0` extra steps** across a subsequent `6s` hold (proving retirement of the legacy 256-turn `idle` loop). | `wake_steps = 7`, `extra_steps_after_6s_idle = 0` |
| **Checkpoint 3②** (`zero_value_control_night`) | Control night `22:50` -> `23:15` -> `03:05` -> `03:15` -> `09:30` | With recurring morning cron removed and only casual small talk (`散步喝热牛奶`), `<proactive-nightly-wake>` executed on schedule (verified in session trace) and produced `0` `proposed` cards, `0` morning schedules, `0` morning LLM wakes (`03:15..09:30`), and `0` hollow morning briefs. | `proactive_nightly_verified_in_trace = true`, `new_proposed_cards = 0`, `active_morning_schedules = 0`, `morning_wakes_between_0315_and_0930 = 0`, `hollow_morning_messages = 0` |

### Trace & Cache Prefix Verification Note

- On this development host, `LLM_PROXY` (`127.0.0.1:4000`) runs with `REQUEST_LOGGING_ENABLED=false` (an external host service setting not modified per repository boundary rules). Live session wake blocks (`<proactive-review-wake>`, `<proactive-nightly-wake>`, `<updated-formal-memory>`, `Fresh observation sync completed`, `Current Task context:`) and step counts were verified directly from the isolated DSH session log (`session.v4.jsonl.zstd`) and IM `/work` records.
- Wire-level Anthropic prompt cache prefix stability (`PA=false` and `PA=true`) was verified via `pnpm exec vitest run packages/dsh-integration/tests/context-cache-prefix-provider.test.ts` (**2/2 PASS**). `tla2tools.jar` is not installed on this host (`TLA2TOOLS=""`), so TLC model checking was skipped and recorded as an environment boundary per `verify-context-cache-prefix`.

## 3. Web IM (`1280x860` & `390x844`) & Native iOS Verification vs `prototype.html`

| Surface / `must-match` Requirement | Platform & Viewport | Result & Self-Check Corrections |
| --- | --- | --- |
| Dual-Lens `/tasks` (`当前行动` / `长线目标`), default `与我有关`, Crewden pill popovers (0 native `<select>`), quick-capture bar (`mode: "none"`), `拆多步目标` | Web `1280x860` & `390x844`, iOS SwiftUI (`TasksView.swift`) | **PASS** (`native_select_count = 0`, `focus_overflow = false` on both `1280` & `390`). Fixed `390px` quick-capture input to occupy full top row inside rounded composer and aligned mobile filter popovers (`left: 0`) so menus never clip off-screen. |
| `待你拍板 ⇄ 先存着` switcher, 9-status `.tasks-badge` (no wait-reason/assignee text inside badge), `批准开工` / `批准立项` (`prereq_blocked`), folded `查看已完结记录` | Web `1280x860` & `390x844`, iOS SwiftUI (`TasksView.swift`) | **PASS** — badges strictly render the 9 status labels (`待拍板`, `待办`, `推进中`, `等待中`, `待确认`, `已完成`, `已暂缓`, `先存着`, `已关闭`) with wait reason / next check / assignee rendered to the right. |
| `? 状态说明` 9-status flow diagram modal (`一张图看懂任务状态与页面分区`) | Web `1280x860` & `390x844`, iOS sheet | **PASS** — main track (`待拍板 -> 待办 -> 推进中 -> 待确认 -> 已完成`), side branches (`先存着` / `已关闭`, `等待中` / `已暂缓`), and 3-zone guide verified on screen. |
| Stage-adaptive Task Detail Drawer / Bottom Sheet | Web `1280x860` (452px drawer) & `390x844` (bottom sheet), iOS sheet | **PASS** — `proposed` card displays `为什么提议 & 批准后怎么做` (`rationale` + `on_approve`) and `批准开工` / `先存着` / `关闭` footer actions without empty result noise. |
| Goal Graph Panorama (`/tasks/:graphId`): North-Star banner (`终局目标`), desktop DAG/explore canvas, mobile `< 768px` default Vertical Stage Spine (`纵向脉络`) | Web `1280x860` & `390x844`, iOS `TaskGraphView.swift` | **PASS** (`panorama_overflow = false`, `spine_overflow = false`). Caught and fixed `390px` compact header breadcrumb (`‹ 返回任务聚焦`) wrapping by giving `.tasks-breadcrumbs` `flex: 1 1 100%` on `< 768px`. |
| Live synchronized `task_cards` inside chat bubbles (`MessageTaskCards` / `TaskEmbeddedCardsView`) | Web `1280x860` & `390x844`, iOS `ChatMessageView.swift` + GRDB `v7_message_task_cards` | **PASS** — rendered inline inside PA chat bubbles with live-synced status badge (`已完成` / `待拍板`) and `去任务页查看 ›` deep-link navigation. |
| PA-only `主动筹划` (`proactive_planning`) toggle & `task_graph` dependency feedback | Web `/settings/agents/:paId` vs ordinary agent, iOS `AgentConfigView.swift` & `PersonalAgentManagementView.swift` | **PASS** — `pa_proactive_visible = true` under `特性开关` for PA, `ordinary_agent_proactive_count = 0` for `daily-product`, floating `CapabilityToast` portal avoids layout shift. |
| Native iOS Build, Simulator Unit/Contract Suite & Release Archive | Xcode (`build.sh test`, `build.sh build`, `build.sh archive`, `pnpm check:ios-runtime`) | **PASS** — `257` XCTests + `44` Swift Testing tests passed (`0` failures), Simulator Debug `.app` and Release unsigned `.ipa` (`NanoIM-unsigned.ipa`) built cleanly; temporary simulator deleted. |
